from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from rapidfuzz import fuzz

from backend.app.models.domain import EquipmentItem
from backend.app.normalization.text import normalize_search_text


@dataclass(frozen=True)
class ProjectProfile:
    key: str | None
    label: str
    confidence: float
    source: str
    sector_text: str
    description_text: str


@dataclass(frozen=True)
class SectorAssessment:
    status: str
    risk: str
    score: float | None
    comment: str


_PROFILES = {
    "PAPER_PACKAGING": {
        "label": "Papier, carton et emballage",
        "keywords": [
            "papier", "carton", "alveole", "alvéole", "egg tray", "corrugated", "cardboard", "pulp", "pate a papier",
            "moulage", "moule", "sechoir", "séchoir", "flexographique", "slotter", "plieuse", "colleuse", "glue",
            "refendeuse", "onduleuse", "corrugator", "paper rack", "preheater", "stacker", "box maker", "stitcher",
            "agitateur", "tamis", "epurateur", "épurateur", "raffineur", "dosage", "banderoleuse", "filmeuse", "banc de test",
            "collage", "pressage", "poinconneuse", "poinçonneuse", "perforatrice", "decoupeuse", "découpeuse", "aspiration",
            "outillage", "derouleur", "dérouleur", "rainureuse", "couture", "agrafage", "mise a plat", "mise à plat", "empilage",
            "cliche", "cliché", "slitting", "creasing", "knife", "glue station", "steam system", "air source system",
            "preheating", "corrugating", "conveying bridge", "double sided", "double-sided", "transverse cutting",
        ],
    },
    "SOLAR_PV": {
        "label": "Solaire photovoltaïque",
        "keywords": [
            "solar", "solaire", "photovolta", "cellule", "cell", "topcon", "eva", "poe", "junction box", "back sheet",
            "laminator", "stringer", "glass loader", "module", "panel", "panneau", "ribbon", "busbar", "frame aluminium",
        ],
    },
    "BTP": {
        "label": "BTP, construction et structures",
        "keywords": [
            "construction", "btp", "steel", "acier", "beam", "poutre", "column", "colonne", "purlin", "charpente",
            "crane", "grue", "concrete", "beton", "béton", "excavator", "bulldozer", "loader", "pelle", "road", "route",
            "bolt", "boulon", "roof", "toiture", "panel sandwich", "shutter door",
        ],
    },
    "HOSPITALITY": {
        "label": "Hôtellerie, tourisme, loisirs et événementiel",
        "keywords": [
            "hotel", "hôtel", "restaurant", "piscine", "pool", "event", "événement", "tourisme", "loisir", "lighting",
            "luminaire", "led", "kitchen", "cuisine", "furniture", "mobilier", "room", "chambre", "spa", "bar",
        ],
    },
    "AGRO": {
        "label": "Agro-industrie et transformation alimentaire",
        "keywords": [
            "agro", "food", "aliment", "grain", "maize", "mais", "maïs", "milling", "mill", "poultry", "avicole",
            "cold room", "chambre froide", "processing", "pasteur", "filling", "packaging", "oil press", "rice", "flour",
        ],
    },
    "ENERGY": {
        "label": "Énergie et électricité",
        "keywords": [
            "electric", "électri", "energy", "énergie", "generator", "groupe electrogene", "transformer", "transformateur",
            "inverter", "onduleur", "cable", "câble", "switchgear", "battery", "batterie", "substation", "poste électrique",
        ],
    },
}

# Industrial support items may be directly justifiable across many sectors. We do
# not call them inconsistent merely because the project description does not name them.
_UNIVERSAL_SUPPORT = [
    "compressor", "compresseur", "pump", "pompe", "conveyor", "convoyeur", "forklift", "chariot elevateur",
    "gerbeur", "transpalette", "generator", "groupe electrogene", "transformer", "transformateur", "electrical cabinet",
    "armoire electrique", "water treatment", "traitement d eau", "boiler", "chaudiere", "laboratoire", "lab", "balance",
    "rack", "rayonnage", "warehouse", "stockage", "fire", "incendie", "air dryer", "secheur d air", "vacuum", "vide",
    "pneumatic", "pneumatique", "spare", "rechange", "bearing", "roulement", "motor", "moteur", "sensor", "capteur",
    "agitateur", "tamis", "epurateur", "épurateur", "raffineur", "dosage", "compteur", "banderoleuse", "filmeuse",
    "banc de test", "pupitre", "commande", "supervision", "automatisme", "variateur", "aspiration", "outillage",
    "reservoir", "réservoir", "tuyauterie", "palette", "pallet", "table elevatrice", "table élévatrice", "porte sectionnelle",
    "pesage", "bascule", "codification", "identification de stocks", "diable", "rampe", "courroie", "chaine", "chaîne",
    "joint technique", "lame", "couteau", "crane", "grue", "steel column", "beam", "purlin", "tie rod", "bracing",
    "bolt", "boulon", "sandwich panel", "roof", "toiture", "wall", "shutter door", "window", "fenetre", "fenêtre",
    "electrical control", "armoire de distribution", "reseau", "réseau", "air source", "steam system", "banc d essai",
    "ordinateur industriel", "etiquetage", "étiquetage", "bac industriel", "bacs industriels", "table elevatrice", "tables elevatrices", "chariot elevateur", "chariots elevateurs", "porte sectionnelle", "portes sectionnelles",
    "joint", "corner brace", "edge trim", "cable electrique", "cable électrique", "disjoncteur",
]


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", normalize_search_text(text)) if len(x) >= 3}


def infer_project_profile(items: Iterable[EquipmentItem], sector: str = "", description: str = "") -> ProjectProfile:
    explicit = f"{sector} {description}".strip()
    corpus = explicit or " ".join((x.designation_source + " " + (x.specifications or "")) for x in items)
    norm = normalize_search_text(corpus)
    if not norm:
        return ProjectProfile(None, "Profil non déterminé", 0.0, "insufficient_context", sector, description)

    scores: list[tuple[float, str]] = []
    for key, cfg in _PROFILES.items():
        hits = 0.0
        for kw in cfg["keywords"]:
            nkw = normalize_search_text(kw)
            if nkw and nkw in norm:
                hits += 1.0
            elif explicit and fuzz.partial_ratio(nkw, normalize_search_text(explicit)) >= 88:
                hits += 0.5
        scores.append((hits, key))
    scores.sort(reverse=True)
    best_score, best_key = scores[0]
    second = scores[1][0] if len(scores) > 1 else 0.0
    if best_score <= 0:
        return ProjectProfile(None, "Profil non déterminé", 0.0, "no_match", sector, description)
    # Confidence reflects dominance, not legal certainty.
    confidence = min(0.98, 0.45 + 0.08 * best_score + 0.05 * max(0.0, best_score - second))
    source = "user_context" if explicit else "inferred_from_equipment_list"
    return ProjectProfile(best_key, _PROFILES[best_key]["label"], round(confidence, 3), source, sector, description)


def assess_sector(item: EquipmentItem, profile: ProjectProfile) -> SectorAssessment:
    if profile.key is None:
        return SectorAssessment("NON_EVALUEE", "NON_EVALUE", None, "Contexte sectoriel insuffisant : renseigner l’activité ou le process pour une analyse fiable.")

    text = normalize_search_text(f"{item.designation_source} {item.specifications or ''}")
    cfg = _PROFILES[profile.key]
    direct_hits = [kw for kw in cfg["keywords"] if normalize_search_text(kw) in text]
    support_hits = [kw for kw in _UNIVERSAL_SUPPORT if normalize_search_text(kw) in text]

    # Compare against explicit project text as a supplementary, explainable signal.
    project_text = normalize_search_text(f"{profile.sector_text} {profile.description_text}")
    project_similarity = fuzz.token_set_ratio(text, project_text) / 100.0 if project_text else 0.0

    if direct_hits:
        score = min(0.99, 0.82 + 0.03 * min(len(direct_hits), 5))
        return SectorAssessment(
            "COHERENT", "FAIBLE", round(score, 3),
            f"Lien direct identifié avec le profil « {profile.label} » ({', '.join(direct_hits[:3])}).",
        )
    if support_hits:
        return SectorAssessment(
            "JUSTIFIABLE", "MODERE", 0.72,
            f"Équipement d’utilité/support industriel ({', '.join(support_hits[:3])}) ; son lien fonctionnel avec le process doit être conservé dans l’argumentaire.",
        )
    if project_similarity >= 0.62:
        return SectorAssessment(
            "COHERENT", "FAIBLE", round(project_similarity, 3),
            "La désignation est cohérente avec le contexte projet décrit par l’utilisateur.",
        )

    return SectorAssessment(
        "A_EXAMINER", "MODERE", round(project_similarity, 3),
        f"Aucun lien sectoriel direct n’a été démontré automatiquement avec le profil « {profile.label} ». Vérification métier ciblée recommandée, sans conclure à une non-éligibilité.",
    )
