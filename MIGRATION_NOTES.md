# Migration V2.2 → V2.3

## À faire une seule fois

Après avoir appliqué la V2.3 sur une installation V2.2 existante :

```bat
update_to_v23.bat
```

Ce script :
1. réutilise l'environnement Python CADUCEUS existant ;
2. teste la présence des seules nouvelles bibliothèques du Sprint 3 ;
3. n'appelle `pip install` que si elles manquent ;
4. ne réinstalle donc pas Streamlit ou Sentence Transformers.

Les lancements normaux restent :

```bat
run_caduceus.bat
```

## Nouvelles dépendances Python

Uniquement : PyMuPDF, pdfplumber, python-docx, Pillow et pytesseract.

Tesseract lui-même est un moteur externe optionnel. Sans lui, Excel/CSV/TXT/Word et PDF natifs fonctionnent toujours.

## Données existantes

Le stockage `%LOCALAPPDATA%\CADUCEUS` est réutilisé. La mise à jour du code ne supprime ni Qdrant, ni métriques, ni audit, ni manifeste CAMCIS.
