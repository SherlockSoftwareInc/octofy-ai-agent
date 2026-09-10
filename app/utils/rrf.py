"""Reciprocal Rank Fusion merge for discovery ranking."""

from typing import Dict, Iterable, List, Sequence, Tuple

from app.core.constants import (
    RRF_WEIGHT_BM25_DEFAULT,
    RRF_WEIGHT_DATA_GROUP,
    RRF_WEIGHT_FEW_SHOT,
    RRF_WEIGHT_SCHEMA_VECTOR,
    RRF_WEIGHT_VALUE_INDEX,
    RrfK,
)
from app.models.pipeline import ScoredObject


DEFAULT_WEIGHTS = {
    "value_index": RRF_WEIGHT_VALUE_INDEX,
    "few_shot": RRF_WEIGHT_FEW_SHOT,
    "schema_vector": RRF_WEIGHT_SCHEMA_VECTOR,
    "data_group": RRF_WEIGHT_DATA_GROUP,
    "bm25": RRF_WEIGHT_BM25_DEFAULT,
}


def rrf_score(rank: int, weight: float, k: float = RrfK) -> float:
    return weight * (1.0 / (k + rank + 1))


def rrf_merge(
    ranked_lists: Dict[str, Sequence[ScoredObject]],
    weights: Dict[str, float] = None,
    k: float = RrfK,
    max_results: int = 8,
) -> List[ScoredObject]:
    weights = weights or DEFAULT_WEIGHTS
    scores: Dict[str, float] = {}
    objects: Dict[str, ScoredObject] = {}

    for list_name, items in ranked_lists.items():
        weight = weights.get(list_name, 1.0)
        for rank, obj in enumerate(items):
            key = obj.merge_key()
            scores[key] = scores.get(key, 0.0) + rrf_score(rank, weight, k)
            existing = objects.get(key)
            if existing is None:
                objects[key] = obj.model_copy(deep=True)
            else:
                if obj.matched_columns:
                    merged_cols = list(dict.fromkeys(existing.matched_columns + obj.matched_columns))
                    existing.matched_columns = merged_cols
                    if merged_cols:
                        existing.required = True
                if obj.priority:
                    existing.priority = True
                if obj.required:
                    existing.required = True
                if obj.markdown and not existing.markdown:
                    existing.markdown = obj.markdown

    ranked = sorted(objects.values(), key=lambda o: scores[o.merge_key()], reverse=True)
    for obj in ranked:
        obj.score = scores[obj.merge_key()]
    return ranked[:max_results]


def merge_and_dedup(objects: Iterable[ScoredObject]) -> List[ScoredObject]:
    unique: Dict[str, ScoredObject] = {}
    for obj in objects:
        key = obj.merge_key()
        existing = unique.get(key)
        if existing is None:
            unique[key] = obj.model_copy(deep=True)
            continue
        if obj.score > existing.score:
            cols = list(dict.fromkeys(obj.matched_columns + existing.matched_columns))
            obj = obj.model_copy(deep=True)
            obj.matched_columns = cols
            unique[key] = obj
        else:
            for col in obj.matched_columns:
                if col not in existing.matched_columns:
                    existing.matched_columns.append(col)
            existing.priority = existing.priority or obj.priority
            existing.required = existing.required or obj.required
    return list(unique.values())
