from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class ReceiptLineExtraction(BaseModel):
    """One line as read on the receipt — item or discount, exactly as seen."""

    description: str
    kind: Literal["item", "discount"] = "item"
    ean: str | None = None
    quantity: Decimal = Decimal("1")
    unit_price: Decimal | None = None
    total_price: Decimal | None = None  # negative for discounts
    confidence: float = Field(default=1.0, ge=0, le=1)


class ReceiptExtraction(BaseModel):
    """What the provider claims to have seen. Facts only — may be wrong,
    which is why deterministic validation scores it afterwards."""

    retailer_hint: str | None = None
    store_hint: str | None = None
    purchase_date: date | None = None
    total_amount: Decimal | None = None
    lines: list[ReceiptLineExtraction] = Field(default_factory=list)
    raw_text: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class OCRProviderError(Exception):
    """Provider failed or returned unusable output — maps to HTTP 502."""


class OCRProvider(Protocol):
    def extract(self, image: bytes, content_type: str) -> ReceiptExtraction: ...
