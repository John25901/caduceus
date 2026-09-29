#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
VENV="${CADUCEUS_VENV:-${HOME}/.caduceus/venv}"
python3 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo "Installation terminée. Utilisez désormais ./run_caduceus.sh"
