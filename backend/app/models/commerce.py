import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import JSONBVariant, Timestamped, UUIDPrimaryKey


class Retailer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "retailers"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)

    stores: Mapped[list["Store"]] = relationship(back_populates="retailer")


class Store(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "stores"

    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120))
    postcode: Mapped[str | None] = mapped_column(String(10), index=True)
    external_ref: Mapped[str | None] = mapped_column(String(120))

    retailer: Mapped[Retailer] = relationship(back_populates="stores")


class Product(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "products"

    ean: Mapped[str | None] = mapped_column(String(14), index=True)
    retailer_sku: Mapped[str | None] = mapped_column(String(60), index=True)
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("retailers.id"), index=True)
    brand: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(255))
    size: Mapped[str | None] = mapped_column(String(60))
    variant: Mapped[str | None] = mapped_column(String(120))
    is_multipack: Mapped[bool] = mapped_column(default=False)
    units_per_pack: Mapped[int | None] = mapped_column()
    attributes: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
