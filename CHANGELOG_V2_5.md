# CADUCEUS V2.5 — Sprint 5 Automatisation opérationnelle

## Correctifs et évolutions

- Démarrage UX : `run_caduceus.bat` attend maintenant que l'API soit réellement prête avant d'ouvrir Streamlit. L'erreur rouge initiale des métriques disparaît.
- Métriques : chargement automatique ; aucun bouton « Rafraîchir » nécessaire pour l'usage normal.
- Régression PDF corrigée : les tableaux commerciaux poursuivis sur une page suivante sans en-tête sont conservés. Le devis `Steel Structure Workshop...pdf` retrouve ses 22 lignes commerciales.
- Conversion XAF automatique : EUR/XAF via la parité fixe BEAC ; USD et autres devises via une référence quotidienne Frankfurter -> EUR, puis conversion déterministe vers XAF. Cache local quotidien et traçabilité source/date.
- Un taux officiel de dossier peut toujours remplacer l'automatique dans les options avancées.
- OCR : meilleure détection de Tesseract sous Windows + installateur `install_ocr_windows.bat`. `update_to_v25.bat` l'active sans réinstaller les packages Python.
- Model Lab : interface francisée et expliquée ; tests MiniLM/E5 lançables depuis l'interface, résultats présentés en Top-1/Top-3/Top-5/MRR avec détails techniques repliés.
- Aucune nouvelle dépendance Python et aucune réinstallation de `requirements.txt` nécessaire depuis V2.4.
