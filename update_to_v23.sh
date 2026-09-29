#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
VENV="${CADUCEUS_VENV:-$HOME/.caduceus/venv}"
if [ -f "$VENV/bin/activate" ]; then source "$VENV/bin/activate";
elif [ -f .venv/bin/activate ]; then source .venv/bin/activate;
elif [ -f venv/bin/activate ]; then source venv/bin/activate;
else echo "Environnement CADUCEUS absent. Lancez setup_once.sh."; exit 1; fi
if python - <<'PY' >/dev/null 2>&1
import fitz, pdfplumber, docx, pytesseract
from PIL import Image
PY
then
  echo "[OK] Dépendances Sprint 3 déjà présentes."
else
  python -m pip install -r requirements-update-v2.3.txt
fi
if command -v tesseract >/dev/null 2>&1; then echo "[OK] Tesseract OCR détecté."; else echo "[INFO] Tesseract absent : les formats natifs restent utilisables."; fi
