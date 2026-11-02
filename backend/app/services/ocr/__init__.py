"""OCR providers — extraction only, never verdicts.

A provider takes image bytes and returns ReceiptExtraction: the *facts* it
saw (lines, prices, totals, raw text). Deterministic code downstream
validates the arithmetic and decides confidence.
"""

from app.services.ocr.types import OCRProvider, OCRProviderError, ReceiptExtraction, ReceiptLineExtraction


def get_ocr_provider() -> OCRProvider:
    """Provider factory — Depends()-injectable so tests can override it."""
    from app.core.config import settings

    if settings.ocr_backend == "fixture":
        from app.services.ocr.fixture import FixtureOCRProvider

        return FixtureOCRProvider()
    from app.services.ocr.groq_provider import GroqVisionOCRProvider

    return GroqVisionOCRProvider()


__all__ = [
    "OCRProvider",
    "OCRProviderError",
    "ReceiptExtraction",
    "ReceiptLineExtraction",
    "get_ocr_provider",
]
