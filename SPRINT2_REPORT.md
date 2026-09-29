# Rapport Sprint 2 — Pérennité des références & observabilité

## Objectif

Rendre le socle V2 exploitable sans séquence d'initialisation manuelle fragile et introduire une discipline de mesure avant d'ajouter OCR, cohérence sectorielle et LLM.

## Livré

1. `requirements.txt` unique pour l'exécution ; `requirements-dev.txt` pour les tests.
2. Qdrant local embarqué, sans Docker.
3. Bootstrap automatique CAMCIS via SHA-256.
4. Collections Qdrant physiques versionnées par hash CAMCIS + hash du modèle.
5. Manifeste persistant et photographie de l'état des références.
6. Aucun rebuild si référentiel et modèle inchangés.
7. Démarrage dégradé explicite si la couche sémantique est indisponible, sans présomption de conformité.
8. Instrumentation temps/RSS persistée dans SQLite.
9. Model Lab avec métriques de ranking et cache d'embeddings de benchmark.
10. Interface Streamlit enrichie avec vues Santé/Métriques et Évaluation moteur.
11. `run_caduceus` sans `--reload` afin de limiter les conflits de verrouillage Qdrant local.

## Règles de sobriété

- Aucun benchmark de modèle n'est exécuté automatiquement.
- Aucun deuxième modèle n'est chargé lors du traitement normal.
- Le corpus sémantique CAMCIS n'est recalculé que si le hash CAMCIS ou le modèle change.
- Les métriques runtime utilisent des mesures ponctuelles de RSS plutôt qu'un échantillonnage permanent.
- Les modèles benchmark sont chargés séquentiellement.

## Baseline mesurée

Jeu complet : 911 cas historiques avec code attendu, mémoire historique désactivée.

| Moteur | Top-1 | Top-3 | Top-5 | MRR | Temps moyen |
|---|---:|---:|---:|---:|---:|
| Lexical CAMCIS | 5,8 % | 11,2 % | 14,4 % | 0,093 | ~6,1 ms/requête |

Interprétation : excellente sobriété/latence, mais rappel insuffisant pour constituer seul un moteur d'imputation. Le benchmark sémantique local doit maintenant déterminer le meilleur compromis qualité / RAM / latence.

## Critères de décision pour les prochains modèles

Un modèle plus lourd ne sera adopté que si son gain Top-3/Top-5 et son impact sur les faux auto-accept justifient son coût en RAM, latence et temps de démarrage.

La prochaine étape recommandée après retour local sur V2.1 : exécuter le Model Lab sur les deux modèles locaux par défaut, figer une baseline, puis passer au Sprint 3 documentaire (PDF/OCR/Word) sans mélanger les sources d'erreurs.
