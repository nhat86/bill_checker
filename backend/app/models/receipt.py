import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import JSONBVariant, Timestamped, UUIDPrimaryKey, utcnow

SESSION_STATUSES = (
    "DRAFT",
    "PRODUCTS_CAPTURED",
    "RECEIPT_UPLOADED",
    "AUDITING",
    "COMPLETED",
    "FAILED",
)

FINDING_STATUSES = (
    "APPLIED",
    "NOT_APPLIED",
    "PARTIALLY_APPLIED",
    "NOT_ELIGIBLE",
    "NEEDS_CONFIRMATION",
    "UNVERIFIABLE",
    "CONFIRMED",
    "POTENTIAL",
)


class AuditSession(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "audit_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(
        Enum(*SESSION_STATUSES, name="session_status", native_enum=False), default="DRAFT"
    )

    basket_items: Mapped[list["BasketItem"]] = relationship(back_populates="session")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="session")
    findings: Mapped[list["AuditFinding"]] = relationship(back_populates="session")


class BasketItem(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "basket_items"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_sessions.id"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    label: Mapped[str | None] = mapped_column(String(255))
    ean: Mapped[str | None] = mapped_column(String(14), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), default=1)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    user_confirmed: Mapped[bool] = mapped_column(default=False)
    image_ref: Mapped[str | None] = mapped_column(String(512))
    recognition_evidence: Mapped[dict] = mapped_column(JSONBVariant, default=dict)

    session: Mapped[AuditSession] = relationship(back_populates="basket_items")


class Receipt(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "receipts"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_sessions.id"), index=True)
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("retailers.id"))
    store_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stores.id"))
    purchase_date: Mapped[date | None] = mapped_column(Date, index=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    image_ref: Mapped[str | None] = mapped_column(String(512))
    raw_ocr_text: Mapped[str | None] = mapped_column(Text)
    parse_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    user_confirmed: Mapped[bool] = mapped_column(default=False)

    session: Mapped[AuditSession] = relationship(back_populates="receipts")
    # delete-orphan: children exist only inside their receipt — replacing the
    # collection deletes the old rows (keeps ORM state and DB in sync)
    items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )
    discounts: Mapped[list["ReceiptDiscount"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class ReceiptItem(UUIDPrimaryKey, Base):
    __tablename__ = "receipt_items"

    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receipts.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    ean: Mapped[str | None] = mapped_column(String(14), index=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), default=1)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    total_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    line_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))

    receipt: Mapped[Receipt] = relationship(back_populates="items")


class ReceiptDiscount(UUIDPrimaryKey, Base):
    __tablename__ = "receipt_discounts"

    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receipts.id"), index=True)
    receipt_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("receipt_items.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    discount_type: Mapped[str | None] = mapped_column(String(40))

    receipt: Mapped[Receipt] = relationship(back_populates="discounts")


class AuditFinding(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "audit_findings"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_sessions.id"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    finding_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(
        Enum(*FINDING_STATUSES, name="finding_status", native_enum=False)
    )
    product_name: Mapped[str | None] = mapped_column(String(255))
    expected_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    actual_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    difference: Mapped[float | None] = mapped_column(Numeric(10, 2))
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    evidence: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    explanation_fr: Mapped[str | None] = mapped_column(Text)
    # deferred cashback is separated from immediate savings
    is_deferred: Mapped[bool] = mapped_column(default=False)

    session: Mapped[AuditSession] = relationship(back_populates="findings")


class AuditEvent(UUIDPrimaryKey, Base):
    __tablename__ = "audit_events"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_sessions.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
