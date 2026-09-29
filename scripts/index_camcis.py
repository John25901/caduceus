"""Outil de maintenance facultatif.

Le démarrage normal n'en dépend plus: `run_caduceus` et l'API synchronisent CAMCIS automatiquement.
Utiliser ce script uniquement pour forcer volontairement une reconstruction sémantique.
"""
from __future__ import annotations

from backend.app.core.bootstrap import synchronize_references
from backend.app.core.config import settings


def main() -> int:
    try:
        repo, result, _, _ = synchronize_references(settings, force_index=True)
    except Exception as exc:
        print(f"[ERREUR] {exc}")
        return 2
    print(f"CAMCIS: {len(repo.load())} positions | {repo.sha256[:16]}…")
    print(result.as_dict())
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
