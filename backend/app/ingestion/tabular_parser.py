from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from backend.app.models.domain import EquipmentItem
from backend.app.normalization.text import clean_text, normalize_hs_code, normalize_search_text


FIELD_SYNONYMS = {
    "order": ["n d ordre", "n° d ordre", "numero d ordre", "numéro d ordre", "no", "n°", "numero", "numéro", "serial", "sn", "s/n"],
    "designation": ["designation", "désignation", "description", "equipement", "équipement", "equipment", "materiel", "matériel", "material", "article", "item", "name", "nom", "produit", "goods description"],
    "specifications": ["specification", "specifications", "spec", "caracteristique", "caracteristiques", "technical description"],
    "quantity": ["quantite", "quantité", "quantity", "qty", "qte"],
    "unit": ["unite", "unit", "uom"],
    "unit_price": ["prix unitaire", "unit price", "price usd", "price eur", "price xaf", "pu"],
    "total_price": ["prix total", "total price", "amount", "amount usd", "amount eur", "amount xaf", "montant", "valeur totale", "fob en devise"],
    "origin": ["origine", "origin", "pays origine", "country of origin"],
    "hs_code": ["code sh", "hs code", "position tarifaire", "pos tarifaire", "pos. tarifaire", "tariff code"],
    "customs_label": ["libelle douanier", "customs label", "tariff description"],
}

HEADER_TOKENS = sorted({s for values in FIELD_SYNONYMS.values() for s in values})


def _header_cell_score(value: object) -> float:
    text = normalize_search_text(value)
    if not text:
        return 0.0
    score = 0.0
    for token in HEADER_TOKENS:
        nt = normalize_search_text(token)
        if text == nt:
            score = max(score, 3.0)
        elif nt in text or text in nt:
            score = max(score, 1.5)
    return score


def detect_header_row(preview: pd.DataFrame) -> tuple[int, float]:
    best_idx, best_score = 0, -1.0
    for idx in range(min(len(preview), 30)):
        values = preview.iloc[idx].tolist()
        score = sum(_header_cell_score(v) for v in values)
        # Reward rows containing multiple distinct field types.
        joined = " | ".join(normalize_search_text(v) for v in values if clean_text(v))
        matched_fields = sum(any(normalize_search_text(s) in joined for s in synonyms) for synonyms in FIELD_SYNONYMS.values())
        score += matched_fields * 0.8
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx, best_score


def _map_columns(columns: list[object]) -> dict[str, object]:
    out: dict[str, object] = {}
    normalized = {c: normalize_search_text(c) for c in columns}
    for field, synonyms in FIELD_SYNONYMS.items():
        best = None
        best_score = 0
        for col, norm in normalized.items():
            for syn in synonyms:
                ns = normalize_search_text(syn)
                if field == "order":
                    score = 3 if norm == ns and len(ns) >= 1 else 0
                else:
                    score = 3 if norm == ns else 2 if ns and ns in norm else 0
                if field == "unit" and ("price" in norm or "ligne" in norm or "concern" in norm):
                    score = 0
                # Cameroon professional output is XAF: when a workbook exposes both
                # supplier currency and FCFA columns, prefer the XAF monetary columns.
                if field in {"unit_price", "total_price"} and score > 0:
                    if any(tag in norm for tag in ("xaf", "fcfa", "cfa")):
                        score += 3
                    elif any(tag in norm for tag in ("usd", "eur", "euro", "dollar")):
                        score += 0.5
                if score > best_score:
                    best, best_score = col, score
        if best is not None and best_score > 0:
            out[field] = best
    return out


def _to_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value)
    if not text:
        return None
    # tolerate spaces and comma decimals
    text = re.sub(r"[^0-9,.-]", "", text)
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(",") > 0 and text.count(".") > 0:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None



def _infer_unit_from_quantity(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    m = re.search(r"[0-9.,\s]+\s*([A-Za-zÀ-ÿ²³]+)$", text)
    return m.group(1) if m else None

def _infer_currency(column_name: object) -> str | None:
    n = normalize_search_text(column_name)
    if any(x in n for x in ["fcfa", "x af", "xaf", "cfa"]):
        return "XAF"
    if "usd" in n or "dollar" in n:
        return "USD"
    if "eur" in n or "euro" in n:
        return "EUR"
    return None


@dataclass
class ParsedTable:
    items: list[EquipmentItem]
    source_sheet: str | None
    header_row: int
    header_score: float
    column_mapping: dict[str, str]
    warnings: list[str]


class TabularEquipmentParser:
    def parse_path(self, path: str | Path) -> ParsedTable:
        path = Path(path)
        with path.open("rb") as f:
            return self.parse_bytes(f.read(), path.name)

    def parse_bytes(self, data: bytes, filename: str) -> ParsedTable:
        lower = filename.lower()
        if lower.endswith((".xlsx", ".xls")):
            return self._parse_excel(data, filename)
        if lower.endswith((".csv", ".txt")):
            return self._parse_csv(data, filename)
        raise ValueError(f"Format tabulaire non pris en charge dans V2: {filename}")

    def _parse_excel(self, data: bytes, filename: str) -> ParsedTable:
        bio = io.BytesIO(data)
        xls = pd.ExcelFile(bio)
        best = None
        for sheet in xls.sheet_names:
            preview = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=30, dtype=object)
            idx, score = detect_header_row(preview)
            if best is None or score > best[2]:
                best = (sheet, idx, score)
        if best is None:
            raise ValueError("Aucune feuille Excel lisible.")
        sheet, header_idx, header_score = best
        df = pd.read_excel(xls, sheet_name=sheet, header=header_idx, dtype=object)
        return self._build_items(df, filename, sheet, header_idx, header_score, extraction_method="EXCEL")

    def _parse_csv(self, data: bytes, filename: str) -> ParsedTable:
        text = data.decode("utf-8-sig", errors="replace")
        preview = pd.read_csv(io.StringIO(text), header=None, nrows=30, sep=None, engine="python", dtype=object)
        header_idx, header_score = detect_header_row(preview)
        df = pd.read_csv(io.StringIO(text), header=header_idx, sep=None, engine="python", dtype=object)
        return self._build_items(df, filename, None, header_idx, header_score, extraction_method="CSV/TXT")

    def parse_dataframe(
        self,
        df: pd.DataFrame,
        filename: str,
        *,
        source_sheet: str | None = None,
        source_page: int | None = None,
        header_idx: int | None = None,
        header_score: float | None = None,
        extraction_method: str = "TABLE",
    ) -> ParsedTable:
        if df.empty:
            raise ValueError("Table vide.")
        if header_idx is None or header_score is None:
            preview = df.head(30).reset_index(drop=True)
            header_idx, header_score = detect_header_row(preview)
            header = [clean_text(v) or f"col_{i+1}" for i, v in enumerate(preview.iloc[header_idx].tolist())]
            data = preview.iloc[header_idx + 1 :].copy() if len(df) <= 30 else df.iloc[header_idx + 1 :].copy()
            data.columns = header
            data = data.reset_index(drop=True)
        else:
            data = df
        return self._build_items(
            data, filename, source_sheet, header_idx, header_score,
            source_page=source_page, extraction_method=extraction_method,
        )

    def _build_items(
        self,
        df: pd.DataFrame,
        filename: str,
        sheet: str | None,
        header_idx: int,
        header_score: float,
        *,
        source_page: int | None = None,
        extraction_method: str = "TABLE",
    ) -> ParsedTable:
        mapping = _map_columns(list(df.columns))
        warnings: list[str] = []
        if "designation" not in mapping:
            raise ValueError(
                "Impossible d'identifier la colonne Désignation/Description. "
                f"Colonnes détectées: {[str(c) for c in df.columns]}"
            )
        if header_score < 3.0:
            warnings.append(f"Confiance faible sur la ligne d'en-tête (score={header_score:.2f}).")

        currency = None
        if "total_price" in mapping:
            currency = _infer_currency(mapping["total_price"])
        if currency is None and "unit_price" in mapping:
            currency = _infer_currency(mapping["unit_price"])

        items: list[EquipmentItem] = []
        for ridx, row in df.iterrows():
            designation = clean_text(row.get(mapping["designation"]))
            if not designation:
                continue
            nd = normalize_search_text(designation)
            if any(k in nd for k in ["sous total", "subtotal", "total general", "grand total", "quotation file"]):
                continue
            if "total" in nd and any(k in nd for k in ["fob", "cif", "exw", "amount", "price"]):
                continue
            # Skip accidental repeated header rows.
            if _header_cell_score(designation) >= 2.5:
                continue

            specs = clean_text(row.get(mapping.get("specifications"))) if mapping.get("specifications") is not None else ""
            raw = {str(c): (None if pd.isna(row.get(c)) else row.get(c)) for c in df.columns}
            item = EquipmentItem(
                source_document=filename,
                source_sheet=sheet,
                source_row=(
                    int(_to_float(row.get(mapping.get("order"))))
                    if source_page is not None and mapping.get("order") is not None and _to_float(row.get(mapping.get("order"))) is not None
                    else (int(ridx) + header_idx + 2 if source_page is None else None)
                ),
                source_page=source_page,
                extraction_method=extraction_method,
                designation_source=designation,
                designation_normalisee=nd,
                specifications=specs or None,
                quantite=_to_float(row.get(mapping.get("quantity"))) if mapping.get("quantity") is not None else None,
                unite=(
                    (clean_text(row.get(mapping.get("unit"))) or None)
                    if mapping.get("unit") is not None
                    else (_infer_unit_from_quantity(row.get(mapping.get("quantity"))) if mapping.get("quantity") is not None else None)
                ),
                prix_unitaire=_to_float(row.get(mapping.get("unit_price"))) if mapping.get("unit_price") is not None else None,
                prix_total=_to_float(row.get(mapping.get("total_price"))) if mapping.get("total_price") is not None else None,
                devise=currency,
                origine=clean_text(row.get(mapping.get("origin"))) or None if mapping.get("origin") is not None else None,
                code_sh_source=normalize_hs_code(row.get(mapping.get("hs_code"))) if mapping.get("hs_code") is not None else None,
                libelle_douanier_source=clean_text(row.get(mapping.get("customs_label"))) or None if mapping.get("customs_label") is not None else None,
                extraction_confidence=1.0 if header_score >= 5.0 else 0.8,
                raw_fields=raw,
            )
            # Preserve deterministic monetary relationships at ingestion time.
            # For schedules that only provide a line total, derive unit price from
            # quantity; for quotations that omit total, derive it from quantity x unit.
            if item.quantite is not None and item.quantite > 0:
                if item.prix_unitaire is None and item.prix_total is not None:
                    item.prix_unitaire = item.prix_total / item.quantite
                    item.raw_fields["prix_unitaire_derive"] = True
                elif item.prix_total is None and item.prix_unitaire is not None:
                    item.prix_total = item.quantite * item.prix_unitaire
                    item.raw_fields["prix_total_derive"] = True
            items.append(item)

        return ParsedTable(
            items=items,
            source_sheet=sheet,
            header_row=header_idx,
            header_score=header_score,
            column_mapping={k: str(v) for k, v in mapping.items()},
            warnings=warnings,
        )
