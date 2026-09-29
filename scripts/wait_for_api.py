from __future__ import annotations
import sys, time, requests

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/health"
timeout_s = int(sys.argv[2]) if len(sys.argv) > 2 else 120
deadline = time.time() + timeout_s
last = None
while time.time() < deadline:
    try:
        r = requests.get(url, timeout=2)
        if r.ok:
            print("[API] prête.")
            raise SystemExit(0)
        last = f"HTTP {r.status_code}"
    except Exception as exc:
        last = str(exc)
    time.sleep(1)
print(f"[API] non disponible apres {timeout_s}s: {last}")
raise SystemExit(1)
