# Sprint 5 — Automatisation opérationnelle et UX du moteur

Objectif : supprimer les manipulations inutiles, restaurer la fidélité documentaire et rendre les fonctions techniques compréhensibles.

## Points livrés

1. Synchronisation de démarrage API/UI sans erreur de santé transitoire.
2. Taux de change XAF automatique et auditable, avec cache et override officiel possible.
3. Correction du parsing des tableaux PDF multi-pages sans répétition d'en-tête.
4. Activation OCR Windows simplifiée sans réinstaller l'environnement Python.
5. Model Lab exploitable depuis Streamlit avec indicateurs métier expliqués.
6. Maintien du principe anti-hallucination : aucun taux, code SH ou traduction n'est inventé si la source échoue.

## Régression de référence

Le devis `Steel Structure Workshop 90m×50m×12m Quotation-SHANDONG LANJING-20260403.pdf` contient 22 lignes commerciales sur deux pages. La V2.5 doit en extraire 22, y compris `Turnbuckle bolts` et les lignes de la seconde page.
