"""Optional BM25 lexical rerank signal (feature-flagged)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List

from app.models.pipeline import ScoredObject


class Bm25Service:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled

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
                score += idf * (freq * 2.2) / (freq + 1.2 * (0.25 + 0.75 * dl / avgdl))
            copy = obj.model_copy(deep=True)
            copy.score = score
            scored.append(copy)
        scored.sort(key=lambda o: o.score, reverse=True)
        return scored[:top_k]

    def _tokens(self, text: str) -> List[str]:
        return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", text or "")]
