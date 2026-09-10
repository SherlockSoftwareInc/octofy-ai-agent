"""Shared vector math and score normalization (cosine distance, lower = closer)."""

from __future__ import annotations

import json
import math
from typing import Iterable, List, Optional, Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / math.sqrt(na * nb)


def cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


def milvus_score_to_cosine_distance(score: float, metric: str = "COSINE") -> float:
    """Normalize provider scores to cosine distance (lower = more similar)."""
    kind = (metric or "COSINE").upper()
    if kind == "L2":
        return float(score)
    if kind in {"IP", "INNER_PRODUCT"}:
        return 1.0 - float(score)
    # COSINE similarity in [ -1, 1 ] → distance
    return 1.0 - float(score)


def dumps_vector(vec: Iterable[float]) -> str:
    return json.dumps(list(vec))


def loads_vector(raw: Optional[str]) -> List[float]:
    if not raw:
        return []
    if isinstance(raw, (bytes, memoryview)):
        raw = bytes(raw).decode("utf-8")
    data = json.loads(raw)
    return [float(x) for x in data]
