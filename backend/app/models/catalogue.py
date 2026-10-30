import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import JSONBVariant, Timestamped, UUIDPrimaryKey

PROMOTION_TYPES = (
    "IMMEDIATE_DISCOUNT",
    "PERCENTAGE_DISCOUNT",
    "BUY_X_GET_Y_FREE",
    "SECOND_ITEM_DISCOUNT",
    "MULTIBUY_BUNDLE",
    "LOYALTY_DISCOUNT",
    "COUPON",
    "DEFERRED_CASHBACK",
    "MULTI_PRODUCT_PROMOTION",
)


class Catalogue(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "catalogues"

    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stores.id"), index=True)
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_to: Mapped[date] = mapped_column(Date, index=True)
    version: Mapped[str | None] = mapped_column(String(60))

    sources: Mapped[list["CatalogueSource"]] = relationship(back_populates="catalogue")


class CatalogueSource(UUIDPrimaryKey, Base):
    __tablename__ = "catalogue_sources"

    catalogue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalogues.id"), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_type: Mapped[str] = mapped_column(String(20))  # pdf | html | image | fixture
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_ref: Mapped[str | None] = mapped_column(String(512))  # object-storage key

    catalogue: Mapped[Catalogue] = relationship(back_populates="sources")


class Promotion(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "promotions"

    catalogue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("catalogues.id"), index=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id"), index=True)
    promo_type: Mapped[str] = mapped_column(
        Enum(*PROMOTION_TYPES, name="promotion_type", native_enum=False)
    )
    title: Mapped[str | None] = mapped_column(String(255))
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_to: Mapped[date] = mapped_column(Date, index=True)
    store_scope: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    conditions: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    discount_formula: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    max_discount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    combination_rules: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    source_evidence: Mapped[dict] = mapped_column(JSONBVariant, default=dict)

    products: Mapped[list["PromotionProduct"]] = relationship(back_populates="promotion")


class PromotionProduct(UUIDPrimaryKey, Base):
    __tablename__ = "promotion_products"

    promotion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promotions.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="qualifying")  # qualifying | bonus

    promotion: Mapped[Promotion] = relationship(back_populates="products")


class PromotionEligibility(UUIDPrimaryKey, Base):
    __tablename__ = "promotion_eligibility"

    promotion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promotions.id"), index=True)
    requirement_type: Mapped[str] = mapped_column(String(40))  # loyalty_card | coupon | min_quantity
    params: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
