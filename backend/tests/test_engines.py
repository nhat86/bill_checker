"""Engine unit tests — pure data in, findings out. No DB, no HTTP.

Mandatory scenarios from spec §15 (quantity/billing subset)."""

from decimal import Decimal

from app.engines import audit_billing, audit_quantities
from app.engines.types import BasketEntry, ReceiptLine


def _basket(label: str, qty: str, ean: str | None = None, confirmed: bool = True) -> BasketEntry:
    key = f"ean:{ean}" if ean else f"txt:{label.lower()}"
    return BasketEntry(key=key, label=label, quantity=Decimal(qty), user_confirmed=confirmed)


def _line(desc: str, qty: str, unit: str | None = None, total: str | None = None, ean: str | None = None) -> ReceiptLine:
    key = f"ean:{ean}" if ean else f"txt:{desc.lower()}"
    return ReceiptLine(
        key=key, description=desc, quantity=Decimal(qty),
        unit_price=Decimal(unit) if unit else None,
        total_price=Decimal(total) if total else None,
        ean=ean,
    )


def test_two_bought_two_charged_no_findings():
    basket = [_basket("lait 1l", "2")]
    lines = [_line("LAIT 1L", "2", "1.45", "2.90")]
    assert audit_quantities(basket, lines) == []


def test_two_bought_three_charged_overbilling():
    basket = [_basket("lait 1l", "2")]
    lines = [_line("LAIT 1L", "3", "1.45", "4.35")]
    findings = audit_quantities(basket, lines)
    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "QUANTITY_MISMATCH"
    assert f.status == "POTENTIAL"  # confirmed basket → strong signal
    assert f.difference == Decimal("1.45")


def test_unconfirmed_basket_lowers_status():
    basket = [_basket("lait 1l", "2", confirmed=False)]
    lines = [_line("LAIT 1L", "3", "1.45", "4.35")]
    findings = audit_quantities(basket, lines)
    assert findings[0].status == "NEEDS_CONFIRMATION"


def test_charged_not_in_basket():
    basket = [_basket("lait 1l", "2")]
    lines = [_line("LAIT 1L", "2", "1.45", "2.90"), _line("EAU 1L5", "1", "0.80", "0.80")]
    findings = audit_quantities(basket, lines)
    assert [f.finding_type for f in findings] == ["UNPURCHASED_CHARGED"]
    assert findings[0].difference == Decimal("0.80")


def test_basket_item_missing_from_receipt():
    basket = [_basket("lait 1l", "2"), _basket("beurre 250g", "1")]
    lines = [_line("LAIT 1L", "2", "1.45", "2.90")]
    findings = audit_quantities(basket, lines)
    assert [f.finding_type for f in findings] == ["MISSING_RECEIPT_ITEM"]
    assert findings[0].status == "UNVERIFIABLE"


def test_ean_match_beats_label_mismatch():
    # same product, different wording — EAN still unifies them
    basket = [_basket("lait demi ecreme", "1", ean="3017620422003")]
    lines = [_line("LAIT D/ECR 1L CRF", "1", "1.45", "1.45", ean="3017620422003")]
    assert audit_quantities(basket, lines) == []


def test_duplicate_identical_lines():
    lines = [
        _line("BAGUETTE", "1", "1.10", "1.10"),
        _line("BAGUETTE", "1", "1.10", "1.10"),
        _line("LAIT", "2", "1.45", "2.90"),  # qty=2 on ONE line is fine
    ]
    findings = audit_billing(lines, None)
    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "DUPLICATE_LINE"
    assert f.status == "POTENTIAL"
    assert f.difference == Decimal("1.10")  # one extra charge


def test_line_arithmetic_error():
    lines = [_line("PRODUIT X", "3", "1.45", "9.99")]  # 3×1.45 = 4.35
    findings = audit_billing(lines, None)
    assert findings[0].finding_type == "ARITHMETIC_ERROR"
    assert findings[0].status == "CONFIRMED"


def test_total_mismatch_detected():
    lines = [_line("A", "1", "2.00", "2.00"), _line("B", "1", "3.00", "3.00")]
    findings = audit_billing(lines, Decimal("4.50"))  # sum=5.00, total=4.50
    assert any(f.finding_type == "TOTAL_MISMATCH" for f in findings)


def test_clean_receipt_no_findings():
    lines = [_line("A", "1", "2.00", "2.00"), _line("B", "2", "1.50", "3.00")]
    assert audit_billing(lines, Decimal("5.00")) == []


def test_discount_lines_count_toward_total():
    # French receipts print remises as separate negative lines —
    # items_sum + discounts must equal the receipt total, not items alone
    lines = [_line("A", "1", "6.00", "6.00")]
    assert audit_billing(lines, Decimal("5.80"), discounts_total=Decimal("-0.20")) == []
