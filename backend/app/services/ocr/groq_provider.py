"""Groq vision provider — LLM reads the receipt, returns strict JSON.

The prompt forbids invention: null for unreadable fields. The output is
validated by Pydantic AND later by deterministic arithmetic checks — a
misreading LLM is caught, not trusted.
"""

import base64
import json

from app.core.config import settings
from app.services.ocr.types import OCRProviderError, ReceiptExtraction

EXTRACTION_PROMPT = """Tu lis une photo de ticket de caisse français (supermarché).
Extrais STRICTEMENT ce JSON, rien d'autre:

{
  "retailer_hint": "nom de l'enseigne ou null",
  "store_hint": "ville/magasin ou null",
  "purchase_date": "YYYY-MM-DD ou null",
  "total_amount": nombre décimal ou null,
  "lines": [
    {
      "description": "texte exact de la ligne",
      "kind": "item" ou "discount",
      "ean": "code barre ou null",
      "quantity": nombre,
      "unit_price": nombre ou null,
      "total_price": nombre (négatif pour une remise) ou null,
      "confidence": 0.0 à 1.0
    }
  ],
  "raw_text": "texte intégral du ticket, mot à mot",
  "confidence": 0.0 à 1.0
}

Règles impératives:
- N'INVENTE RIEN. Si un champ est illisible, mets null.
- "kind" = "discount" pour remises, promotions, fidélité, coupons.
- Les lignes de remise ont un total_price NÉGATIF.
- Prix en euros (virgule → point). Quantités au poids possibles (ex: 0.350).
- Réponds UNIQUEMENT avec le JSON valide."""


class GroqVisionOCRProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_vision_model

    def extract(self, image: bytes, content_type: str) -> ReceiptExtraction:
        if not self.api_key:
            raise OCRProviderError("GROQ_API_KEY manquante")
        try:
            from groq import Groq

            client = Groq(api_key=self.api_key)
            b64 = base64.b64encode(image).decode()
            resp = client.chat.completions.create(
                model=self.model,
                temperature=0,  # extraction, not creativity
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": EXTRACTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{content_type};base64,{b64}"},
                            },
                        ],
                    }
                ],
            )
            payload = json.loads(resp.choices[0].message.content)
            return ReceiptExtraction.model_validate(payload)
        except OCRProviderError:
            raise
        except Exception as exc:
            raise OCRProviderError(f"Échec OCR: {exc}") from exc
