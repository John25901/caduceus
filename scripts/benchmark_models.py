from __future__ import annotations

import argparse
import socket
from pathlib import Path

from backend.app.core.config import settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.evaluation.benchmark import BenchmarkRunner, load_evaluation_cases
from backend.app.metrics.store import MetricsStore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = [
    ROOT / "tests" / "evaluation" / "fixtures" / "NETIC_reference.xlsx",
    ROOT / "tests" / "evaluation" / "fixtures" / "FRANCY_GARDEN_reference.xlsx",
    ROOT / "tests" / "evaluation" / "fixtures" / "SOCAAL_reference.xlsx",
]


def print_result(r: dict) -> None:
    model = r.get("model_name") or "-"
    print(
        f"{r['engine_type']:<12} | {model:<58} | n={r['cases']:<4} "
        f"Top1={r['top1_accuracy']:.1%} Top3={r['top3_recall']:.1%} "
        f"Top5={r['top5_recall']:.1%} MRR={r['mrr']:.3f} "
        f"avg={r['avg_query_ms'] or 0:.1f}ms"
    )


def _api_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
            return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="CADUCEUS Model Lab — benchmark local explicite")
    parser.add_argument("--models", nargs="*", default=list(settings.benchmark_models), help="Modèles SentenceTransformer à comparer")
    parser.add_argument("--max-cases", type=int, default=250, help="0 = tous les cas; défaut 250 pour rester frugal")
    parser.add_argument("--lexical-only", action="store_true", help="Exécute uniquement le baseline lexical")
    args = parser.parse_args()

    if _api_running() and not args.lexical_only:
        print("[AVERTISSEMENT] L API CADUCEUS semble active. Pour une mesure RAM/latence plus propre, fermez-la pendant le benchmark multi-modeles.")

    fixtures = [p for p in DEFAULT_FIXTURES if p.exists()]
    if not fixtures:
        raise SystemExit("Aucun jeu d'évaluation disponible.")
    max_cases = None if args.max_cases == 0 else max(1, args.max_cases)
    cases = load_evaluation_cases(fixtures, max_cases=max_cases)
    repo = CamcisRepository(settings.camcis_path)
    metrics = MetricsStore(settings.metrics_db_path)
    runner = BenchmarkRunner(repo, metrics, settings.benchmark_cache_path)

    print(f"CAMCIS: {len(repo.load())} positions | cas benchmark: {len(cases)}")
    baseline = runner.run_lexical(cases)
    print_result(baseline)
    if args.lexical_only:
        return 0

    for model_name in args.models:
        print(f"\n--- {model_name} ---")
        try:
            results = runner.run_semantic_model(cases, model_name)
            for result in results:
                print_result(result)
        except Exception as exc:
            metrics.record_runtime("BENCHMARK_ERROR", details={"model_name": model_name, "error": str(exc)})
            print(f"[ERREUR] {model_name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
