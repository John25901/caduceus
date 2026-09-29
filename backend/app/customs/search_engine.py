from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.customs.camcis_repository import CamcisRepository
from backend.app.customs.history_repository import ValidatedCaseMemory
from backend.app.customs.lexical_search import LexicalTariffSearch
from backend.app.customs.vector_search import OptionalVectorTariffSearch
from backend.app.models.domain import TariffCandidate


class HybridTariffEngine:
    def __init__(self, repo: CamcisRepository, settings: Settings, use_history: bool = True, semantic_collection: str | None = None):
        records = repo.load()
        self.repo = repo
        self.settings = settings
        self.lexical = LexicalTariffSearch(records)
        self.history = ValidatedCaseMemory(settings.validated_cases_path, settings.user_validated_cases_path) if use_history else None
        by_code = {r.code_sh: r for r in records}
        self.vector = None
        if settings.enable_semantic:
            self.vector = OptionalVectorTariffSearch(
                records_by_code=by_code,
                storage_path=settings.qdrant_path,
                collection=semantic_collection,
                model_name=settings.embedding_model,
            )

    def reload_history(self) -> None:
        if self.history is not None:
            self.history = ValidatedCaseMemory(self.settings.validated_cases_path, self.settings.user_validated_cases_path)

    @property
    def mode(self) -> str:
        pieces = ["LEXICAL"]
        if self.vector is not None and self.vector.available:
            pieces.append("SEMANTIQUE")
        if self.history is not None and self.history.count:
            pieces.append("MEMOIRE_VALIDEE")
        return "HYBRIDE_" + "_".join(pieces)

    def search(self, designation: str, top_k: int = 5, include_history: bool = True) -> list[TariffCandidate]:
        limit_pool = max(top_k * 5, 20)
        lexical_hits = self.lexical.search(designation, limit=limit_pool)
        vector_hits = self.vector.search(designation, limit=limit_pool) if self.vector is not None else []
        history_hits = self.history.search(designation, limit=limit_pool) if (include_history and self.history is not None) else []

        lex = {h.record.code_sh: h for h in lexical_hits}
        vec = {h.record.code_sh: h for h in vector_hits}
        hist: dict[str, tuple[float, list[str]]] = {}
        for h in history_hits:
            if self.repo.get(h.code_sh) is None:
                continue
            score, sources = hist.get(h.code_sh, (0.0, []))
            if h.score > score:
                score = h.score
            if h.source_file not in sources:
                sources.append(h.source_file)
            hist[h.code_sh] = (score, sources)

        codes = set(lex) | set(vec) | set(hist)
        candidates = []
        semantic_on = bool(vector_hits)
        history_on = bool(history_hits)
        for code in codes:
            rec = self.repo.get(code)
            if rec is None:
                continue
            ls = lex.get(code).score if code in lex else 0.0
            vs = vec.get(code).score if code in vec else None
            hs, sources = hist.get(code, (0.0, []))
            if semantic_on and history_on:
                vs01 = max(0.0, min(1.0, float(vs or 0.0)))
                combined = 0.50 * hs + 0.30 * vs01 + 0.20 * ls
            elif semantic_on:
                vs01 = max(0.0, min(1.0, float(vs or 0.0)))
                combined = 0.55 * vs01 + 0.45 * ls
            elif history_on:
                combined = 0.88 * hs + 0.12 * ls
            else:
                combined = ls
            candidates.append((combined, ls, vs, hs, sources, rec))

        candidates.sort(key=lambda x: x[0], reverse=True)
        out: list[TariffCandidate] = []
        for rank, (combined, ls, vs, hs, sources, rec) in enumerate(candidates[:top_k], start=1):
            out.append(TariffCandidate(
                code_sh=rec.code_sh,
                code_sh_affiche=rec.code_sh_affiche,
                libelle_douanier=rec.libelle,
                chapter=rec.chapter,
                heading=rec.heading,
                lexical_score=round(float(ls), 4),
                vector_score=round(float(vs), 4) if vs is not None else None,
                history_score=round(float(hs), 4) if hs > 0 else None,
                history_sources=sources,
                combined_score=round(float(combined), 4),
                rank=rank,
            ))
        return out


    def decide_for_item(self, item, candidates: list[TariffCandidate]) -> tuple[str | None, str | None, float | None, str, str]:
        """Prefer validated structured evidence before heuristic retrieval.

        A source HS code that exists in CAMCIS is not sent back to 170 manual
        reviews merely because the retrieval score is conservative. CADUCEUS
        normalizes its official label and keeps retrieval as a hidden cross-check.
        """
        source_code = getattr(item, "code_sh_source", None)
        if source_code:
            rec = self.repo.get(source_code)
            if rec is not None:
                return (
                    rec.code_sh,
                    rec.libelle,
                    1.0,
                    "CONFIRME_SOURCE",
                    "Position présente dans le document source et confirmée dans le référentiel CAMCIS ; libellé officiel CAMCIS appliqué.",
                )

        if candidates:
            first = candidates[0]
            if (first.history_score or 0.0) >= 0.97 and self.repo.get(first.code_sh) is not None:
                return (
                    first.code_sh,
                    first.libelle_douanier,
                    first.combined_score,
                    "CONFIRME_MEMOIRE",
                    "Correspondance quasi exacte avec un précédent humain validé et code confirmé dans CAMCIS.",
                )
        return self.decide(candidates)

    def close(self) -> None:
        if self.vector is not None:
            self.vector.close()

    def decide(self, candidates: list[TariffCandidate]) -> tuple[str | None, str | None, float | None, str, str]:
        if not candidates:
            return None, None, None, "NON_CLASSE", "Aucun candidat CAMCIS récupéré."
        first = candidates[0]
        second_score = candidates[1].combined_score if len(candidates) > 1 else 0.0
        margin = first.combined_score - second_score
        if first.combined_score >= self.settings.auto_accept_score and margin >= self.settings.min_margin:
            return (
                first.code_sh,
                first.libelle_douanier,
                first.combined_score,
                "PROPOSITION",
                f"Top-1 au-dessus du seuil heuristique avec marge {margin:.3f}. Validation humaine requise avant usage officiel.",
            )
        return (
            first.code_sh,
            first.libelle_douanier,
            first.combined_score,
            "A_REVOIR",
            f"Candidat principal conservé pour revue; score={first.combined_score:.3f}, marge={margin:.3f}. Aucun classement automatique définitif.",
        )
