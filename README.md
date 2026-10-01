# CGS - Harmonisation Douanière — Plateforme propriétaire CREATIV GROUP SARL

CGS - Harmonisation Douanière automatise l'ingestion des listes d'équipements, leur harmonisation au référentiel douanier camerounais, les contrôles de cohérence sectorielle, la normalisation financière en XAF, l'audit et la production de livrables professionnels.

## Démarrage

Si une version V2.5 fonctionne déjà : appliquez le patch V2.6 puis lancez simplement :

```bat
run_caduceus.bat
```

**Ne relancez pas `requirements.txt`.** Le Sprint 6 n'ajoute aucune dépendance Python.

Sur une nouvelle machine :

```bat
setup_once.bat
run_caduceus.bat
```

Docker n'est pas requis.

## Référentiel CAMCIS et persistance

Le référentiel maître est `data/reference/Code_SH_CAMCIS.xlsx`. Qdrant, métriques, audit, taux de change et caches sont stockés de façon durable sous `%LOCALAPPDATA%\CADUCEUS` sous Windows.

## Formats d'entrée

Excel, CSV/TXT, Word, PDF natif, PDF scanné et images. L'extraction native est privilégiée ; l'OCR n'est utilisé que lorsqu'il est nécessaire.

## Arbitrage IA contrôlé — Sprint 6

Le moteur local reste prioritaire. Une IA commerciale n'est sollicitée que pour certains cas `A_REVOIR`.

Le fournisseur ne reçoit qu'une **liste fermée de candidats CAMCIS** et doit soit choisir l'un d'eux, soit s'abstenir. Une sortie contenant un autre code est rejetée automatiquement.

Pour configurer NVIDIA/Kimi ou OpenAI :

```bat
configure_ai.bat
```

La saisie de la clé est masquée. Le fichier `.env` local est exclu de Git.

Sans clé IA, l'application reste pleinement opérationnelle avec le moteur local.

## Model Lab

L'onglet **Évaluation moteur** sépare maintenant :
- la qualité de recherche CAMCIS (Top-1 / Top-3 / Top-5) ;
- la valeur ajoutée de l'arbitrage IA sur les cas réellement ambigus ;
- le coût opérationnel : appels, tokens, cache et latence.

Les benchmarks commerciaux sont déclenchés manuellement et plafonnés afin d'éviter des coûts cachés.

## Validation

```bash
python -m pytest -q
```

État V2.6 : **33 tests passent**.

Voir `SPRINT6_REPORT.md`, `CHANGELOG_V2_6.md`, `MIGRATION_V2_6.md` et `GUIDE_UTILISATEUR.md`.

## Déploiement GitHub + Streamlit Community Cloud

La distribution de déploiement inclut `streamlit_app.py`, `packages.txt`, la CI GitHub
Actions et la configuration Streamlit. Voir `DEPLOYMENT_STREAMLIT_CLOUD.md`.


## Identité visuelle

L'application publique utilise l'identité **CGS - Harmonisation Douanière** de CREATIV GROUP SARL,
avec une charte gris / rouge bordeaux. Le même lockup est repris dans les exports Excel, Word et PDF.

Pour utiliser le fichier officiel exact du logo CREATIV GROUP, déposer un PNG validé à l'emplacement :

`assets/creativ_group_logo.png`

Aucun changement de code n'est nécessaire : l'interface et les exports le détectent automatiquement.
