# CGS — Cartographie des données et référentiels

Ce document décrit les magasins de données réellement utilisés par **CGS - Harmonisation Douanière**.

## 1. Référentiel douanier maître

- **Fichier** : `data/reference/Code_SH_CAMCIS.xlsx`
- **Rôle** : source de vérité des codes SH et libellés douaniers utilisés par le moteur.
- **Important** : Qdrant n'est pas la source de vérité ; il s'agit uniquement d'un index dérivé de ce fichier.
- **Accès** : ouvrir directement le classeur Excel depuis le dépôt.

## 2. Index sémantique Qdrant

- **Chemin runtime** : `<CADUCEUS_HOME>/qdrant_storage`
- **Rôle** : recherche vectorielle dense sur les libellés CAMCIS.
- **Collection** : nom physique versionné par hash du fichier CAMCIS et hash du modèle d'embedding.
- **Modèle actuel** : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` sauf surcharge par variable d'environnement.
- **Nature** : cache dérivé reconstruisible.

Sous Windows, `CADUCEUS_HOME` vaut par défaut :

```text
%LOCALAPPDATA%\CADUCEUS
```

Pour examiner les collections localement, arrêter CGS si Qdrant verrouille le stockage puis exécuter :

```bat
python -m scripts.inspect_data_stores --store qdrant
```

## 3. Mémoire de cas humains validés

Références livrées avec l'application :

```text
data/validated_cases/NETIC_valide.xlsx
data/validated_cases/FRANCY_GARDEN_valide.xlsx
data/validated_cases/SOCAAL_valide.xlsx
```

Corrections confirmées par un expert :

```text
<CADUCEUS_HOME>/runtime/validated_cases_user.csv
```

La mémoire validée complète le retrieval lexical/vectoriel. Un code mémorisé n'est retenu que s'il existe toujours dans CAMCIS.

## 4. Journal d'audit SQLite

- **Fichier** : `<CADUCEUS_HOME>/runtime/caduceus_audit.db`
- **Table** : `audit_events`
- **Contenu** : dossier, document source, ligne, désignation, décision complète JSON, hash CAMCIS et version moteur.
- **Convention** : append-only au niveau applicatif.

Ouverture possible avec **DB Browser for SQLite**, SQLiteStudio ou :

```bat
python -m scripts.inspect_data_stores --store audit --limit 20
```

## 5. Base de métriques SQLite

- **Fichier** : `<CADUCEUS_HOME>/runtime/caduceus_metrics.db`
- **Tables** :
  - `runtime_events`
  - `benchmark_runs`
  - `arbitration_benchmark_runs`

Elle contient les temps d'exécution, mémoire, benchmarks du moteur de retrieval et évaluations de l'arbitrage IA.

```bat
python -m scripts.inspect_data_stores --store metrics --limit 20
```

## 6. Cache de décisions IA

- **Fichier** : `<CADUCEUS_HOME>/runtime/caduceus_llm_cache.db`
- **Table** : `llm_decision_cache`
- **Rôle** : éviter de payer/rejouer le même arbitrage IA avec un prompt et une liste de candidats inchangés.

```bat
python -m scripts.inspect_data_stores --store llm --limit 20
```

## 7. Autres états runtime

```text
<CADUCEUS_HOME>/runtime/camcis_index_manifest.json
<CADUCEUS_HOME>/runtime/reference_state.json
<CADUCEUS_HOME>/runtime/fx_rates.json
<CADUCEUS_HOME>/runtime/benchmark_cache/
```

Le manifeste permet à CGS de savoir si l'index sémantique correspond encore au fichier CAMCIS et au modèle d'embedding.

## 8. Commande de vue globale

```bat
python -m scripts.inspect_data_stores --store all --limit 10
```

Cette commande est destinée à l'équipe projet. Elle n'altère aucune donnée.

## 9. Streamlit Community Cloud

Le stockage runtime de Streamlit Community Cloud est **éphémère**. Les données versionnées dans GitHub
(CAMCIS et cas validés livrés) reviennent au redéploiement, mais les bases SQLite, Qdrant, caches et
corrections créés pendant l'exécution ne constituent pas encore une base de production persistante.

Pour une cible multi-utilisateur, CGS devra déplacer ces magasins vers des services persistants
(base relationnelle, stockage objet et/ou Qdrant distant) tout en conservant CAMCIS comme source
de vérité versionnée.
