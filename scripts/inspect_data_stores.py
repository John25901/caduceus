from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.history_repository import ValidatedCaseMemory


def _print(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _sqlite_preview(path: Path, tables: list[str], limit: int) -> dict[str, Any]:
    out: dict[str, Any] = {"path": str(path), "exists": path.exists(), "tables": {}}
    if not path.exists():
        return out
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        for table in tables:
            try:
                count = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                rows = [
                    dict(r)
                    for r in conn.execute(
                        f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)
                    ).fetchall()
                ]
                out["tables"][table] = {"count": count, "sample": rows}
            except Exception as exc:
                out["tables"][table] = {"error": str(exc)}
    return out


def inspect_camcis(limit: int) -> dict[str, Any]:
    repo = CamcisRepository(settings.camcis_path)
    rows = repo.load()
    return {
        "path": str(settings.camcis_path),
        "stats": repo.stats(),
        "sample": [
            {
                "code_sh": r.code_sh,
                "libelle": r.libelle,
                "chapter": r.chapter,
                "heading": r.heading,
            }
            for r in rows[:limit]
        ],
    }


def inspect_validated(limit: int) -> dict[str, Any]:
    memory = ValidatedCaseMemory(settings.validated_cases_path, settings.user_validated_cases_path)
    sample = [
        {"designation_normalisee": text, "code_sh": code, "source": source}
        for text, code, source in memory._cases[:limit]  # team inspection utility
    ]
    return {
        "shipped_folder": str(settings.validated_cases_path),
        "user_file": str(settings.user_validated_cases_path),
        "stats": memory.stats(),
        "sample": sample,
    }


def inspect_qdrant() -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(settings.qdrant_path), "exists": settings.qdrant_path.exists()}
    if not settings.qdrant_path.exists():
        return result
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(path=str(settings.qdrant_path))
        try:
            collections = []
            for col in client.get_collections().collections:
                try:
                    count = int(client.count(collection_name=col.name, exact=True).count)
                except Exception:
                    count = None
                collections.append({"name": col.name, "points": count})
            result["collections"] = collections
        finally:
            client.close()
    except Exception as exc:
        result["error"] = (
            f"{exc}. Si CGS est lancé localement, arrêtez-le avant d'ouvrir directement "
            "le stockage Qdrant afin d'éviter un conflit de verrouillage."
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspection en lecture seule des magasins de données CGS.")
    parser.add_argument(
        "--store",
        default="all",
        choices=["all", "camcis", "validated", "audit", "metrics", "llm", "qdrant"],
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    limit = max(1, min(args.limit, 100))

    _print(
        "Chemins CGS",
        {
            "CADUCEUS_HOME": str(settings.app_data_root),
            "camcis": str(settings.camcis_path),
            "qdrant": str(settings.qdrant_path),
            "audit": str(settings.audit_db_path),
            "metrics": str(settings.metrics_db_path),
            "llm_cache": str(settings.llm_cache_path),
            "validated_user": str(settings.user_validated_cases_path),
        },
    )

    if args.store in {"all", "camcis"}:
        _print("Référentiel CAMCIS", inspect_camcis(limit))
    if args.store in {"all", "validated"}:
        _print("Mémoire validée", inspect_validated(limit))
    if args.store in {"all", "audit"}:
        _print("Audit", _sqlite_preview(settings.audit_db_path, ["audit_events"], limit))
    if args.store in {"all", "metrics"}:
        _print(
            "Métriques",
            _sqlite_preview(
                settings.metrics_db_path,
                ["runtime_events", "benchmark_runs", "arbitration_benchmark_runs"],
                limit,
            ),
        )
    if args.store in {"all", "llm"}:
        _print("Cache IA", _sqlite_preview(settings.llm_cache_path, ["llm_decision_cache"], limit))
    if args.store in {"all", "qdrant"}:
        _print("Qdrant", inspect_qdrant())


if __name__ == "__main__":
    main()
