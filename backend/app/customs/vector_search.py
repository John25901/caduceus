from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.customs.camcis_repository import CamcisRecord


@dataclass(frozen=True)
class VectorHit:
    record: CamcisRecord
    score: float


class OptionalVectorTariffSearch:
    """Lazy semantic search over a pre-synchronized local Qdrant collection."""

    def __init__(self, records_by_code: dict[str, CamcisRecord], storage_path: Path, collection: str | None, model_name: str):
        self.records_by_code = records_by_code
        self.storage_path = storage_path
        self.collection = collection
        self.model_name = model_name
        self.available = False
        self.reason_unavailable: str | None = None
        self._client = None
        self._model = None
        self._init()

    def _init(self) -> None:
        if not self.collection:
            self.reason_unavailable = "Aucune collection sémantique synchronisée"
            return
        try:
            from qdrant_client import QdrantClient
            from sentence_transformers import SentenceTransformer

            self._client = QdrantClient(path=str(self.storage_path))
            collections = {c.name for c in self._client.get_collections().collections}
            if self.collection not in collections:
                self.reason_unavailable = f"Collection Qdrant absente: {self.collection}"
                self.close()
                return
            self._model = SentenceTransformer(self.model_name)
            self.available = True
        except Exception as exc:
            self.reason_unavailable = str(exc)
            self.available = False
            self.close()

    def search(self, query: str, limit: int = 20) -> list[VectorHit]:
        if not self.available or self._client is None or self._model is None or not self.collection:
            return []
        vector = self._model.encode(query, normalize_embeddings=True).tolist()
        if hasattr(self._client, "query_points"):
            result = self._client.query_points(collection_name=self.collection, query=vector, limit=limit)
            points = result.points
        else:
            points = self._client.search(collection_name=self.collection, query_vector=vector, limit=limit)
        hits: list[VectorHit] = []
        for p in points:
            payload = p.payload or {}
            code = str(payload.get("code_sh", ""))
            rec = self.records_by_code.get(code)
            if rec is not None:
                hits.append(VectorHit(record=rec, score=float(p.score)))
        return hits

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._model = None
        self.available = False
