"""Plain data types for engines — deliberately NOT ORM objects.

The runner maps DB rows → these types → engines → Findings → DB rows.
Engines stay pure: same input, same findings, no side effects.
"""

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


def normalize(text: str) -> str:
    """Match key for receipt descriptions vs basket labels:
    lowercase, no accents, collapsed spaces. 'LAIT DEMI-ÉCRÉMÉ' ~ 'lait demi ecreme'."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


@dataclass
class BasketEntry:
    """What the user actually bought (ground-truth side)."""

    key: str  # match key: EAN if known else normalized label
    label: str
    quantity: Decimal
    user_confirmed: bool
    product_id: str | None = None


@dataclass
class ReceiptLine:
    """One charged line (claim side)."""

    key: str
    description: str
    quantity: Decimal
    unit_price: Decimal | None
    total_price: Decimal | None
    ean: str | None = None


@dataclass
class Finding:
    """Engine verdict — evidence and explanation are mandatory."""

    finding_type: str
    status: str  # CONFIRMED | POTENTIAL | NEEDS_CONFIRMATION | UNVERIFIABLE | ...
    product_name: str
    expected_amount: Decimal | None = None
    actual_amount: Decimal | None = None
    difference: Decimal | None = None
    confidence: Decimal = Decimal("0.5")
    evidence: dict[str, Any] = field(default_factory=dict)
    explanation_fr: str = ""
    product_id: str | None = None
    is_deferred: bool = False
