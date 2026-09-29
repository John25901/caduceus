from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.ingestion.tabular_parser import TabularEquipmentParser
from backend.app.models.domain import EquipmentItem
from backend.app.normalization.text import normalize_search_text


@dataclass(frozen=True)
class HistoricalHit:
    code_sh: str
    designation: str
    source_file: str
    score: float


class ValidatedCaseMemory:
    """Searchable memory of human-validated mappings.

    Shipped reference cases and user-confirmed feedback are kept separate from CAMCIS.
    A remembered code is surfaced only if it exists in CAMCIS at search time.
    """

    def __init__(self, folder: str | Path, user_file: str | Path | None = None):
        self.folder = Path(folder)
        self.user_file = Path(user_file) if user_file else None
        self._cases: list[tuple[str, str, str]] = []
        self._vectorizer = None
        self._matrix = None
        self.load_warnings: list[str] = []
        self._files: list[Path] = []
        self._load()

    def _add_case(self, text: str, code: str, source: str, seen: set[tuple[str, str]]) -> None:
        norm = normalize_search_text(text)
        key = (norm, code)
        if not norm or not code or key in seen:
            return
        seen.add(key)
        self._cases.append((norm, code, source))

    def _load(self) -> None:
        parser = TabularEquipmentParser()
        seen: set[tuple[str, str]] = set()
        if self.folder.exists():
            for path in sorted(self.folder.glob("*.xlsx")):
                self._files.append(path)
                try:
                    parsed = parser.parse_path(path)
                except Exception as exc:
                    self.load_warnings.append(f"{path.name}: {exc}")
                    continue
                for item in parsed.items:
                    if not item.code_sh_source:
                        continue
                    text = item.designation_source + (f". {item.specifications}" if item.specifications else "")
                    self._add_case(text, item.code_sh_source, path.name, seen)

        if self.user_file and self.user_file.exists():
            self._files.append(self.user_file)
            try:
                with self.user_file.open("r", encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        text = (row.get("designation") or "") + (f". {row.get('specifications')}" if row.get("specifications") else "")
                        self._add_case(text, row.get("code_sh") or "", row.get("source_file") or self.user_file.name, seen)
            except Exception as exc:
                self.load_warnings.append(f"{self.user_file.name}: {exc}")

        if self._cases:
            self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
            self._matrix = self._vectorizer.fit_transform([x[0] for x in self._cases])

    def append_validated_items(self, items: list[EquipmentItem], source_file: str) -> int:
        if self.user_file is None:
            return 0
        self.user_file.parent.mkdir(parents=True, exist_ok=True)
        existing: set[tuple[str, str]] = set()
        if self.user_file.exists():
            with self.user_file.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    existing.add((normalize_search_text(row.get("designation") or ""), row.get("code_sh") or ""))
        rows = []
        for item in items:
            if not item.code_sh_source:
                continue
            key = (normalize_search_text(item.designation_source), item.code_sh_source)
            if key in existing:
                continue
            existing.add(key)
            rows.append({
                "designation": item.designation_source,
                "specifications": item.specifications or "",
                "code_sh": item.code_sh_source,
                "source_file": source_file,
                "validated_at_utc": datetime.now(timezone.utc).isoformat(),
            })
        if not rows:
            return 0
        exists = self.user_file.exists()
        with self.user_file.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["designation", "specifications", "code_sh", "source_file", "validated_at_utc"])
            if not exists:
                writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    @property
    def count(self) -> int:
        return len(self._cases)

    @property
    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for path in sorted(self._files, key=lambda p: p.name.lower()):
            h.update(path.name.encode("utf-8"))
            try:
                with path.open("rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(chunk)
            except FileNotFoundError:
                continue
        return h.hexdigest()

    def stats(self) -> dict:
        return {"cases": self.count, "files": [p.name for p in self._files], "sha256": self.fingerprint, "warnings": list(self.load_warnings)}

    def search(self, query: str, limit: int = 20) -> list[HistoricalHit]:
        if not self._cases or self._vectorizer is None or self._matrix is None:
            return []
        q = normalize_search_text(query)
        if not q:
            return []
        qv = self._vectorizer.transform([q])
        cosine = (self._matrix @ qv.T).toarray().ravel()
        pre_n = min(max(limit * 5, 50), len(self._cases))
        idxs = np.argpartition(cosine, -pre_n)[-pre_n:] if pre_n < len(cosine) else np.arange(len(cosine))
        hits: list[HistoricalHit] = []
        for idx in idxs:
            text, code, source = self._cases[int(idx)]
            fuzzy = fuzz.token_set_ratio(q, text) / 100.0
            score = 0.8 * float(cosine[int(idx)]) + 0.2 * fuzzy
            hits.append(HistoricalHit(code_sh=code, designation=text, source_file=source, score=max(0.0, min(1.0, score))))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
