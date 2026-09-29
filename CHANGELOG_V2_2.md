# CADUCEUS V2.2 — Correctif UX, export professionnel et persistance

## Changements demandés après test utilisateur

1. **Plus d'installation à chaque version**
   - `setup_once.bat` crée un environnement Python persistant dans `%LOCALAPPDATA%\CADUCEUS\venv`.
   - `run_caduceus.bat` ne lance aucun `pip install`.
   - `update_dependencies.bat` est réservé aux changements réels de dépendances.
   - `openpyxl` est bien présent dans `requirements.txt`.

2. **Persistance réelle de l'index CAMCIS**
   - Qdrant, le manifeste d'index, les métriques et l'audit sont déplacés hors du dossier source vers `%LOCALAPPDATA%\CADUCEUS` (ou `~/.caduceus`).
   - Une nouvelle archive du code ne provoque donc plus, à elle seule, une reconstruction du référentiel.
   - Lors du passage depuis V2.1, CADUCEUS migre automatiquement l’ancien index Qdrant et les fichiers runtime locaux vers le stockage persistant lorsqu’ils sont présents.

3. **Interface métier simplifiée**
   - suppression du réglage « nombre de candidats CAMCIS » ; Top-K=5 reste un paramètre interne ;
   - suppression de `Ligne source`, `Score retrieval`, `Top 2`, `Statut tarifaire` et `Motif` de la restitution principale ;
   - diagnostics techniques disponibles uniquement dans un expander réservé à l'équipe projet ;
   - ajout d'un vrai onglet `Guide utilisateur`.

4. **Export Excel professionnel**
   - tableau principal proche des listes de travail métier ;
   - position tarifaire, libellé douanier, spécifications, quantité, unité, prix et origine ;
   - colonne `Observations` en langage métier ;
   - clé de lecture latérale avec couleurs jaune/orange/bleu/rouge ;
   - synthèse latérale ;
   - mise en page paysage A3, filtres, volets figés, largeurs et retours à la ligne ;
   - feuilles `_Audit_technique` et `_Métadonnées` masquées afin de préserver la traçabilité sans polluer le document Direction/client.

## Validation

- compilation Python : OK ;
- tests automatiques : **12/12** ;
- export Excel test NETIC : OK ;
- aucun Docker requis.
