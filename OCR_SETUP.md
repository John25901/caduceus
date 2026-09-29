# CADUCEUS V2.3 — OCR Tesseract (optionnel)

CADUCEUS traite **sans OCR** les fichiers Excel, CSV, TXT, Word et les PDF qui contiennent déjà du texte exploitable.

L'OCR n'est appelé que pour :
- les images (`PNG`, `JPG`, `WEBP`, `TIF`) ;
- les pages PDF scannées ne contenant pratiquement aucun texte natif.

## Windows

1. Installer **Tesseract OCR 5.x** avec les langues française et anglaise.
2. Si `tesseract.exe` n'est pas dans le `PATH`, définir une variable d'environnement :

```text
TESSERACT_CMD=C:\chemin\vers\Tesseract-OCR\tesseract.exe
```

3. Relancer `run_caduceus.bat`.

Le panneau **État du système** indique si l'OCR est disponible.

## Principe de sobriété

CADUCEUS ne rasterise pas un PDF entier par défaut. Une page contenant déjà du texte est traitée nativement. L'OCR n'est déclenché que lorsque la page ressemble à un scan, ce qui limite fortement le temps CPU et la consommation mémoire.
