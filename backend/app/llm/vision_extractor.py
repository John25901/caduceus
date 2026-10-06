from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.core.config import Settings
from backend.app.llm.providers import OpenAICompatibleChatProvider, ProviderConfig
from backend.app.models.domain import EquipmentItem
from backend.app.normalization.text import normalize_search_text


@dataclass
class VisionExtractionOutcome:
    ok: bool
    items: list[EquipmentItem]
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


def _num(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace(" ", "")
    if not text:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(",", "")
    try:
        return float(text)
    except Exception:
        return None


def _total_like(text: str) -> bool:
    n = normalize_search_text(text or "")
    return n.startswith(("total", "grand total", "subtotal", "sous total"))


def _arith_ok(qty: float | None, unit_price: float | None, total: float | None) -> bool | None:
    if qty is None or unit_price is None or total is None:
        return None
    tolerance = max(1.0, abs(total) * 0.015)
    return abs((qty * unit_price) - total) <= tolerance


class ControlledVisionExtractor:
    """Multimodal rescue extractor with deterministic post-validation.

    Local OCR remains the primary extractor. This service is invoked only when
    the caller decides the local structural result is incomplete. It cannot
    create tariff codes and missing cells must remain null.
    """

    def __init__(self, settings: Settings, provider: OpenAICompatibleChatProvider | None = None):
        self.settings = settings
        requested = (settings.ai_vision_provider or "NVIDIA").strip().upper()
        self.provider_name = requested if requested in {"NVIDIA", "OPENAI"} else "NVIDIA"

        if provider is not None:
            self.provider = provider
        elif self.provider_name == "OPENAI":
            self.provider = OpenAICompatibleChatProvider(
                ProviderConfig(
                    name="OPENAI",
                    model=settings.openai_vision_model,
                    base_url=settings.openai_base_url,
                    api_key=settings.openai_api_key,
                    max_tokens_field="max_completion_tokens",
                ),
                timeout_seconds=settings.ai_vision_timeout_seconds,
            )
        else:
            self.provider = OpenAICompatibleChatProvider(
                ProviderConfig(
                    name="NVIDIA",
                    model=settings.nvidia_vision_model,
                    base_url=settings.nvidia_base_url,
                    api_key=settings.nvidia_api_key,
                    max_tokens_field="max_tokens",
                ),
                timeout_seconds=settings.ai_vision_timeout_seconds,
            )

    @property
    def configured(self) -> bool:
        return bool(self.settings.enable_ai_vision and self.provider.config.configured)

    def status(self) -> dict[str, Any]:
        base = self.provider.status()
        base["enabled"] = self.settings.enable_ai_vision
        base["configured"] = self.configured
        base["purpose"] = "vision_document_rescue"
        return base

    @staticmethod
    def _mime_type(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp",
        }.get(ext, "image/png")

    def extract(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        local_ocr_text: str,
        document_label: str = "",
    ) -> VisionExtractionOutcome:
        if not self.configured:
            return VisionExtractionOutcome(ok=False, items=[], error="IA vision non configurée.")

        system = (
            "Tu es un moteur d'extraction documentaire pour une application douanière. "
            "Ta tâche est UNIQUEMENT de retranscrire les lignes commerciales visibles dans l'image. "
            "N'invente aucune valeur illisible. Ne complète aucun code SH. "
            "Exclus les lignes TOTAL, SOUS TOTAL, GRAND TOTAL et les paragraphes narratifs. "
            "Retourne uniquement un JSON strict avec les clés document_type, currency, rows. "
            "rows est une liste d'objets avec exactement: designation, specifications, quantity, unit, "
            "unit_price, total, origin, confidence. Les nombres doivent être des nombres JSON sans séparateur "
            "de milliers. Les cellules absentes ou ambiguës valent null. "
            "Si quantity, unit_price et total sont présents, vérifie mentalement quantity*unit_price=total; "
            "si la relation ne tient pas, mets les champs numériques ambigus à null plutôt que de deviner."
        )
        user = (
            f"Nom du fichier: {filename}\n"
            f"Type local estimé: {document_label or 'inconnu'}\n"
            "Transcription OCR locale (peut être incomplète ou mal alignée):\n"
            f"{(local_ocr_text or '')[:7000]}\n\n"
            "Relis directement l'image et reconstruis le tableau commercial visible."
        )

        response = self.provider.complete_multimodal_json(
            system_prompt=system,
            user_prompt=user,
            image_bytes=image_bytes,
            mime_type=self._mime_type(filename),
            temperature=0.0,
            max_tokens=1800,
        )
        if not response.ok:
            return VisionExtractionOutcome(
                ok=False,
                items=[],
                provider=self.provider_name,
                model=self.provider.config.model,
                latency_ms=response.latency_ms,
                error=response.error,
            )

        try:
            data = self.provider.parse_json(response.content)
        except Exception as exc:
            return VisionExtractionOutcome(
                ok=False,
                items=[],
                provider=self.provider_name,
                model=self.provider.config.model,
                latency_ms=response.latency_ms,
                error=f"JSON IA invalide: {exc}",
            )

        currency = str(data.get("currency") or "").strip() or None
        rows = data.get("rows")
        if not isinstance(rows, list):
            rows = []

        items: list[EquipmentItem] = []
        for idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            designation = " ".join(str(row.get("designation") or "").split()).strip()
            if len(designation) < 2 or _total_like(designation):
                continue

            qty = _num(row.get("quantity"))
            unit_price = _num(row.get("unit_price"))
            total = _num(row.get("total"))
            arith = _arith_ok(qty, unit_price, total)

            # Never accept a complete but internally inconsistent numeric triplet.
            # Keep the designation and remove the uncertain monetary interpretation.
            if arith is False:
                qty = None
                unit_price = None
                total = None

            try:
                confidence = float(row.get("confidence"))
            except Exception:
                confidence = 0.72
            confidence = max(0.0, min(0.95, confidence))

            items.append(
                EquipmentItem(
                    source_document=filename,
                    source_page=1,
                    source_row=idx,
                    extraction_method=f"AI_VISION_{self.provider_name}",
                    designation_source=designation,
                    designation_normalisee=normalize_search_text(designation),
                    specifications=" ".join(str(row.get("specifications") or "").split()).strip() or None,
                    quantite=qty,
                    unite=" ".join(str(row.get("unit") or "").split()).strip() or None,
                    prix_unitaire=unit_price,
                    prix_total=total,
                    devise=currency,
                    origine=" ".join(str(row.get("origin") or "").split()).strip() or None,
                    extraction_confidence=confidence,
                    raw_fields={
                        "ai_vision_rescue": True,
                        "provider": self.provider_name,
                        "model": self.provider.config.model,
                        "arithmetic_check": arith,
                    },
                )
            )

        return VisionExtractionOutcome(
            ok=bool(items),
            items=items,
            provider=self.provider_name,
            model=self.provider.config.model,
            latency_ms=response.latency_ms,
            error=None if items else "Aucune ligne commerciale fiable retournée par l'IA vision.",
            raw=data,
        )
