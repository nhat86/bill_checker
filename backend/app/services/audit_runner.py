"""Audit runner — the ONLY bridge between engines and the database.

Maps ORM rows → engine dataclasses, runs deterministic engines, persists
Findings as AuditFinding rows, logs AuditEvents. Idempotent: re-running
replaces this engine's findings, never duplicates.
"""

import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.engines import audit_billing, audit_quantities
from app.engines.types import BasketEntry, Finding, ReceiptLine, normalize
from app.models import AuditEvent, AuditFinding, AuditSession, ReceiptItem

BILLING_FINDING_TYPES = (
    "QUANTITY_MISMATCH",
    "MISSING_RECEIPT_ITEM",
    "UNPURCHASED_CHARGED",
    "DUPLICATE_LINE",
    "ARITHMETIC_ERROR",
    "TOTAL_MISMATCH",
)


def _match_key(ean: str | None, label: str | None) -> str:
    # EAN is a stronger identity than any text; fall back to normalized label
    if ean:
        return f"ean:{ean}"
    return f"txt:{normalize(label or '')}"


def run_billing_audit(db: Session, session: AuditSession) -> list[AuditFinding]:
    basket = [
        BasketEntry(
            key=_match_key(item.ean, item.label),
            label=item.label or "(inconnu)",
            quantity=Decimal(item.quantity),
            user_confirmed=item.user_confirmed,
            product_id=str(item.product_id) if item.product_id else None,
        )
        for item in session.basket_items
        if item.label or item.ean  # photo-only rows carry no matchable identity yet
    ]
    receipt_ids = [r.id for r in session.receipts]
    lines = [
        ReceiptLine(
            key=_match_key(item.ean, item.description),
            description=item.description,
            quantity=Decimal(item.quantity),
            unit_price=Decimal(item.unit_price) if item.unit_price is not None else None,
            total_price=Decimal(item.total_price) if item.total_price is not None else None,
            ean=item.ean,
        )
        for item in db.scalars(
            select(ReceiptItem).where(ReceiptItem.receipt_id.in_(receipt_ids))
        ).all()
    ]
    totals = [r.total_amount for r in session.receipts if r.total_amount is not None]
    receipt_total = sum(totals, Decimal("0")) if totals else None
    discounts_total = sum(
        (Decimal(d.amount) for r in session.receipts for d in r.discounts),
        Decimal("0"),
    )

    findings: list[Finding] = audit_quantities(basket, lines) + audit_billing(
        lines, receipt_total, discounts_total
    )

    # replace this engine's previous findings (idempotent re-run)
    db.execute(
        delete(AuditFinding).where(
            AuditFinding.session_id == session.id,
            AuditFinding.finding_type.in_(BILLING_FINDING_TYPES),
        )
    )
    rows = [
        AuditFinding(
            session_id=session.id,
            product_id=uuid.UUID(f.product_id) if f.product_id else None,
            finding_type=f.finding_type,
            status=f.status,
            product_name=f.product_name,
            expected_amount=f.expected_amount,
            actual_amount=f.actual_amount,
            difference=f.difference,
            confidence=f.confidence,
            evidence=f.evidence,
            explanation_fr=f.explanation_fr,
            is_deferred=f.is_deferred,
        )
        for f in findings
    ]
    db.add_all(rows)
    session.status = "COMPLETED"
    db.add(
        AuditEvent(
            session_id=session.id,
            event_type="billing_audit_completed",
            payload={
                "basket_entries": len(basket),
                "receipt_lines": len(lines),
                "findings": len(findings),
                "by_type": {t: sum(1 for f in findings if f.finding_type == t) for t in BILLING_FINDING_TYPES},
            },
        )
    )
    db.commit()
    return rows
