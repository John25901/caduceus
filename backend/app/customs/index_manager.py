from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.config import Settings
from backend.app.customs.camcis_repository import CamcisRepository


@dataclass
class IndexSyncResult:
    status: str
    semantic_enabled: bool
    collection_name: str | None = None
    camcis_sha256: str | None = None
    embedding_model: str | None = None
    records: int | None = None
    vector_size: int | None = None
    qdrant_points: int | None = None
    build_seconds: float | None = None
    checked_seconds: float | None = None
    reason: str | None = None
    manifest_path: str | None = None

    @property
    def ready(self) -> bool:
        return self.status in {"CURRENT", "REBUILT"} and bool(self.collection_name)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CamcisIndexManager:
    """Durable semantic-index synchronizer for the CAMCIS source of truth.

    The index is a derived cache. A versioned physical Qdrant collection is rebuilt only when
    the CAMCIS SHA-256 or embedding-model identity changes. No manual init step is required.
    """

    MANIFEST_VERSION = 1

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _model_fingerprint(model_name: str) -> str:
        return hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:10]

    def physical_collection_name(self, camcis_sha256: str, model_name: str) -> str:
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", self.settings.qdrant_collection).strip("_") or "camcis"
        return f"{base}_{camcis_sha256[:12]}_{self._model_fingerprint(model_name)}"

    def load_manifest(self) -> dict[str, Any] | None:
        path = self.settings.index_manifest_path
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        path = self.settings.index_manifest_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def manifest_matches(
        cls,
        manifest: dict[str, Any] | None,
        *,
        camcis_sha256: str,
        embedding_model: str,
        expected_records: int,
        expected_collection: str,
    ) -> bool:
        if not manifest:
            return False
        return (
            manifest.get("manifest_version") == cls.MANIFEST_VERSION
            and manifest.get("camcis_sha256") == camcis_sha256
            and manifest.get("embedding_model") == embedding_model
            and int(manifest.get("records", -1)) == int(expected_records)
            and manifest.get("collection_name") == expected_collection
        )

    def ensure_current(self, repo: CamcisRepository, force: bool = False) -> IndexSyncResult:
        started = time.perf_counter()
        records = repo.load()
        camcis_hash = repo.sha256
        model_name = self.settings.embedding_model
        collection = self.physical_collection_name(camcis_hash, model_name)

        if not self.settings.enable_semantic:
            return IndexSyncResult(
                status="DISABLED",
                semantic_enabled=False,
                camcis_sha256=camcis_hash,
                embedding_model=model_name,
                records=len(records),
                checked_seconds=round(time.perf_counter() - started, 3),
                reason="Recherche sémantique désactivée par configuration.",
                manifest_path=str(self.settings.index_manifest_path),
            )

        if not self.settings.auto_sync_index and not force:
            manifest = self.load_manifest()
            return IndexSyncResult(
                status="NOT_SYNCED",
                semantic_enabled=True,
                collection_name=manifest.get("collection_name") if manifest else None,
                camcis_sha256=camcis_hash,
                embedding_model=model_name,
                records=len(records),
                checked_seconds=round(time.perf_counter() - started, 3),
                reason="Auto-synchronisation désactivée.",
                manifest_path=str(self.settings.index_manifest_path),
            )

        client = None
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PointStruct, VectorParams

            self.settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=str(self.settings.qdrant_path))
            collection_names = {c.name for c in client.get_collections().collections}
            manifest = self.load_manifest()

            if not force and self.manifest_matches(
                manifest,
                camcis_sha256=camcis_hash,
                embedding_model=model_name,
                expected_records=len(records),
                expected_collection=collection,
            ) and collection in collection_names:
                count = int(client.count(collection_name=collection, exact=True).count)
                if count == len(records):
                    return IndexSyncResult(
                        status="CURRENT",
                        semantic_enabled=True,
                        collection_name=collection,
                        camcis_sha256=camcis_hash,
                        embedding_model=model_name,
                        records=len(records),
                        vector_size=int(manifest.get("vector_size")) if manifest.get("vector_size") else None,
                        qdrant_points=count,
                        build_seconds=float(manifest.get("build_seconds")) if manifest.get("build_seconds") is not None else None,
                        checked_seconds=round(time.perf_counter() - started, 3),
                        reason="Index CAMCIS déjà synchronisé; aucun embedding recalculé.",
                        manifest_path=str(self.settings.index_manifest_path),
                    )

            # Only load the ML model if a rebuild is actually necessary.
            from sentence_transformers import SentenceTransformer

            model_started = time.perf_counter()
            model = SentenceTransformer(model_name)
            vector_size = int(model.get_sentence_embedding_dimension() or 0)
            if vector_size <= 0:
                probe = model.encode(["test"], normalize_embeddings=True)
                vector_size = int(probe.shape[1])

            # Versioned collection: a failed rebuild never destroys the previously valid one.
            if collection in collection_names:
                client.delete_collection(collection)
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

            batch_size = max(16, int(self.settings.embedding_batch_size))
            for start_idx in range(0, len(records), batch_size):
                batch = records[start_idx : start_idx + batch_size]
                vectors = model.encode(
                    [r.libelle for r in batch],
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    batch_size=min(batch_size, len(batch)),
                )
                points = [
                    PointStruct(
                        id=start_idx + i,
                        vector=vectors[i].tolist(),
                        payload={
                            "code_sh": r.code_sh,
                            "libelle": r.libelle,
                            "camcis_sha256": camcis_hash,
                            "embedding_model": model_name,
                        },
                    )
                    for i, r in enumerate(batch)
                ]
                client.upsert(collection_name=collection, points=points)

            count = int(client.count(collection_name=collection, exact=True).count)
            if count != len(records):
                raise RuntimeError(f"Index incomplet: {count} points pour {len(records)} positions CAMCIS.")

            build_seconds = round(time.perf_counter() - model_started, 3)
            manifest_payload = {
                "manifest_version": self.MANIFEST_VERSION,
                "indexed_at_utc": datetime.now(timezone.utc).isoformat(),
                "camcis_sha256": camcis_hash,
                "source_file": repo.path.name,
                "records": len(records),
                "embedding_model": model_name,
                "vector_size": vector_size,
                "collection_name": collection,
                "qdrant_points": count,
                "build_seconds": build_seconds,
            }
            self._write_manifest(manifest_payload)

            if not self.settings.keep_old_indexes:
                for old_name in list(collection_names):
                    if old_name.startswith(f"{self.settings.qdrant_collection}_") and old_name != collection:
                        try:
                            client.delete_collection(old_name)
                        except Exception:
                            pass

            return IndexSyncResult(
                status="REBUILT",
                semantic_enabled=True,
                collection_name=collection,
                camcis_sha256=camcis_hash,
                embedding_model=model_name,
                records=len(records),
                vector_size=vector_size,
                qdrant_points=count,
                build_seconds=build_seconds,
                checked_seconds=round(time.perf_counter() - started, 3),
                reason="Index CAMCIS reconstruit car la source, le modèle ou l'état Qdrant avait changé.",
                manifest_path=str(self.settings.index_manifest_path),
            )
        except Exception as exc:
            return IndexSyncResult(
                status="ERROR",
                semantic_enabled=True,
                collection_name=None,
                camcis_sha256=camcis_hash,
                embedding_model=model_name,
                records=len(records),
                checked_seconds=round(time.perf_counter() - started, 3),
                reason=f"Synchronisation sémantique impossible: {exc}",
                manifest_path=str(self.settings.index_manifest_path),
            )
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
