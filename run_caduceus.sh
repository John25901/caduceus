#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
VENV="${CADUCEUS_VENV:-${HOME}/.caduceus/venv}"
if [[ -f "$VENV/bin/activate" ]]; then
  source "$VENV/bin/activate"
elif [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  source venv/bin/activate
else
  echo "Environnement absent. Exécutez ./setup_once.sh une seule fois."
  exit 1
fi
[[ -f data/reference/Code_SH_CAMCIS.xlsx ]] || { echo "CAMCIS absent"; exit 2; }
python -m scripts.bootstrap || code=$?
code=${code:-0}
if [[ "$code" == "10" ]]; then export CADUCEUS_AUTO_SYNC_INDEX=0; elif [[ "$code" != "0" ]]; then exit "$code"; fi
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
sleep 2
python -m streamlit run frontend/app.py
