from backend.app.metrics.performance import PerformanceSnapshot
from backend.app.metrics.store import MetricsStore


def test_metrics_store_persists_runtime_and_benchmark(tmp_path):
    store = MetricsStore(tmp_path / "metrics.db")
    store.record_runtime(
        "TEST",
        PerformanceSnapshot(12.3, 100.0, 101.0, 1.0, {"x": 1}),
    )
    store.record_benchmark({
        "engine_type": "LEXICAL",
        "model_name": None,
        "dataset_name": "fixture",
        "cases": 2,
        "top1_accuracy": 0.5,
        "top3_recall": 1.0,
        "top5_recall": 1.0,
        "mrr": 0.75,
        "avg_query_ms": 1.2,
        "p95_query_ms": 2.0,
        "corpus_build_seconds": None,
        "rss_delta_mb": 0.0,
        "camcis_sha256": "abc",
        "details": {"history_memory": False},
    })
    assert store.summary()["runtime_events"] == 1
    assert store.summary()["benchmark_runs"] == 1
    assert store.recent_runtime(1)[0]["details"]["x"] == 1
    assert store.benchmark_results(1)[0]["top1_accuracy"] == 0.5
