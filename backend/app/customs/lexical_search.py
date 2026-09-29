from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.customs.camcis_repository import CamcisRecord
from backend.app.normalization.text import normalize_search_text


@dataclass(frozen=True)
class LexicalHit:
    record: CamcisRecord
    score: float


class LexicalTariffSearch:
    """Deterministic lexical retrieval over CAMCIS.

    Uses character n-gram TF-IDF (robust to spelling/translation noise) plus a fuzzy token score.
    Scores are retrieval/ranking signals, not calibrated probabilities.
    """

    def __init__(self, records: list[CamcisRecord]):
        self.records = records
        corpus = [r.search_text for r in records]
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, limit: int = 20) -> list[LexicalHit]:
        q = normalize_search_text(query)
        if not q:
            return []
        qv = self.vectorizer.transform([q])
        cosine = (self.matrix @ qv.T).toarray().ravel()
        # Preselect by TF-IDF, then blend with fuzzy score.
        pre_n = min(max(limit * 8, 80), len(self.records))
        idxs = np.argpartition(cosine, -pre_n)[-pre_n:] if pre_n < len(cosine) else np.arange(len(cosine))
        hits: list[LexicalHit] = []
        for idx in idxs:
            rec = self.records[int(idx)]
            fuzzy = fuzz.token_set_ratio(q, rec.search_text) / 100.0
            score = 0.82 * float(cosine[int(idx)]) + 0.18 * fuzzy
            hits.append(LexicalHit(record=rec, score=max(0.0, min(1.0, score))))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
