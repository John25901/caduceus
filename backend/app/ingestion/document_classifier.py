from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.normalization.text import normalize_search_text


@dataclass(frozen=True)
class DocumentProfile:
    kind: str
    label: str
    confidence: float
    equipment_likelihood: float
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "equipment_likelihood": round(self.equipment_likelihood, 3),
            "reasons": list(self.reasons),
        }


_CONTACT_TERMS = (
    "raison sociale", "adresse", "address", "tel", "telephone", "phone",
    "fax", "email", "e mail", "contact", "quartier", "societe", "company",
)
_COMMERCIAL_TERMS = (
    "proforma", "invoice", "quotation", "quote", "devis", "unit price",
    "prix unitaire", "amount", "montant", "quantity", "quantite", "qty", "qte",
    "total price", "prix total", "fob", "cif", "exw",
)
_EQUIPMENT_HEADER_TERMS = (
    "designation", "description", "equipment", "equipement", "materiel",
    "material", "article", "item", "goods description", "product name",
)
_EQUIPMENT_TERMS = (
    "machine", "machinery", "equipment", "equipement", "materiel", "line",
    "ligne", "conveyor", "convoyeur", "pump", "pompe", "motor", "moteur",
    "compressor", "compresseur", "mixer", "melangeur", "crusher", "broyeur",
    "transformer", "transformateur", "generator", "generateur", "chiller",
    "boiler", "chaudiere", "dryer", "sechoir", "tank", "cuve", "furnace",
    "four", "loader", "chargeur", "press", "mould", "mold", "moule",
    "printer", "imprimante", "panel", "panneau", "cabinet", "armoire",
    "sensor", "capteur", "valve", "vanne", "filter", "filtre", "solar cell",
    "junction box", "back sheet", "inverter", "onduleur", "battery", "batterie",
)
_HS_TERMS = ("code sh", "hs code", "position tarifaire", "libelle douanier", "tariff code")


def _hits(text: str, terms: tuple[str, ...]) -> int:
    return sum(text.count(term) for term in terms)


def classify_document(text: str) -> DocumentProfile:
    n = normalize_search_text(text or "")
    if not n:
        return DocumentProfile("EMPTY", "Document vide ou illisible", 0.99, 0.0, ("aucun texte exploitable",))

    contact = _hits(n, _CONTACT_TERMS)
    commercial = _hits(n, _COMMERCIAL_TERMS)
    headers = _hits(n, _EQUIPMENT_HEADER_TERMS)
    equipment = _hits(n, _EQUIPMENT_TERMS)
    hs = _hits(n, _HS_TERMS)
    numbered = len(re.findall(r"(?m)^\s*\d{1,4}\s*[.)-]?\s+", text or ""))
    lines = max(1, len([x for x in (text or "").splitlines() if x.strip()]))

    reasons: list[str] = []
    if contact >= 5 and equipment <= 1 and commercial <= 1:
        reasons.append("forte densité de coordonnées/contacts")
        return DocumentProfile("CONTACT_DIRECTORY", "Annuaire / liste de contacts", 0.96, 0.02, tuple(reasons))

    if hs >= 1 and (headers >= 1 or numbered >= 2):
        reasons.append("présence d'un vocabulaire tarifaire")
        return DocumentProfile("CUSTOMS_EQUIPMENT_LIST", "Liste d'équipements déjà tarifée", 0.94, 0.98, tuple(reasons))

    if commercial >= 3 and (headers >= 1 or equipment >= 1):
        reasons.append("structure commerciale et désignations détectées")
        return DocumentProfile("PROFORMA_OR_QUOTATION", "Proforma / devis fournisseur", 0.90, 0.94, tuple(reasons))

    if headers >= 1 and (numbered >= 2 or equipment >= 1):
        reasons.append("en-tête d'articles/équipements détecté")
        return DocumentProfile("EQUIPMENT_LIST", "Liste d'équipements", 0.88, 0.92, tuple(reasons))

    if equipment >= 3:
        reasons.append("plusieurs termes d'équipements détectés")
        return DocumentProfile("EQUIPMENT_LIST", "Liste d'équipements", 0.78, 0.86, tuple(reasons))

    if numbered >= 3 and (commercial >= 1 or equipment >= 1):
        reasons.append("lignes numérotées avec contexte matériel/commercial")
        return DocumentProfile("EQUIPMENT_LIST", "Liste d'équipements", 0.72, 0.76, tuple(reasons))

    if contact >= 3 and contact > equipment + commercial:
        reasons.append("coordonnées plus fréquentes que les éléments matériels")
        return DocumentProfile("CONTACT_DIRECTORY", "Annuaire / liste de contacts", 0.82, 0.08, tuple(reasons))

    # Generic table-like OCR: many short lines but no reliable equipment semantics.
    avg_len = len(n) / lines
    if lines >= 8 and avg_len < 90:
        reasons.append("structure tabulaire/textuelle détectée sans schéma équipement fiable")
        return DocumentProfile("GENERIC_TABLE", "Tableau générique", 0.66, 0.25, tuple(reasons))

    return DocumentProfile("UNKNOWN", "Document non classé", 0.55, 0.20, ("structure métier insuffisante",))


def looks_like_equipment_text(text: str) -> bool:
    return classify_document(text).equipment_likelihood >= 0.70
