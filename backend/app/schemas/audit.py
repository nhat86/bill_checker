import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AuditSessionCreate(BaseModel):
    pass


class AuditSessionOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BasketItemIn(BaseModel):
    label: str | None = None
    ean: str | None = None
    quantity: Decimal = Decimal(1)
    user_confirmed: bool = False


class BasketItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    label: str | None
    ean: str | None
    quantity: Decimal
    confidence: Decimal | None
    user_confirmed: bool

    model_config = {"from_attributes": True}


class ReceiptItemIn(BaseModel):
    description: str = Field(max_length=255)
    ean: str | None = None
    quantity: Decimal = Decimal(1)
    unit_price: Decimal | None = None
    total_price: Decimal | None = None


class ReceiptItemOut(ReceiptItemIn):
    id: uuid.UUID
    line_confidence: Decimal | None

    model_config = {"from_attributes": True}


class ReceiptOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    retailer_id: uuid.UUID | None
    store_id: uuid.UUID | None
    purchase_date: date | None
    total_amount: Decimal | None
    parse_confidence: Decimal | None
    user_confirmed: bool
    items: list[ReceiptItemOut] = []

    model_config = {"from_attributes": True}


class AuditSessionDetailOut(AuditSessionOut):
    basket_items: list[BasketItemOut] = []
    receipts: list[ReceiptOut] = []
