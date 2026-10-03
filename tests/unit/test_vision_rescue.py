from pathlib import Path

from backend.app.core.config import Settings
from backend.app.llm.providers import OpenAICompatibleChatProvider, ProviderConfig, ProviderResponse
from backend.app.llm.vision_extractor import ControlledVisionExtractor


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        nvidia_api_key="test-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        nvidia_vision_model="deepseek-ai/deepseek-v4.1-flash",
        enable_ai_vision=True,
        ai_vision_provider="NVIDIA",
        ai_vision_timeout_seconds=10,
    )


def test_vision_extractor_keeps_only_supported_visible_values(tmp_path):
    settings = _settings(tmp_path)
    provider = OpenAICompatibleChatProvider(
        ProviderConfig(
            name="NVIDIA",
            model=settings.nvidia_vision_model,
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
        )
    )
    provider.complete_multimodal_json = lambda **kwargs: ProviderResponse(
        ok=True,
        content="""{
          "document_type": "commercial_table",
          "currency": "XAF",
          "rows": [
            {"designation":"Grande poubelle","specifications":null,"quantity":3,"unit":null,"unit_price":28000,"total":84000,"origin":null,"confidence":0.94},
            {"designation":"TOTAL","specifications":null,"quantity":null,"unit":null,"unit_price":null,"total":420000,"origin":null,"confidence":0.99},
            {"designation":"Bac pour fruit","specifications":null,"quantity":6,"unit":null,"unit_price":6500,"total":39001,"origin":null,"confidence":0.90}
          ]
        }""",
    )

    extractor = ControlledVisionExtractor(settings, provider=provider)
    out = extractor.extract(
        image_bytes=b"fake-image",
        filename="table.png",
        local_ocr_text="Designation Quantite Prix unitaire Montant",
        document_label="Proforma",
    )

    assert out.ok is True
    assert len(out.items) == 2
    assert out.items[0].designation_source == "Grande poubelle"
    assert out.items[0].quantite == 3
    assert out.items[0].prix_unitaire == 28000
    assert out.items[0].prix_total == 84000

    # Inconsistent values are not silently trusted.
    assert out.items[1].designation_source == "Bac pour fruit"
    assert out.items[1].quantite is None
    assert out.items[1].prix_unitaire is None
    assert out.items[1].prix_total is None


def test_vision_extractor_is_inert_without_api_key(tmp_path):
    settings = Settings(
        nvidia_api_key="",
        nvidia_vision_model="deepseek-ai/deepseek-v4.1-flash",
        enable_ai_vision=True,
        ai_vision_provider="NVIDIA",
    )
    extractor = ControlledVisionExtractor(settings)
    assert extractor.configured is False
    out = extractor.extract(
        image_bytes=b"fake",
        filename="table.png",
        local_ocr_text="",
    )
    assert out.ok is False
    assert out.items == []
