"""Entrypoint Streamlit Community Cloud pour CADUCEUS V2.6.

Community Cloud n'exécute qu'une commande Streamlit. CADUCEUS conserve pourtant
son API FastAPI interne. Cet entrypoint lance donc l'API comme processus local
privé, attend /health, puis charge l'interface métier.

Aucun port FastAPI n'est exposé publiquement : Streamlit reste le seul point
d'entrée Internet.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# Runtime writable. Community Cloud ne garantit pas la persistance des fichiers
# générés entre redémarrages : cette valeur isole donc les données éphémères.
os.environ.setdefault("CADUCEUS_HOME", str(Path.home() / ".caduceus"))
os.environ.setdefault("CADUCEUS_API_BASE", "http://127.0.0.1:8000")

HOST = "127.0.0.1"
PORT = int(os.getenv("CADUCEUS_INTERNAL_API_PORT", "8000"))
HEALTH_URL = f"http://{HOST}:{PORT}/health"
LOCK = Path(tempfile.gettempdir()) / "caduceus_fastapi_start.lock"


def _port_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.4):
            return True
    except OSError:
        return False


def _healthy() -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=2) as response:  # nosec B310 - localhost only
            return 200 <= response.status < 500
    except Exception:
        return False


def _claim_start_lock() -> bool:
    # Evite deux uvicorn lors de connexions simultanées au premier réveil.
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - LOCK.stat().st_mtime > 300:
                LOCK.unlink(missing_ok=True)
                return _claim_start_lock()
        except OSError:
            pass
        return False


def _start_api_if_needed() -> None:
    if _healthy():
        return

    owner = _claim_start_lock()
    if owner:
        log_path = Path(tempfile.gettempdir()) / "caduceus_fastapi.log"
        log = open(log_path, "a", encoding="utf-8")
        env = os.environ.copy()
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                HOST,
                "--port",
                str(PORT),
                "--log-level",
                os.getenv("CADUCEUS_UVICORN_LOG_LEVEL", "warning"),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # L'index CAMCIS peut être reconstruit lors d'un cold start. L'UI n'est chargée
    # qu'une fois l'API réellement prête, ce qui évite les WinError/ConnectionError.
    timeout_s = int(os.getenv("CADUCEUS_CLOUD_STARTUP_TIMEOUT", "300"))
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _healthy():
            LOCK.unlink(missing_ok=True)
            return
        time.sleep(1.0)

    LOCK.unlink(missing_ok=True)
    log_path = Path(tempfile.gettempdir()) / "caduceus_fastapi.log"
    tail = ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-40:])
    except Exception:
        pass
    raise RuntimeError(
        "L'API interne CADUCEUS n'a pas démarré dans le délai imparti. "
        "Consultez les logs Streamlit.\n" + tail
    )


_start_api_if_needed()

# Exécute l'UI existante comme entrypoint, après set-up de l'API interne.
code = (ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
exec(compile(code, str(ROOT / "frontend" / "app.py"), "exec"), globals(), globals())
