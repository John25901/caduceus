from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import psutil

from backend.app.ingestion.document_parser import UniversalEquipmentParser


def main() -> int:
    ap = argparse.ArgumentParser(description="Mesure locale de l'ingestion documentaire CADUCEUS")
    ap.add_argument("files", nargs="+", help="Documents à analyser")
    ap.add_argument("--no-ocr", action="store_true", help="Désactive l'OCR pour mesurer uniquement l'extraction native")
    args = ap.parse_args()

    parser = UniversalEquipmentParser(enable_ocr=not args.no_ocr)
    proc = psutil.Process(os.getpid())
    rows = []
    for raw in args.files:
        path = Path(raw)
        before = proc.memory_info().rss / 1024 / 1024
        started = time.perf_counter()
        try:
            result = parser.parse_path(path)
            elapsed = (time.perf_counter() - started) * 1000
            after = proc.memory_info().rss / 1024 / 1024
            rows.append({
                "file": path.name,
                "source_type": result.source_type,
                "method": result.extraction_method,
                "items": len(result.items),
                "pages_total": result.pages_total,
                "pages_ocr": result.pages_ocr,
                "duration_ms": round(elapsed, 2),
                "rss_delta_mb": round(after - before, 2),
                "warnings": result.warnings,
            })
        except Exception as exc:
            rows.append({"file": path.name, "error": str(exc)})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
