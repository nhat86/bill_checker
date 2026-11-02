"""Quantity & Billing audit — the deterministic comparison of what was
bought (basket) vs what was charged (receipt lines).

Statuses:
  CONFIRMED          — arithmetic is provably wrong
  POTENTIAL          — strong suspicion (e.g. charged more than bought)
  NEEDS_CONFIRMATION — plausible but data is uncertain (unconfirmed basket)
  UNVERIFIABLE       — can't decide with current data
"""

from collections import defaultdict
from decimal import Decimal

from app.engines.types import BasketEntry, Finding, ReceiptLine

TOLERANCE = Decimal("0.02")


def _price_of(lines: list[ReceiptLine]) -> Decimal | None:
    for line in lines:
        if line.unit_price is not None:
            return line.unit_price
    return None


def _confidence(user_confirmed: bool) -> Decimal:
    return Decimal("0.9") if user_confirmed else Decimal("0.6")


def audit_quantities(basket: list[BasketEntry], lines: list[ReceiptLine]) -> list[Finding]:
    """Compare quantities per match-key: diff = receipt_qty - basket_qty."""
    basket_by_key: dict[str, BasketEntry] = {}
    for entry in basket:
        if entry.key in basket_by_key:
            prev = basket_by_key[entry.key]
            basket_by_key[entry.key] = BasketEntry(
                key=entry.key,
                label=entry.label,
                quantity=prev.quantity + entry.quantity,
                user_confirmed=prev.user_confirmed or entry.user_confirmed,
                product_id=prev.product_id or entry.product_id,
            )
        else:
            basket_by_key[entry.key] = entry

    lines_by_key: dict[str, list[ReceiptLine]] = defaultdict(list)
    for line in lines:
        lines_by_key[line.key].append(line)

    findings: list[Finding] = []
    all_keys = set(basket_by_key) | set(lines_by_key)
    for key in sorted(all_keys):
        b = basket_by_key.get(key)
        charged = lines_by_key.get(key, [])
        receipt_qty = sum((l.quantity for l in charged), Decimal("0"))
        unit = _price_of(charged)

        if b is None:  # charged but not in basket
            line = charged[0]
            amount = receipt_qty * unit if unit else None
            findings.append(
                Finding(
                    finding_type="UNPURCHASED_CHARGED",
                    status="NEEDS_CONFIRMATION",
                    product_name=line.description,
                    actual_amount=amount,
                    difference=amount,
                    confidence=Decimal("0.6"),
                    evidence={"receipt_quantity": str(receipt_qty), "lines": len(charged)},
                    explanation_fr=(
                        f"Produit facturé ({receipt_qty} × {unit or '?'} €) absent du panier "
                        f"— achat oublié ou facturation erronée."
                    ),
                )
            )
            continue

        diff = receipt_qty - b.quantity
        if diff == 0:
            continue
        amount = abs(diff) * unit if unit else None
        if diff > 0:  # overcharged
            findings.append(
                Finding(
                    finding_type="QUANTITY_MISMATCH",
                    status="POTENTIAL" if b.user_confirmed else "NEEDS_CONFIRMATION",
                    product_name=b.label,
                    expected_amount=b.quantity * unit if unit else None,
                    actual_amount=receipt_qty * unit if unit else None,
                    difference=amount,
                    confidence=_confidence(b.user_confirmed),
                    evidence={
                        "basket_quantity": str(b.quantity),
                        "receipt_quantity": str(receipt_qty),
                        "unit_price": str(unit) if unit else None,
                    },
                    explanation_fr=(
                        f"Quantité facturée ({receipt_qty}) supérieure au panier "
                        f"({b.quantity}) — surfacturation potentielle de {diff} article(s)."
                    ),
                )
            )
        else:  # basket item missing from receipt
            findings.append(
                Finding(
                    finding_type="MISSING_RECEIPT_ITEM",
                    status="UNVERIFIABLE",
                    product_name=b.label,
                    expected_amount=b.quantity * unit if unit else None,
                    actual_amount=Decimal("0"),
                    difference=None,
                    confidence=_confidence(b.user_confirmed),
                    evidence={
                        "basket_quantity": str(b.quantity),
                        "receipt_quantity": str(receipt_qty),
                    },
                    explanation_fr=(
                        f"{-diff} article(s) du panier introuvable(s) sur le ticket — "
                        f"article offert, autre ticket, ou erreur de reconnaissance."
                    ),
                )
            )
    return findings


def audit_billing(
    lines: list[ReceiptLine],
    receipt_total: Decimal | None,
    discounts_total: Decimal | None = None,
) -> list[Finding]:
    """Internal consistency of the receipt itself: duplicates, line math, total."""
    findings: list[Finding] = []

    # 1. duplicate identical lines (same key, unit price, qty=1) — classic double-scan
    singles: dict[tuple[str, Decimal | None], list[ReceiptLine]] = defaultdict(list)
    for line in lines:
        if line.quantity == 1:
            singles[(line.key, line.unit_price)].append(line)
    for (key, unit), group in singles.items():
        if len(group) > 1:
            amount = unit * (len(group) - 1) if unit else None
            findings.append(
                Finding(
                    finding_type="DUPLICATE_LINE",
                    status="POTENTIAL",
                    product_name=group[0].description,
                    actual_amount=unit * len(group) if unit else None,
                    expected_amount=unit if unit else None,
                    difference=amount,
                    confidence=Decimal("0.7"),
                    evidence={"occurrences": len(group), "unit_price": str(unit)},
                    explanation_fr=(
                        f"Ligne identique facturée {len(group)} fois — "
                        f"double scan possible ({amount} € si erreur)."
                    ),
                )
            )

    # 2. per-line arithmetic: quantity × unit ≈ total
    for line in lines:
        if line.unit_price is None or line.total_price is None:
            continue
        expected = line.quantity * line.unit_price
        if abs(expected - line.total_price) > TOLERANCE:
            findings.append(
                Finding(
                    finding_type="ARITHMETIC_ERROR",
                    status="CONFIRMED",
                    product_name=line.description,
                    expected_amount=expected,
                    actual_amount=line.total_price,
                    difference=line.total_price - expected,
                    confidence=Decimal("0.95"),
                    evidence={
                        "quantity": str(line.quantity),
                        "unit_price": str(line.unit_price),
                        "total_price": str(line.total_price),
                    },
                    explanation_fr=(
                        f"Incohérence de calcul: {line.quantity} × {line.unit_price} € = "
                        f"{expected} €, mais {line.total_price} € facturé."
                    ),
                )
            )

    # 3. sum of lines vs receipt total — discounts count toward the total
    #    (they're separate rows on French receipts, usually negative amounts)
    if receipt_total is not None and lines:
        items_sum = sum(
            (l.total_price for l in lines if l.total_price is not None), Decimal("0")
        )
        computed = items_sum + (discounts_total or Decimal("0"))
        diff = computed - receipt_total
        if abs(diff) > TOLERANCE:
            findings.append(
                Finding(
                    finding_type="TOTAL_MISMATCH",
                    status="NEEDS_CONFIRMATION",
                    product_name="(ticket complet)",
                    expected_amount=items_sum,
                    actual_amount=receipt_total,
                    difference=diff,
                    confidence=Decimal("0.6"),
                    evidence={
                        "items_sum": str(items_sum),
                        "discounts_total": str(discounts_total or "0"),
                        "receipt_total": str(receipt_total),
                    },
                    explanation_fr=(
                        f"Somme des lignes et remises ({computed} €) ≠ total du ticket "
                        f"({receipt_total} €) — ligne OCR manquante ou remise non lue."
                    ),
                )
            )
    return findings
