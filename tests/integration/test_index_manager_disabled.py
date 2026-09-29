from dataclasses import replace

from backend.app.core.config import settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.index_manager import CamcisIndexManager


def test_index_manager_can_boot_without_semantic_dependencies(tmp_path):
    cfg = replace(
        settings,
        enable_semantic=False,
        qdrant_path=tmp_path / "qdrant",
        index_manifest_path=tmp_path / "manifest.json",
    )
    repo = CamcisRepository(cfg.camcis_path)
    result = CamcisIndexManager(cfg).ensure_current(repo)
    assert result.status == "DISABLED"
    assert result.records == len(repo.load())
