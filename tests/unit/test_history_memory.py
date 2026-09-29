from pathlib import Path

from backend.app.core.config import Settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.search_engine import HybridTariffEngine

ROOT = Path(__file__).resolve().parents[2]


def test_validated_memory_recovers_known_netic_case():
    settings = Settings(
        camcis_path=ROOT / "data" / "reference" / "Code_SH_CAMCIS.xlsx",
        validated_cases_path=ROOT / "data" / "validated_cases",
        enable_semantic=False,
    )
    repo = CamcisRepository(settings.camcis_path)
    engine = HybridTariffEngine(repo, settings)
    hits = engine.search("Solar Cell A Type TOPCON 182.2X183.75mm 16BB 24.9%", top_k=3)
    assert hits
    assert hits[0].code_sh == "85414200000"
    assert hits[0].history_score is not None
