from __future__ import annotations

from backend.app.core.bootstrap import synchronize_references
from backend.app.core.config import settings
from backend.app.metrics.performance import PerformanceProbe
from backend.app.metrics.store import MetricsStore


def main() -> int:
    metrics = MetricsStore(settings.metrics_db_path)
    print("[*] Vérification du référentiel CAMCIS et des caches dérivés…")
    try:
        with PerformanceProbe() as probe:
            repo, index_sync, history_stats, _ = synchronize_references(settings)
            snap = probe.finish({
                "camcis_records": len(repo.load()),
                "camcis_sha256": repo.sha256,
                "semantic_status": index_sync.status,
                "semantic_collection": index_sync.collection_name,
                "validated_cases": history_stats.get("cases", 0),
            })
        metrics.record_runtime("REFERENCE_BOOTSTRAP", snap)
    except Exception as exc:
        metrics.record_runtime("REFERENCE_BOOTSTRAP_ERROR", details={"error": str(exc)})
        print(f"[ERREUR FATALE] {exc}")
        return 2

    print(f"[✓] CAMCIS: {len(repo.load())} positions | SHA256={repo.sha256[:16]}…")
    print(f"[✓] Mémoire validée: {history_stats.get('cases', 0)} cas")
    if index_sync.ready:
        if index_sync.status == "CURRENT":
            print(f"[✓] Index sémantique pérenne: à jour ({index_sync.collection_name}) — 0 embedding recalculé")
        else:
            print(f"[✓] Index sémantique reconstruit: {index_sync.collection_name} en {index_sync.build_seconds}s")
    else:
        print(f"[!] Mode sémantique dégradé: {index_sync.status} — {index_sync.reason}")
        print("    L'application peut démarrer en lexical + mémoire validée; aucune conformité n'est présumée.")
    if settings.enable_semantic and not index_sync.ready:
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
