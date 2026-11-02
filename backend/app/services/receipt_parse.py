"""Receipt parse pipeline — deterministic side of OCR.

Provider output is *claims*; this module:
1. rewrites receipt/items/discounts rows from the extraction,
2. verifies arithmetic (line math, sum vs total) — LLMs misread, math doesn't,
3. derives a parse_confidence from checks, not from the model's self-assessment.
"""

from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.models import AuditEvent, Receipt, ReceiptDiscount, ReceiptItem
from app.services.ocr.types import ReceiptExtraction

TOLERANCE = Decimal("0.02")  # cent rounding slack per line/receipt


class ParseOutcome(NamedTuple):
    confidence: float
    warnings: list[str]


def _check_arithmetic(ext: ReceiptExtraction) -> ParseOutcome:
    """Score the extraction by consistency, not by the model's claimed confidence."""
    score = ext.confidence
    warnings: list[str] = []

    for line in ext.lines:
        if line.unit_price is not None and line.total_price is not None:
            expected = line.quantity * line.unit_price
            if abs(expected - line.total_price) > TOLERANCE:
                warnings.append(
                    f"Ligne incohérente: '{line.description}' "
                    f"{line.quantity}×{line.unit_price} ≠ {line.total_price}"
                )
                score -= 0.15

    if ext.total_amount is not None and ext.lines:
        items_sum = sum(
            (l.total_price or Decimal("0")) for l in ext.lines if l.kind == "item"
        )
        discounts_sum = sum(
            (l.total_price or Decimal("0")) for l in ext.lines if l.kind == "discount"
        )
        computed = items_sum + discounts_sum  # discounts carry negative totals
        diff = abs(computed - ext.total_amount)
        if diff <= TOLERANCE:
            score += 0.1
        elif diff > Decimal("0.10"):
            warnings.append(
                f"Total incohérent: lignes {computed} vs ticket {ext.total_amount} (écart {diff})"
            )
            score -= 0.3

    if not ext.lines:
        warnings.append("Aucune ligne produit détectée")
        score -= 0.2

    return ParseOutcome(confidence=max(0.0, min(1.0, score)), warnings=warnings)


def apply_extraction(db: Session, receipt: Receipt, ext: ReceiptExtraction) -> ParseOutcome:
    """Persist extraction into receipt/items/discounts and log an audit event.

    Re-parse is idempotent: previous lines are replaced, not duplicated.
    """
    # Assign collections wholesale: delete-orphan cascade removes old rows,
    # and the in-memory state matches the DB (no stale collections).
    receipt.items = [
        ReceiptItem(
            description=line.description,
            ean=line.ean,
            quantity=line.quantity,
            unit_price=line.unit_price,
            total_price=line.total_price,
            line_confidence=line.confidence,
        )
        for line in ext.lines
        if line.kind == "item"
    ]
    receipt.discounts = [
        ReceiptDiscount(
            description=line.description,
            amount=line.total_price or Decimal("0"),
            discount_type="ocr_extracted",
        )
        for line in ext.lines
        if line.kind == "discount"
    ]

    receipt.raw_ocr_text = ext.raw_text
    receipt.purchase_date = ext.purchase_date
    receipt.total_amount = ext.total_amount

    outcome = _check_arithmetic(ext)
    receipt.parse_confidence = outcome.confidence

    db.add(
        AuditEvent(
            session_id=receipt.session_id,
            event_type="receipt_parsed",
            payload={
                "receipt_id": str(receipt.id),
                "confidence": outcome.confidence,
                "warnings": outcome.warnings,
                "retailer_hint": ext.retailer_hint,
                "item_count": sum(1 for l in ext.lines if l.kind == "item"),
                "discount_count": sum(1 for l in ext.lines if l.kind == "discount"),
            },
        )
    )
    return outcome
