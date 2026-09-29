# CADUCEUS V2.4 — Rapport de tests

Commande de régression :

```bash
CADUCEUS_ENABLE_SEMANTIC=0 pytest -q
```

Résultat : **24 tests passés**.

## Régression métier SOCAAL
Test de bout en bout sur `SOCAAL Liste Materiels & Equipements.pdf` :

- 170 lignes d'équipements détectées ;
- 0 unité perdue dans les objets extraits ;
- 170/170 codes source reconnus dans CAMCIS et marqués `CONFIRME_SOURCE` ;
- profil projet détecté : `PAPER_PACKAGING` avec confiance 0,97 lorsque le contexte projet est fourni ;
- 80 lignes `COHERENT`, 82 `JUSTIFIABLE`, 8 `A_EXAMINER` ;
- Excel professionnel généré avec `Prix total (XAF)` sous forme de formule `Quantité × Prix unitaire` ;
- rapport d'audit Word : 2 pages dans le cas de régression ;
- rapport d'audit PDF : 2 pages dans le cas de régression.

## Contrôles complémentaires
- NETIC : 423 articles extraits, préférence des colonnes monétaires FCFA/XAF et absence de caractères CJK dans les spécifications professionnelles après normalisation.
- Proforma Egg Tray USD : sans taux de change, le statut financier reste `TAUX_REQUIS` et aucune valeur XAF n'est inventée ; avec le taux 565,124, 38 000 USD donnent 21 474 712 XAF.
- Le fichier source, les valeurs originales et les détails techniques restent disponibles dans l'audit sans surcharger le document destiné à la Direction.

## Principe de test
Le mode sémantique est désactivé pendant la suite de tests unitaires afin de rendre la régression rapide et reproductible. Les benchmarks de modèles sont traités séparément dans le Model Lab.
