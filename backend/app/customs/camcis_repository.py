from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.app.normalization.text import clean_text, display_hs_code, hs_hierarchy, normalize_hs_code, normalize_search_text


@dataclass(frozen=True)
class CamcisRecord:
    code_sh: str
    code_sh_affiche: str
    libelle: str
    search_text: str
    chapter: str | None
    heading: str | None


class CamcisRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._records: list[CamcisRecord] | None = None
        self._by_code: dict[str, CamcisRecord] = {}
        self._sha256: str | None = None

    @property
    def sha256(self) -> str:
        if self._sha256 is None:
            h = hashlib.sha256()
            with self.path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            self._sha256 = h.hexdigest()
        return self._sha256

    def load(self) -> list[CamcisRecord]:
        if self._records is not None:
            return self._records
        if not self.path.exists():
            raise FileNotFoundError(
                f"Référentiel CAMCIS introuvable: {self.path}. "
                "CADUCEUS refuse de produire une imputation sans référentiel officiel."
            )

        df = pd.read_excel(self.path, dtype=str)
        normalized_cols = {normalize_search_text(c): c for c in df.columns}
        code_col = next((orig for norm, orig in normalized_cols.items() if "code sh" in norm or norm == "code"), None)
        label_col = next((orig for norm, orig in normalized_cols.items() if "libelle" in norm), None)
        if code_col is None or label_col is None:
            raise ValueError(f"Structure CAMCIS invalide. Colonnes trouvées: {list(df.columns)}")

        records: list[CamcisRecord] = []
        seen: set[str] = set()
        for _, row in df.iterrows():
            compact = normalize_hs_code(row.get(code_col))
            label = clean_text(row.get(label_col))
            if not compact or not label or compact in seen:
                continue
            h = hs_hierarchy(compact)
            rec = CamcisRecord(
                code_sh=compact,
                code_sh_affiche=display_hs_code(compact) or compact,
                libelle=label,
                search_text=normalize_search_text(label),
                chapter=h["chapter"],
                heading=h["heading"],
            )
            seen.add(compact)
            records.append(rec)
            self._by_code[compact] = rec

        if not records:
            raise ValueError("Le référentiel CAMCIS ne contient aucune position exploitable.")
        self._records = records
        return records

    def get(self, code: str) -> CamcisRecord | None:
        self.load()
        return self._by_code.get(normalize_hs_code(code) or "")

    def stats(self) -> dict:
        records = self.load()
        return {
            "records": len(records),
            "source_file": self.path.name,
            "sha256": self.sha256,
            "chapters": len({r.chapter for r in records if r.chapter}),
        }
