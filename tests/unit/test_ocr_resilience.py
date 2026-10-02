from __future__ import annotations

import io

import pytest
from PIL import Image, features

from backend.app.ingestion.document_parser import UniversalEquipmentParser
from backend.app.ingestion.errors import IngestionError
from backend.app.ingestion.ocr_service import OCRReadResult, OCRStatus


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
