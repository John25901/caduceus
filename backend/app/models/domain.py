from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class EquipmentItem(BaseModel):
    source_document: str
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_page: Optional[int] = None
    extraction_method: Optional[str] = None

    designation_source: str
    designation_normalisee: str
    specifications: Optional[str] = None
    marque: Optional[str] = None
    modele: Optional[str] = None

    quantite: Optional[float] = None
    unite: Optional[str] = None

    # Monetary values read from the source document.
    prix_unitaire: Optional[float] = None
    prix_total: Optional[float] = None
    devise: Optional[str] = None

    # Professional normalized values for the Cameroon context.
    prix_unitaire_source: Optional[float] = None
    prix_total_source: Optional[float] = None
    devise_source: Optional[str] = None
    taux_change_xaf: Optional[float] = None
    prix_unitaire_xaf: Optional[float] = None
    prix_total_xaf: Optional[float] = None
    statut_prix: Optional[str] = None
    note_prix: Optional[str] = None

    origine: Optional[str] = None

    code_sh_source: Optional[str] = None
    libelle_douanier_source: Optional[str] = None
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class TariffCandidate(BaseModel):
    code_sh: str
    code_sh_affiche: str
    libelle_douanier: str
    chapter: Optional[str] = None
    heading: Optional[str] = None
    lexical_score: float = 0.0
    vector_score: Optional[float] = None
    history_score: Optional[float] = None
    history_sources: list[str] = Field(default_factory=list)
    combined_score: float = 0.0
    rank: int


class TariffAssessment(BaseModel):
    item: EquipmentItem
    candidats: list[TariffCandidate]
    code_sh_propose: Optional[str] = None
    libelle_propose: Optional[str] = None
    score_retrieval: Optional[float] = None
    statut_tarifaire: Literal[
        "CONFIRME_SOURCE",
        "CONFIRME_MEMOIRE",
        "PROPOSITION",
        "PROPOSITION_ARBITREE",
        "A_REVOIR",
        "NON_CLASSE",
    ]
    motif_decision: str
    mode_recherche: str

    arbitrage_ia_statut: str = "NON_REQUIS"
    arbitrage_ia_provider: Optional[str] = None
    arbitrage_ia_model: Optional[str] = None
    arbitrage_ia_confidence: Optional[float] = None
    arbitrage_ia_commentaire: Optional[str] = None
    arbitrage_ia_latency_ms: Optional[float] = None
    arbitrage_ia_cache_hit: bool = False

    pertinence_sectorielle: Literal[
        "COHERENT",
        "JUSTIFIABLE",
        "A_EXAMINER",
        "NON_EVALUEE",
    ] = "NON_EVALUEE"
    niveau_risque: Literal["FAIBLE", "MODERE", "ELEVE", "NON_EVALUE"] = "NON_EVALUE"
    commentaire_sectoriel: str = "Analyse sectorielle non exécutée."
    score_sectoriel: Optional[float] = None
