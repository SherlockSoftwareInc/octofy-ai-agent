"""Optional BM25 lexical rerank signal (feature-flagged)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List, Optional

from app.models.pipeline import ScoredObject


class Bm25Service:
    def __init__(
        self,
        enabled: Optional[bool] = None,
        k1: Optional[float] = None,
        b: Optional[float] = None,
    ):
        self._enabled_override = enabled
        self._k1 = k1
        self._b = b

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        from app.core.config import settings
        return bool(settings.ENABLE_BM25_RETRIEVAL)

    @property
    def k1(self) -> float:
        if self._k1 is not None:
            return self._k1
        from app.core.config import settings
        return float(settings.BM25_K1)

    @property
    def b(self) -> float:
        if self._b is not None:
            return self._b
        from app.core.config import settings
        return float(settings.BM25_B)

    def rank(self, query: str, objects: Iterable[ScoredObject], top_k: int = 8) -> List[ScoredObject]:
        if not self.enabled:
            return []
        docs = list(objects)
        if not docs:
            return []
        tokenized = [self._tokens(f"{o.object_name} {o.description or ''}") for o in docs]
        avgdl = sum(len(t) for t in tokenized) / len(tokenized)
        df = Counter()
        for toks in tokenized:
            df.update(set(toks))
        q_tokens = self._tokens(query)
        k1 = self.k1
        b = self.b
        scored = []
        for obj, toks in zip(docs, tokenized):
            score = 0.0
            tf = Counter(toks)
            dl = len(toks) or 1
            for term in q_tokens:
                if term not in df:
                    continue
                idf = math.log((len(docs) - df[term] + 0.5) / (df[term] + 0.5) + 1)
                freq = tf[term]
                score += idf * (freq * (k1 + 1.0)) / (freq + k1 * ((1.0 - b) + b * dl / avgdl))
            copy = obj.model_copy(deep=True)
            copy.score = score
            scored.append(copy)
        scored.sort(key=lambda o: o.score, reverse=True)
        return scored[:top_k]

    def _tokens(self, text: str) -> List[str]:
        return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", text or "")]
