from pathlib import Path

from backend.app.customs.camcis_repository import CamcisRepository

CAMCIS = Path(__file__).resolve().parents[2] / "data" / "reference" / "Code_SH_CAMCIS.xlsx"


def test_camcis_loads_expected_scale_and_known_code():
    repo = CamcisRepository(CAMCIS)
    records = repo.load()
    assert len(records) >= 6800
    known = repo.get("84414000000")
    assert known is not None
    assert "papier" in known.libelle.lower() or "carton" in known.libelle.lower()
