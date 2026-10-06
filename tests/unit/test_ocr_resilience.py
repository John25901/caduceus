from __future__ import annotations

import io

import pytest
from PIL import Image, features

from backend.app.ingestion.document_parser import UniversalEquipmentParser
from backend.app.ingestion.errors import IngestionError
from backend.app.ingestion.ocr_service import OCRReadResult, OCRStatus
from backend.app.llm.vision_extractor import VisionExtractionOutcome
from backend.app.models.domain import EquipmentItem
from backend.app.normalization.text import normalize_search_text


class _FakeOCR:
    def status(self):
        return OCRStatus(True, "fake", "fake", ("fra", "eng"))

    def read_best(self, image):
        return OCRReadResult(
            text="1 Industrial pump 2 pcs 150 300",
            confidence=78.0,
            strategy="enhanced",
            psm=6,
            token_count=7,
        )


def _image_bytes(fmt: str, size=(900, 500)) -> bytes:
    image = Image.new("RGB", size, "white")
    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue()


def test_webp_enters_ocr_pipeline_when_decoder_is_available():
    if not features.check("webp"):
        pytest.skip("Pillow build without WEBP")
    parser = UniversalEquipmentParser()
    parser.ocr = _FakeOCR()
    parsed = parser.parse_bytes(_image_bytes("WEBP"), "supplier.webp")
    assert parsed.source_type == "IMAGE"
    assert parsed.items[0].designation_source == "Industrial pump"
    assert parsed.items[0].unite == "pcs"


def test_low_resolution_image_returns_structured_error():
    parser = UniversalEquipmentParser()
    parser.ocr = _FakeOCR()
    with pytest.raises(IngestionError) as exc:
        parser.parse_bytes(_image_bytes("PNG", size=(120, 80)), "tiny.png")
    assert exc.value.code == "IMAGE_RESOLUTION_TROP_FAIBLE"
    assert exc.value.title == "Résolution insuffisante"


def test_corrupt_webp_returns_friendly_ingestion_error():
    parser = UniversalEquipmentParser()
    parser.ocr = _FakeOCR()
    with pytest.raises(IngestionError) as exc:
        parser.parse_bytes(b"not-a-real-webp", "broken.webp")
    assert exc.value.code in {"IMAGE_ILLISIBLE", "WEBP_NON_SUPPORTE"}



class _DirectoryOCR:
    def status(self):
        return OCRStatus(True, "fake", "fake", ("fra", "eng"))

    def read_best(self, image):
        return OCRReadResult(
            text=(
                "RAISON SOCIALE STE COMPTOIR AGRICOLE\n"
                "ADRESSE RUE JABIR BEN HAYANE\n"
                "TEL 0524434109 FAX 0524434614\n"
                "RAISON SOCIALE STE AGRODEP\n"
                "ADRESSE MARRAKECH\n"
                "TEL 0524420252 FAX 0524430535"
            ),
            confidence=74.0,
            strategy="enhanced",
            psm=6,
            token_count=28,
        )


def test_preview_can_inspect_non_equipment_image_without_fabricating_items():
    parser = UniversalEquipmentParser()
    parser.ocr = _DirectoryOCR()
    parsed = parser.parse_bytes(_image_bytes("PNG"), "directory.png", inspection_only=True)
    assert parsed.items == []
    assert parsed.document_kind == "DIRECTORY_CONTACTS"
    assert parsed.ocr_confidence == 74.0


def test_processing_rejects_non_equipment_image_with_business_error():
    parser = UniversalEquipmentParser()
    parser.ocr = _DirectoryOCR()
    with pytest.raises(IngestionError) as exc:
        parser.parse_bytes(_image_bytes("PNG"), "directory.png")
    assert exc.value.code == "DOCUMENT_HORS_PERIMETRE"



class _WeakTableOCR:
    def status(self):
        return OCRStatus(True, "fake", "fake", ("fra", "eng"))

    def read_best(self, image):
        return OCRReadResult(
            text=(
                "Designation Quantite Prix unitaire Montant\n"
                "Tamis 500 2 000\n"
                "Grande Bassine 6 000 12 000\n"
                "TOTAL 14 000"
            ),
            confidence=82.0,
            strategy="gentle",
            psm=11,
            token_count=16,
            line_count=4,
            low_confidence_ratio=0.08,
        )


class _FakeVisionExtractor:
    configured = True

    def status(self):
        return {"provider": "NVIDIA", "model": "test-vlm", "configured": True}

    def extract(self, **kwargs):
        def item(name, q, pu, total):
            return EquipmentItem(
                source_document=kwargs["filename"],
                source_page=1,
                extraction_method="AI_VISION_NVIDIA",
                designation_source=name,
                designation_normalisee=normalize_search_text(name),
                quantite=q,
                prix_unitaire=pu,
                prix_total=total,
                devise="XAF",
                extraction_confidence=0.94,
            )

        return VisionExtractionOutcome(
            ok=True,
            items=[
                item("Tamis", 4, 500, 2000),
                item("Grande Bassine", 2, 6000, 12000),
            ],
            provider="NVIDIA",
            model="test-vlm",
            latency_ms=120.0,
        )


def test_incomplete_local_ocr_escalates_to_vision_without_interrupting():
    parser = UniversalEquipmentParser(vision_extractor=_FakeVisionExtractor())
    parser.ocr = _WeakTableOCR()
    parsed = parser.parse_bytes(_image_bytes("PNG"), "table.png", inspection_only=True)

    assert parsed.ai_rescue_used is True
    assert parsed.ai_provider == "NVIDIA"
    assert parsed.ai_model == "test-vlm"
    assert len(parsed.items) == 2
    by_name = {item.designation_source: item for item in parsed.items}
    assert by_name["Tamis"].quantite == 4
    assert by_name["Tamis"].prix_unitaire == 500
    assert by_name["Tamis"].prix_total == 2000
