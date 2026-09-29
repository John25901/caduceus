from __future__ import annotations

import gc
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import psutil

from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.lexical_search import LexicalTariffSearch
from backend.app.ingestion.tabular_parser import TabularEquipmentParser
from backend.app.metrics.store import MetricsStore


@dataclass(frozen=True)
class EvaluationCase:
    dataset: str
    query: str
    expected_code: str


def load_evaluation_cases(paths: Iterable[Path], max_cases: int | None = None) -> list[EvaluationCase]:
    """Load deterministic evaluation cases, stratified across source datasets when capped."""
    parser = TabularEquipmentParser()
    buckets: list[list[EvaluationCase]] = []
    for path in paths:
        parsed = parser.parse_path(path)
        bucket: list[EvaluationCase] = []
        for item in parsed.items:
            if not item.code_sh_source:
                continue
            query = item.designation_source
            if item.specifications:
                query += f". {item.specifications}"
            bucket.append(EvaluationCase(path.stem, query, item.code_sh_source))
        if bucket:
            buckets.append(bucket)

    if not max_cases:
        return [case for bucket in buckets for case in bucket]

    # Round-robin sampling prevents a capped benchmark from being dominated by the first workbook.
    selected: list[EvaluationCase] = []
    positions = [0] * len(buckets)
    while len(selected) < max_cases:
        progressed = False
        for i, bucket in enumerate(buckets):
            if positions[i] < len(bucket):
                selected.append(bucket[positions[i]])
                positions[i] += 1
                progressed = True
                if len(selected) >= max_cases:
                    break
        if not progressed:
            break
    return selected


def compute_ranking_metrics(expected: list[str], rankings: list[list[str]]) -> dict[str, float]:
    if not expected:
        return {"top1_accuracy": 0.0, "top3_recall": 0.0, "top5_recall": 0.0, "mrr": 0.0}
    top1 = top3 = top5 = 0
    rr = 0.0
    for exp, ranked in zip(expected, rankings):
        top1 += bool(ranked and ranked[0] == exp)
        top3 += exp in ranked[:3]
        top5 += exp in ranked[:5]
        try:
            rr += 1.0 / (ranked.index(exp) + 1)
        except ValueError:
            pass
    n = len(expected)
    return {
        "top1_accuracy": top1 / n,
        "top3_recall": top3 / n,
        "top5_recall": top5 / n,
        "mrr": rr / n,
    }


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), 95))


def _rrf_merge(a: list[str], b: list[str], k: int = 60, limit: int = 10) -> list[str]:
    scores: dict[str, float] = {}
    for ranked in (a, b):
        for rank, code in enumerate(ranked, start=1):
            scores[code] = scores.get(code, 0.0) + 1.0 / (k + rank)
    return [code for code, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _model_texts(model_name: str, texts: list[str], query: bool) -> list[str]:
    # multilingual-e5 models are trained with explicit query/passage prefixes.
    if "e5" in model_name.lower():
        prefix = "query: " if query else "passage: "
        return [prefix + t for t in texts]
    return texts


def _model_tag(model_name: str) -> str:
    return hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:12]


class BenchmarkRunner:
    """Explicit, measurable model laboratory. Never runs automatically at application startup."""

    def __init__(self, repo: CamcisRepository, metrics: MetricsStore, cache_path: Path):
        self.repo = repo
        self.metrics = metrics
        self.cache_path = Path(cache_path)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.records = repo.load()
        self.lexical = LexicalTariffSearch(self.records)
        self._code_order = [r.code_sh for r in self.records]

    def _result(
        self,
        *,
        engine_type: str,
        model_name: str | None,
        cases: list[EvaluationCase],
        rankings: list[list[str]],
        latencies_ms: list[float],
        corpus_build_seconds: float | None = None,
        rss_delta_mb: float | None = None,
        details: dict | None = None,
    ) -> dict:
        m = compute_ranking_metrics([c.expected_code for c in cases], rankings)
        datasets = sorted({c.dataset for c in cases})
        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "engine_type": engine_type,
            "model_name": model_name,
            "dataset_name": "+".join(datasets) if datasets else "NONE",
            "cases": len(cases),
            **m,
            "avg_query_ms": round(float(np.mean(latencies_ms)), 3) if latencies_ms else None,
            "p95_query_ms": round(float(_p95(latencies_ms)), 3) if latencies_ms else None,
            "corpus_build_seconds": round(corpus_build_seconds, 3) if corpus_build_seconds is not None else None,
            "rss_delta_mb": round(rss_delta_mb, 3) if rss_delta_mb is not None else None,
            "camcis_sha256": self.repo.sha256,
            "details": details or {},
        }

    def run_lexical(self, cases: list[EvaluationCase], persist: bool = True) -> dict:
        rankings: list[list[str]] = []
        latencies: list[float] = []
        for c in cases:
            t0 = time.perf_counter()
            hits = self.lexical.search(c.query, limit=10)
            latencies.append((time.perf_counter() - t0) * 1000)
            rankings.append([h.record.code_sh for h in hits])
        result = self._result(
            engine_type="LEXICAL",
            model_name=None,
            cases=cases,
            rankings=rankings,
            latencies_ms=latencies,
            details={"history_memory": False, "purpose": "baseline sans fuite des cas validés"},
        )
        if persist:
            self.metrics.record_benchmark(result)
        return result

    def _semantic_corpus(self, model, model_name: str) -> tuple[np.ndarray, float, bool]:
        cache_file = self.cache_path / f"camcis_{self.repo.sha256[:16]}_{_model_tag(model_name)}.npz"
        if cache_file.exists():
            loaded = np.load(cache_file, allow_pickle=False)
            vectors = loaded["vectors"].astype(np.float32, copy=False)
            if vectors.shape[0] == len(self.records):
                return vectors, 0.0, True

        started = time.perf_counter()
        passages = _model_texts(model_name, [r.libelle for r in self.records], query=False)
        vectors = model.encode(
            passages,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=128,
            convert_to_numpy=True,
        ).astype(np.float32, copy=False)
        build_s = time.perf_counter() - started
        np.savez_compressed(cache_file, vectors=vectors)
        meta = {
            "camcis_sha256": self.repo.sha256,
            "model_name": model_name,
            "records": len(self.records),
            "dimensions": int(vectors.shape[1]),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        cache_file.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return vectors, build_s, False

    def run_semantic_model(self, cases: list[EvaluationCase], model_name: str, persist: bool = True) -> list[dict]:
        from sentence_transformers import SentenceTransformer

        process = psutil.Process()
        rss_before = process.memory_info().rss / (1024 * 1024)
        model_load_started = time.perf_counter()
        model = SentenceTransformer(model_name)
        model_load_seconds = time.perf_counter() - model_load_started
        corpus, corpus_build_seconds, cache_hit = self._semantic_corpus(model, model_name)

        semantic_rankings: list[list[str]] = []
        hybrid_rankings: list[list[str]] = []
        semantic_latencies: list[float] = []
        hybrid_latencies: list[float] = []

        # Batching query encoding prevents benchmark instrumentation from becoming the bottleneck.
        for c in cases:
            semantic_start = time.perf_counter()
            q_text = _model_texts(model_name, [c.query], query=True)
            q = model.encode(q_text, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)[0].astype(np.float32, copy=False)
            scores = corpus @ q
            k = min(20, len(scores))
            idx = np.argpartition(scores, -k)[-k:]
            idx = idx[np.argsort(scores[idx])[::-1]]
            sem_codes = [self._code_order[int(i)] for i in idx]
            sem_ms = (time.perf_counter() - semantic_start) * 1000
            semantic_latencies.append(sem_ms)
            semantic_rankings.append(sem_codes[:10])

            hybrid_start = time.perf_counter()
            lex_codes = [h.record.code_sh for h in self.lexical.search(c.query, limit=20)]
            hybrid_rankings.append(_rrf_merge(lex_codes, sem_codes, limit=10))
            hybrid_latencies.append(sem_ms + (time.perf_counter() - hybrid_start) * 1000)

        rss_after = process.memory_info().rss / (1024 * 1024)
        common_details = {
            "history_memory": False,
            "model_load_seconds": round(model_load_seconds, 3),
            "corpus_cache_hit": cache_hit,
            "dimensions": int(corpus.shape[1]),
        }
        sem_result = self._result(
            engine_type="SEMANTIC",
            model_name=model_name,
            cases=cases,
            rankings=semantic_rankings,
            latencies_ms=semantic_latencies,
            corpus_build_seconds=corpus_build_seconds,
            rss_delta_mb=rss_after - rss_before,
            details=common_details,
        )
        hybrid_result = self._result(
            engine_type="HYBRID_RRF",
            model_name=model_name,
            cases=cases,
            rankings=hybrid_rankings,
            latencies_ms=hybrid_latencies,
            corpus_build_seconds=corpus_build_seconds,
            rss_delta_mb=rss_after - rss_before,
            details={**common_details, "fusion": "Reciprocal Rank Fusion lexical+semantic, k=60"},
        )
        if persist:
            self.metrics.record_benchmark(sem_result)
            self.metrics.record_benchmark(hybrid_result)

        del model, corpus
        gc.collect()
        return [sem_result, hybrid_result]
