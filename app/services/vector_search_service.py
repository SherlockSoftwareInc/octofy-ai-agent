"""Object/column vector retrieval + precomputed exact pre-check."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from app.core.constants import (
    PrecomputedQueryTopK,
    effective_object_search_threshold,
    precomputed_direct_match_threshold,
)
from app.models.pipeline import FewShotExample, ScoredObject
from app.services.stores.embeddings import embed_text
from app.utils.hashing import question_lookup_key


class VectorSearchService:
    def __init__(self, provider, source_id: str):
        self.provider = provider
        self.source_id = source_id

    def search_objects(
        self,
        query: str,
        top_k: int = 8,
        max_vector_score: Optional[float] = None,
        entity_types: Optional[Sequence[str]] = None,
    ) -> List[ScoredObject]:
        threshold = effective_object_search_threshold(max_vector_score)
        vector = embed_text(query, self.provider, self.source_id)
        hits = self.provider.search_vector(
            "schemas",
            self.source_id,
            vector,
            top_k=max(top_k * 4, 20),
            min_score=threshold,
        )
        objects: Dict[str, ScoredObject] = {}
        for hit in hits:
            entity = (hit.get("entity_type") or "Table")
            if entity_types and entity not in entity_types:
                continue
            schema_name = hit.get("schema_name") or "dbo"
            object_name = hit.get("object_name") or ""
            if entity == "Column":
                parent_key = f"{schema_name}|{object_name}".lower()
                obj = objects.get(parent_key) or ScoredObject(
                    schema_name=schema_name,
                    object_name=object_name,
                    object_type=hit.get("object_type") or "Table",
                    score=1.0 - float(hit.get("_distance") or 1.0),
                    vector_score=float(hit.get("_distance") or 1.0),
                )
                col = hit.get("column_name")
                if col and col not in obj.matched_columns:
                    obj.matched_columns.append(col)
                    obj.required = True
                objects[parent_key] = obj
            else:
                key = f"{schema_name}|{object_name}".lower()
                existing = objects.get(key)
                if existing:
                    if hit.get("description") and not existing.description:
                        existing.description = hit.get("description")
                    if hit.get("object_type"):
                        existing.object_type = hit.get("object_type") or existing.object_type
                else:
                    objects[key] = ScoredObject(
                        schema_name=schema_name,
                        object_name=object_name,
                        object_type=hit.get("object_type") or entity,
                        score=1.0 - float(hit.get("_distance") or 1.0),
                        vector_score=float(hit.get("_distance") or 1.0),
                        description=hit.get("description"),
                    )
        ranked = sorted(objects.values(), key=lambda o: o.score, reverse=True)
        return ranked[:top_k]

    def search_columns_scored(self, query: str, top_k: int = 100, min_score: Optional[float] = None) -> List[dict]:
        threshold = effective_object_search_threshold(min_score)
        vector = embed_text(query, self.provider, self.source_id)
        hits = self.provider.search_vector(
            "schemas",
            self.source_id,
            vector,
            top_k=top_k,
            min_score=threshold,
            filter_fn=lambda r: (r.get("entity_type") or "") == "Column",
        )
        return hits

    def try_get_precomputed_exact(self, question: str) -> Optional[FewShotExample]:
        needle = question_lookup_key(question)
        rows = self.provider.fetch_all("vec_data_group_queries", self.source_id)
        for row in rows:
            status = (row.get("status") or "")
            if status not in {"Approved", "Modified"}:
                continue
            if question_lookup_key(row.get("question") or "") == needle:
                return FewShotExample(
                    question=row["question"],
                    sql=row.get("sql_query") or "",
                    score=1.0,
                    is_exact_match=True,
                    smq_query=row.get("smq_query") or "",
                    source="precomputed",
                )
        return None

    def search_precomputed(
        self,
        question: str,
        top_k: int = PrecomputedQueryTopK,
        direct_threshold: Optional[float] = None,
        fewshot_threshold: Optional[float] = None,
    ) -> List[FewShotExample]:
        if direct_threshold is None:
            direct_threshold = precomputed_direct_match_threshold()
        vector = embed_text(question, self.provider, self.source_id)
        cache_rows = self.provider.fetch_all("vec_data_group_query_vectors_cache", self.source_id)
        meta = {r["query_id"]: r for r in self.provider.fetch_all("vec_data_group_queries", self.source_id)}
        scored = []
        for row in cache_rows:
            meta_row = meta.get(row.get("query_id"))
            if not meta_row or (meta_row.get("status") or "") != "Approved":
                continue
            from app.services.stores.score_utils import cosine_similarity, loads_vector

            vec = loads_vector(row.get("question_vector_json"))
            if not vec:
                continue
            sim = cosine_similarity(vector, vec)
            scored.append((sim, meta_row))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, meta_row in scored[:top_k]:
            results.append(
                FewShotExample(
                    question=meta_row.get("question") or "",
                    sql=meta_row.get("sql_query") or "",
                    score=sim,
                    is_exact_match=sim >= direct_threshold,
                    smq_query=meta_row.get("smq_query") or "",
                    source="precomputed",
                )
            )
        return results

    def upsert_schema_rows(self, rows: List[dict]) -> None:
        for row in rows:
            row.setdefault("data_source_id", self.source_id)
        self.provider.upsert("schemas", rows)
