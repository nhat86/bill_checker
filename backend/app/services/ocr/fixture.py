"""Fixture provider — canned Carrefour-style receipt for dev without an API key.

Enable with OCR_BACKEND=fixture. Lets the whole parse pipeline run offline.
NOT for real user findings — clearly labelled synthetic data.
"""

from datetime import date
from decimal import Decimal

from app.services.ocr.types import ReceiptExtraction, ReceiptLineExtraction

_FIXTURE = ReceiptExtraction(
    retailer_hint="CARREFOUR",
    store_hint="CARR EXPRESS",
    purchase_date=date(2026, 10, 30),
    total_amount=Decimal("5.80"),
    lines=[
        ReceiptLineExtraction(
            description="LAIT DEMI ECREME 1L",
            quantity=Decimal("2"),
            unit_price=Decimal("1.45"),
            total_price=Decimal("2.90"),
            confidence=0.95,
        ),
        ReceiptLineExtraction(
            description="PAIN CAMPAGNE 400G",
            quantity=Decimal("1"),
            unit_price=Decimal("3.10"),
            total_price=Decimal("3.10"),
            confidence=0.9,
        ),
        ReceiptLineExtraction(
            description="REMISE CARTE FIDELITE",
            kind="discount",
            total_price=Decimal("-0.20"),
            confidence=0.85,
        ),
    ],
    raw_text=(
        "CARREFOUR\nCARR EXPRESS\nTicket N. 00123\n"
        "LAIT DEMI ECREME 1L  2x1,45   2,90\nPAIN CAMPAGNE 400G          3,10\n"
        "REMISE CARTE FIDELITE        -0,20\nTOTAL                      5,80\n"
        "30/10/2026 18:42\n"
    ),
    confidence=0.9,
)


class FixtureOCRProvider:
    def extract(self, image: bytes, content_type: str) -> ReceiptExtraction:
        return _FIXTURE
