from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.app.audit.store import AuditStore
from backend.app.core.config import Settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.history_repository import ValidatedCaseMemory
from backend.app.customs.index_manager import CamcisIndexManager, IndexSyncResult
from backend.app.customs.search_engine import HybridTariffEngine
from backend.app.metrics.store import MetricsStore
from backend.app.llm.arbitrator import ControlledTariffArbitrator


def migrate_legacy_runtime_if_needed(settings: Settings) -> dict:
    """One-time migration from V2.1 project-local runtime into persistent CADUCEUS_HOME.

    This allows an existing workstation to upgrade without rebuilding CAMCIS or losing
    metrics/audit merely because the source code was replaced.
    """
    migrated: list[str] = []
    legacy_qdrant = settings.project_root / "data" / "qdrant_storage"
    try:
        has_legacy_qdrant = legacy_qdrant.exists() and any(p.name != ".gitkeep" for p in legacy_qdrant.iterdir())
    except Exception:
        has_legacy_qdrant = False
    try:
        has_new_qdrant = settings.qdrant_path.exists() and any(settings.qdrant_path.iterdir())
    except Exception:
        has_new_qdrant = False
    if has_legacy_qdrant and not has_new_qdrant and legacy_qdrant.resolve() != settings.qdrant_path.resolve():
        settings.qdrant_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(legacy_qdrant, settings.qdrant_path, dirs_exist_ok=True)
        migrated.append("qdrant_storage")

    legacy_runtime = settings.project_root / "data" / "runtime"
    targets = {
        "camcis_index_manifest.json": settings.index_manifest_path,
        "reference_state.json": settings.reference_state_path,
        "caduceus_metrics.db": settings.metrics_db_path,
        "caduceus_audit.db": settings.audit_db_path,
    }
    for filename, target in targets.items():
        source = legacy_runtime / filename
        if source.exists() and not target.exists() and source.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            migrated.append(filename)
    return {"migrated": migrated, "app_data_root": str(settings.app_data_root)}


@dataclass
class RuntimeServices:
    repo: CamcisRepository
    engine: HybridTariffEngine
    audit: AuditStore
    metrics: MetricsStore
    index_sync: IndexSyncResult
    reference_state: dict
    arbitrator: ControlledTariffArbitrator


def write_reference_state(settings: Settings, repo: CamcisRepository, index_sync: IndexSyncResult, history_stats: dict) -> dict:
    payload = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "camcis": repo.stats(),
        "validated_memory": history_stats,
        "semantic_index": index_sync.as_dict(),
    }
    path = settings.reference_state_path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return payload


def synchronize_references(settings: Settings, force_index: bool = False) -> tuple[CamcisRepository, IndexSyncResult, dict, dict]:
    migrate_legacy_runtime_if_needed(settings)
    repo = CamcisRepository(settings.camcis_path)
    repo.load()  # fatal if the official reference is absent or invalid
    index_sync = CamcisIndexManager(settings).ensure_current(repo, force=force_index)
    history = ValidatedCaseMemory(settings.validated_cases_path, settings.user_validated_cases_path)
    history_stats = history.stats()
    state = write_reference_state(settings, repo, index_sync, history_stats)
    return repo, index_sync, history_stats, state


def build_runtime_services(settings: Settings) -> RuntimeServices:
    metrics = MetricsStore(settings.metrics_db_path)
    repo, index_sync, _, state = synchronize_references(settings)
    engine = HybridTariffEngine(
        repo,
        settings,
        use_history=True,
        semantic_collection=index_sync.collection_name if index_sync.ready else None,
    )
    audit = AuditStore(settings.audit_db_path)
    arbitrator = ControlledTariffArbitrator(settings)
    return RuntimeServices(
        repo=repo,
        engine=engine,
        audit=audit,
        metrics=metrics,
        index_sync=index_sync,
        reference_state=state,
        arbitrator=arbitrator,
    )
