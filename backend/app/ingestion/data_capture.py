from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CapturedLine:
    line_no: int
    text: str


def capture_text_lines(text: str, *, limit: int = 160) -> list[dict]:
    """Preserve OCR output without forcing it into an equipment schema.

    This layer is deliberately generic: it exists so CGS can show what was
    actually collected even when harmonisation is not possible.
    """
    rows: list[dict] = []
    for line in (text or "").splitlines():
        clean = " ".join(line.split()).strip()
        if not clean:
            continue
        rows.append({"line": len(rows) + 1, "text": clean})
        if len(rows) >= limit:
            break
    return rows


_LABEL_VALUE_RE = re.compile(
    r"^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 /&().,'_-]{1,42}?)\s*[:：]\s*(.+?)\s*$"
)


def capture_label_value_records(text: str, *, limit: int = 80) -> list[dict]:
    """Extract repeated label/value blocks from OCR text.

    Useful for directories, specification sheets and forms. The routine does
    not infer missing values and never maps these records to customs items.
    """
    records: list[dict] = []
    current: dict[str, str] = {}
    seen_keys: set[str] = set()

    for raw in (text or "").splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        match = _LABEL_VALUE_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip().rstrip(".").upper()
        value = match.group(2).strip()
        if not value:
            continue

        # When a key repeats, we are probably entering the next visual block.
        if key in seen_keys and current:
            records.append(dict(current))
            if len(records) >= limit:
                break
            current = {}
            seen_keys = set()

        current[key] = value
        seen_keys.add(key)

    if current and len(records) < limit:
        records.append(dict(current))

    return records
