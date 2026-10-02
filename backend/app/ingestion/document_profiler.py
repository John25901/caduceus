from __future__ import annotations

from dataclasses import dataclass

from backend.app.normalization.text import normalize_search_text


@dataclass(frozen=True)
class DocumentProfile:
    kind: str
    label: str
    confidence: float
    equipment_likelihood: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "equipment_likelihood": round(self.equipment_likelihood, 3),
            "reasons": list(self.reasons),
        }


_CONTACT_MARKERS = (
    "raison sociale", "adresse", "address", "tel", "telephone", "fax",
    "email", "quartier", "societe", "company", "contact",
)

_COMMERCIAL_MARKERS = (
    "designation", "description", "article", "item", "equipment", "equipement",
    "materiel", "material", "quantity", "quantite", "qty", "qte", "unit", "unite",
    "unit price", "prix unitaire", "amount", "montant", "total", "quotation",
    "proforma", "invoice", "facture", "price", "prix",
)

_CUSTOMS_MARKERS = (
    "code sh", "hs code", "position tarifaire", "tariff code", "libelle douanier",
)

_EQUIPMENT_WORDS = (
    "machine", "machines", "equipment", "equipement", "materiel", "motor", "moteur",
    "pump", "pompe", "compressor", "compresseur", "conveyor", "convoyeur",
    "chiller", "transformer", "transformateur", "generator", "generateur",
    "oven", "four", "dryer", "sechoir", "mixer", "melangeur", "crusher", "broyeur",
    "tank", "cuve", "boiler", "chaudiere", "press", "printer", "imprimante",
    "line", "ligne", "workstation", "poste", "tool", "outillage", "cabinet", "armoire",
)


def _count(text: str, markers: tuple[str, ...]) -> int:
    return sum(text.count(normalize_search_text(m)) for m in markers)


def profile_document_text(text: str) -> DocumentProfile:
    n = normalize_search_text(text or "")
    if not n:
        return DocumentProfile(
            kind="EMPTY",
            label="Document sans texte exploitable",
            confidence=1.0,
            equipment_likelihood=0.0,
            reasons=("aucun texte détecté",),
        )

    contact_hits = _count(n, _CONTACT_MARKERS)
    commercial_hits = _count(n, _COMMERCIAL_MARKERS)
    customs_hits = _count(n, _CUSTOMS_MARKERS)
    equipment_hits = _count(n, _EQUIPMENT_WORDS)

    reasons: list[str] = []

    # Strong negative case: directories/address books often contain repeated
    # company/address/telephone blocks but no quantities/prices/equipment rows.
    if contact_hits >= 6 and commercial_hits <= 2 and equipment_hits <= 1:
        reasons.append("nombreux champs société/adresse/téléphone")
        return DocumentProfile(
            kind="DIRECTORY_CONTACTS",
            label="Annuaire / répertoire de contacts",
            confidence=min(0.99, 0.72 + contact_hits * 0.02),
            equipment_likelihood=0.02,
            reasons=tuple(reasons),
        )

    if customs_hits >= 1:
        reasons.append("vocabulaire douanier explicite")
        likelihood = min(0.99, 0.72 + 0.06 * customs_hits + 0.03 * equipment_hits)
        return DocumentProfile(
            kind="CUSTOMS_EQUIPMENT_LIST",
            label="Liste d'équipements avec informations douanières",
            confidence=likelihood,
            equipment_likelihood=likelihood,
            reasons=tuple(reasons),
        )

    if commercial_hits >= 4 and equipment_hits >= 1:
        reasons.append("colonnes commerciales détectées")
        reasons.append("vocabulaire équipement détecté")
        confidence = min(0.97, 0.62 + commercial_hits * 0.025 + equipment_hits * 0.02)
        return DocumentProfile(
            kind="COMMERCIAL_EQUIPMENT_TABLE",
            label="Proforma / devis / liste commerciale d'équipements",
            confidence=confidence,
            equipment_likelihood=min(0.99, confidence + 0.04),
            reasons=tuple(reasons),
        )

    if equipment_hits >= 3:
        reasons.append("plusieurs termes d'équipements détectés")
        confidence = min(0.92, 0.55 + equipment_hits * 0.035)
        return DocumentProfile(
            kind="EQUIPMENT_LIST",
            label="Liste d'équipements",
            confidence=confidence,
            equipment_likelihood=min(0.95, confidence + 0.05),
            reasons=tuple(reasons),
        )

    if commercial_hits >= 3:
        reasons.append("structure commerciale probable")
        return DocumentProfile(
            kind="GENERIC_COMMERCIAL_TABLE",
            label="Tableau commercial générique",
            confidence=min(0.82, 0.50 + commercial_hits * 0.035),
            equipment_likelihood=min(0.58, 0.20 + equipment_hits * 0.08),
            reasons=tuple(reasons),
        )

    if contact_hits >= 3:
        reasons.append("plusieurs champs de contact détectés")
        return DocumentProfile(
            kind="DIRECTORY_CONTACTS",
            label="Annuaire / répertoire de contacts",
            confidence=min(0.90, 0.55 + contact_hits * 0.04),
            equipment_likelihood=0.05,
            reasons=tuple(reasons),
        )

    reasons.append("structure insuffisamment caractérisée")
    return DocumentProfile(
        kind="GENERIC_DOCUMENT",
        label="Document générique",
        confidence=0.45,
        equipment_likelihood=min(0.45, equipment_hits * 0.08 + commercial_hits * 0.04),
        reasons=tuple(reasons),
    )
