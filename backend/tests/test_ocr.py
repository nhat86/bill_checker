"""OCR pipeline tests — the provider is faked; we test the deterministic
validation + persistence, which is where correctness actually lives."""

import io
from datetime import date
from decimal import Decimal

import pytest

from app.services.ocr import get_ocr_provider
from app.services.ocr.types import ReceiptExtraction, ReceiptLineExtraction


def _extraction(**overrides) -> ReceiptExtraction:
    base = ReceiptExtraction(
        retailer_hint="CARREFOUR",
        purchase_date=date(2026, 10, 30),
        total_amount=Decimal("5.80"),
        lines=[
            ReceiptLineExtraction(
                description="LAIT DEMI ECREME 1L",
                quantity=Decimal("2"),
                unit_price=Decimal("1.45"),
                total_price=Decimal("2.90"),
            ),
            ReceiptLineExtraction(
                description="PAIN CAMPAGNE 400G",
                unit_price=Decimal("3.10"),
                total_price=Decimal("3.10"),
            ),
            ReceiptLineExtraction(
                description="REMISE CARTE",
                kind="discount",
                total_price=Decimal("-0.20"),
            ),
        ],
        raw_text="TICKET BRUT",
        confidence=0.9,
    )
    return base.model_copy(update=overrides)


class _FakeProvider:
    def __init__(self, extraction: ReceiptExtraction) -> None:
        self._extraction = extraction

    def extract(self, image: bytes, content_type: str) -> ReceiptExtraction:
        return self._extraction


@pytest.fixture
def fake_ocr(client, monkeypatch):
    """Swap the OCR provider via dependency_overrides; returns a setter."""
    from app.main import app

    def _set(extraction: ReceiptExtraction) -> None:
        app.dependency_overrides[get_ocr_provider] = lambda: _FakeProvider(extraction)

    yield _set
    app.dependency_overrides.pop(get_ocr_provider, None)


def _receipt_id(client, auth_headers) -> tuple[str, str]:
    sid = client.post("/api/v1/sessions", headers=auth_headers).json()["id"]
    client.post(
        f"/api/v1/sessions/{sid}/receipt",
        headers=auth_headers,
        files=[("file", ("t.jpg", io.BytesIO(b"\xff\xd8fake-jpg"), "image/jpeg"))],
    )
    detail = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers).json()
    return sid, detail["receipts"][0]["id"]


def test_parse_creates_items_and_discounts(client, auth_headers, fake_ocr):
    fake_ocr(_extraction())
    sid, rid = _receipt_id(client, auth_headers)

    resp = client.post(f"/api/v1/sessions/{sid}/receipts/{rid}/parse", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["items"]) == 2
    assert body["items"][0]["description"] == "LAIT DEMI ECREME 1L"
    assert Decimal(body["items"][0]["quantity"]) == Decimal("2")
    assert len(body["discounts"]) == 1
    assert Decimal(body["discounts"][0]["amount"]) == Decimal("-0.20")
    assert body["total_amount"] == "5.80"
    # arithmetic is consistent (2,90 + 3,10 - 0,20 = 5,80) → confidence boosted
    assert Decimal(body["parse_confidence"]) >= Decimal("0.9")


def test_parse_penalizes_incoherent_total(client, auth_headers, fake_ocr):
    # items sum to 6.00 but ticket says 5.80 → discrepancy detected by math, not the LLM
    fake_ocr(_extraction(
        lines=[
            ReceiptLineExtraction(description="PRODUIT A", unit_price=Decimal("6.00"), total_price=Decimal("6.00")),
        ],
        total_amount=Decimal("5.80"),
    ))
    sid, rid = _receipt_id(client, auth_headers)

    body = client.post(f"/api/v1/sessions/{sid}/receipts/{rid}/parse", headers=auth_headers).json()
    assert Decimal(body["parse_confidence"]) < Decimal("0.9")


def test_parse_penalizes_bad_line_math(client, auth_headers, fake_ocr):
    fake_ocr(_extraction(
        lines=[
            ReceiptLineExtraction(
                description="ERREUR QTE", quantity=Decimal("3"),
                unit_price=Decimal("1.45"), total_price=Decimal("9.99"),  # 3×1.45=4.35
            ),
        ],
        total_amount=None,
    ))
    sid, rid = _receipt_id(client, auth_headers)
    body = client.post(f"/api/v1/sessions/{sid}/receipts/{rid}/parse", headers=auth_headers).json()
    assert Decimal(body["parse_confidence"]) < Decimal("0.85")


def test_reparse_is_idempotent(client, auth_headers, fake_ocr):
    fake_ocr(_extraction())
    sid, rid = _receipt_id(client, auth_headers)
    client.post(f"/api/v1/sessions/{sid}/receipts/{rid}/parse", headers=auth_headers)
    body = client.post(f"/api/v1/sessions/{sid}/receipts/{rid}/parse", headers=auth_headers).json()
    assert len(body["items"]) == 2  # not 4


def test_parse_requires_receipt_image(client, auth_headers, fake_ocr):
    fake_ocr(_extraction())
    sid = client.post("/api/v1/sessions", headers=auth_headers).json()["id"]
    # receipt row needs an image; use a fake id → 404
    import uuid

    resp = client.post(
        f"/api/v1/sessions/{sid}/receipts/{uuid.uuid4()}/parse", headers=auth_headers
    )
    assert resp.status_code == 404
