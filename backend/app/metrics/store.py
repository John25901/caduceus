from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.metrics.performance import PerformanceSnapshot


SCHEMA = """
CREATE TABLE IF NOT EXISTS runtime_events (
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    duration_ms REAL,
    rss_before_mb REAL,
    rss_after_mb REAL,
    rss_delta_mb REAL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runtime_events_created_at
ON runtime_events(created_at DESC);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    engine_type TEXT NOT NULL,
    model_name TEXT,
    dataset_name TEXT NOT NULL,
    cases INTEGER NOT NULL,
    top1_accuracy REAL NOT NULL,
    top3_recall REAL NOT NULL,
    top5_recall REAL NOT NULL,
    mrr REAL NOT NULL,
    avg_query_ms REAL,
    p95_query_ms REAL,
    corpus_build_seconds REAL,
    rss_delta_mb REAL,
    camcis_sha256 TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_benchmark_runs_created_at
ON benchmark_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS arbitration_benchmark_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT,
    dataset_name TEXT NOT NULL,
    cases INTEGER NOT NULL,
    retrieval_coverage REAL NOT NULL,
    baseline_top1_accuracy REAL NOT NULL,
    arbitration_accuracy_on_covered REAL NOT NULL,
    end_to_end_accuracy REAL NOT NULL,
    abstention_rate REAL NOT NULL,
    invalid_output_rate REAL NOT NULL,
    api_error_rate REAL NOT NULL,
    avg_latency_ms REAL,
    calls INTEGER NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cache_hits INTEGER NOT NULL,
    camcis_sha256 TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_arbitration_benchmark_created_at
ON arbitration_benchmark_runs(created_at DESC);
"""


class MetricsStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_runtime(
        self,
        event_type: str,
        snapshot: PerformanceSnapshot | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        merged = dict(snapshot.details if snapshot else {})
        merged.update(details or {})
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO runtime_events
                   (event_id, created_at, event_type, duration_ms, rss_before_mb, rss_after_mb, rss_delta_mb, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    snapshot.duration_ms if snapshot else None,
                    snapshot.rss_before_mb if snapshot else None,
                    snapshot.rss_after_mb if snapshot else None,
                    snapshot.rss_delta_mb if snapshot else None,
                    json.dumps(merged, ensure_ascii=False),
                ),
            )
        return event_id

    def record_benchmark(self, result: dict[str, Any]) -> str:
        run_id = str(result.get("run_id") or uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO benchmark_runs
                   (run_id, created_at, engine_type, model_name, dataset_name, cases,
                    top1_accuracy, top3_recall, top5_recall, mrr,
                    avg_query_ms, p95_query_ms, corpus_build_seconds, rss_delta_mb,
                    camcis_sha256, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    result.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    result["engine_type"],
                    result.get("model_name"),
                    result.get("dataset_name", "ALL"),
                    int(result.get("cases", 0)),
                    float(result.get("top1_accuracy", 0.0)),
                    float(result.get("top3_recall", 0.0)),
                    float(result.get("top5_recall", 0.0)),
                    float(result.get("mrr", 0.0)),
                    result.get("avg_query_ms"),
                    result.get("p95_query_ms"),
                    result.get("corpus_build_seconds"),
                    result.get("rss_delta_mb"),
                    result["camcis_sha256"],
                    json.dumps(result.get("details", {}), ensure_ascii=False),
                ),
            )
        return run_id

    def recent_runtime(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runtime_events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["details"] = json.loads(item.pop("details_json") or "{}")
            out.append(item)
        return out

    def benchmark_results(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM benchmark_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["details"] = json.loads(item.pop("details_json") or "{}")
            out.append(item)
        return out


    def record_arbitration_benchmark(self, result: dict[str, Any]) -> str:
        run_id = str(result.get("run_id") or uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO arbitration_benchmark_runs
                   (run_id, created_at, provider, model_name, dataset_name, cases,
                    retrieval_coverage, baseline_top1_accuracy, arbitration_accuracy_on_covered,
                    end_to_end_accuracy, abstention_rate, invalid_output_rate, api_error_rate,
                    avg_latency_ms, calls, prompt_tokens, completion_tokens, cache_hits, camcis_sha256, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id, result.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    result.get("provider") or "UNKNOWN", result.get("model_name"), result.get("dataset_name", "ALL"),
                    int(result.get("cases", 0)), float(result.get("retrieval_coverage", 0.0)),
                    float(result.get("baseline_top1_accuracy", 0.0)), float(result.get("arbitration_accuracy_on_covered", 0.0)),
                    float(result.get("end_to_end_accuracy", 0.0)), float(result.get("abstention_rate", 0.0)),
                    float(result.get("invalid_output_rate", 0.0)), float(result.get("api_error_rate", 0.0)),
                    result.get("avg_latency_ms"), int(result.get("calls", 0)),
                    result.get("prompt_tokens"), result.get("completion_tokens"), int(result.get("cache_hits", 0)),
                    result["camcis_sha256"], json.dumps(result.get("details", {}), ensure_ascii=False),
                ),
            )
        return run_id

    def arbitration_benchmark_results(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM arbitration_benchmark_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["details"] = json.loads(item.pop("details_json") or "{}")
            out.append(item)
        return out

    def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            runtime_count = conn.execute("SELECT COUNT(*) FROM runtime_events").fetchone()[0]
            benchmark_count = conn.execute("SELECT COUNT(*) FROM benchmark_runs").fetchone()[0]
            arbitration_count = conn.execute("SELECT COUNT(*) FROM arbitration_benchmark_runs").fetchone()[0]
            mapping = conn.execute(
                """SELECT COUNT(*) AS n, AVG(duration_ms) AS avg_ms
                   FROM runtime_events WHERE event_type='PROCESS_BORDEREAU'"""
            ).fetchone()
            startup = conn.execute(
                """SELECT duration_ms, created_at FROM runtime_events
                   WHERE event_type='APP_STARTUP' ORDER BY created_at DESC LIMIT 1"""
            ).fetchone()
        return {
            "runtime_events": int(runtime_count),
            "benchmark_runs": int(benchmark_count),
            "arbitration_benchmark_runs": int(arbitration_count),
            "mapping_runs": int(mapping["n"] or 0),
            "mapping_avg_ms": round(float(mapping["avg_ms"]), 3) if mapping["avg_ms"] is not None else None,
            "last_startup_ms": float(startup["duration_ms"]) if startup and startup["duration_ms"] is not None else None,
            "last_startup_at": startup["created_at"] if startup else None,
        }
