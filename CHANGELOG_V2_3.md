# Changelog V2.3 — Sprint 3 Ingestion documentaire

- Ajout du dispatcher d'ingestion universel.
- Ajout Word `.docx`.
- Ajout PDF natif (tables + texte).
- Ajout images et PDF scannés via Tesseract, uniquement à la demande.
- Ajout `source_page` et `extraction_method` dans la trace technique.
- Détection conservatrice des lignes commerciales afin de ne pas transformer les clauses contractuelles en équipements.
- Arrêt anticipé de l'analyse des longues spécifications lorsqu'un séparateur explicite est détecté.
- Ajout de métriques d'ingestion : type, méthode, pages OCR, temps et RAM.
- Ajout d'un benchmark CLI d'ingestion.
- Ajout d'une mise à jour de dépendances ciblée (`update_to_v23.bat`) sans réinstallation de Streamlit.
- 17 tests automatisés validés.
