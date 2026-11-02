"""Deterministic audit engines — pure Python, no web framework, no ORM.

Engines receive plain dataclasses and return Finding objects. They are the
only layer allowed to produce financial verdicts; every finding carries
evidence and a French explanation.
"""

from app.engines.billing import audit_billing, audit_quantities
from app.engines.types import BasketEntry, Finding, ReceiptLine

__all__ = ["BasketEntry", "Finding", "ReceiptLine", "audit_billing", "audit_quantities"]
