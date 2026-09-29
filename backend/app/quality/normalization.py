from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.models.domain import EquipmentItem

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


@dataclass(frozen=True)
class FinancialResult:
    unit_price_xaf: float | None
    total_price_xaf: float | None
    exchange_rate_xaf: float | None
    status: str
    note: str | None


def sanitize_professional_text(value: str | None) -> tuple[str | None, bool]:
    """Keep French/English/Latin content; never invent a translation.

    Returns (sanitized_text, foreign_text_suppressed). CJK source text remains
    available in raw_fields/audit but is not exposed in the professional sheet.
    """
    if not value:
        return None, False
    text = str(value).strip()
    if not _CJK_RE.search(text):
        return text, False
    cleaned = _CJK_RUN_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|,;:/")
    latin_count = len(re.findall(r"[A-Za-zÀ-ÿ]", cleaned))
    if latin_count < 2:
        return None, True
    return cleaned, True


def normalize_financials(item: EquipmentItem, exchange_rate_xaf: float | None = None) -> FinancialResult:
    """Normalize prices to XAF conservatively.

    - XAF source -> rate 1.
    - Foreign source -> caller must provide a positive XAF exchange rate.
    - Missing unit/total can be deterministically derived from qty.
    - Existing inconsistent unit/total pairs are flagged; no silent overwrite.
    """
    qty = item.quantite
    source_unit = item.prix_unitaire
    source_total = item.prix_total
    currency = (item.devise or "").upper().strip() or None

    if currency in {"XAF", "FCFA", "CFA"}:
        rate = 1.0
    elif currency is None:
        # Do not pretend an unidentified supplier currency is XAF.
        rate = None if (source_unit is not None or source_total is not None) else 1.0
    else:
        rate = float(exchange_rate_xaf) if exchange_rate_xaf and exchange_rate_xaf > 0 else None

    if rate is None:
        return FinancialResult(None, None, None, "TAUX_REQUIS", f"Conversion {currency or 'devise source inconnue'} -> XAF requise.")

    unit_xaf = source_unit * rate if source_unit is not None else None
    total_xaf = source_total * rate if source_total is not None else None

    if qty is not None and qty > 0:
        if unit_xaf is None and total_xaf is not None:
            unit_xaf = total_xaf / qty
            return FinancialResult(unit_xaf, total_xaf, rate, "UNITE_DERIVEE", "Prix unitaire XAF calculé à partir du total et de la quantité.")
        if total_xaf is None and unit_xaf is not None:
            total_xaf = qty * unit_xaf
            return FinancialResult(unit_xaf, total_xaf, rate, "TOTAL_DERIVE", "Prix total XAF calculé à partir de la quantité et du prix unitaire.")
        if unit_xaf is not None and total_xaf is not None:
            expected = qty * unit_xaf
            tolerance = max(1.0, abs(total_xaf) * 0.005)
            if abs(expected - total_xaf) > tolerance:
                return FinancialResult(unit_xaf, expected, rate, "INCOHERENT_SOURCE", "Écart détecté entre le total source et Quantité x Prix unitaire ; le total harmonisé est recalculé.")
            return FinancialResult(unit_xaf, expected, rate, "OK", None)

    return FinancialResult(unit_xaf, total_xaf, rate, "INCOMPLET", "Quantité ou prix insuffisant pour contrôler le total.")


def apply_professional_normalization(item: EquipmentItem, exchange_rate_xaf: float | None = None) -> EquipmentItem:
    # Keep the source designation intact for retrieval. Professional sanitation is
    # currently applied to specifications only; this avoids destroying useful
    # multilingual evidence while ensuring the exported operational sheet does not
    # expose Chinese-only technical text.
    specs_original = item.specifications
    specs, specs_suppressed = sanitize_professional_text(specs_original)
    _, designation_suppressed = sanitize_professional_text(item.designation_source)
    if designation_suppressed:
        item.raw_fields["designation_originale"] = item.designation_source
        item.raw_fields["foreign_text_suppressed"] = True
    if specs_suppressed:
        item.raw_fields["specifications_originales"] = specs_original
        item.raw_fields["foreign_text_suppressed"] = True
        item.specifications = specs

    item.devise_source = item.devise
    item.prix_unitaire_source = item.prix_unitaire
    item.prix_total_source = item.prix_total

    f = normalize_financials(item, exchange_rate_xaf=exchange_rate_xaf)
    item.taux_change_xaf = f.exchange_rate_xaf
    item.prix_unitaire_xaf = f.unit_price_xaf
    item.prix_total_xaf = f.total_price_xaf
    item.statut_prix = f.status
    item.note_prix = f.note
    return item

