"""Data-group metadata + vector cache."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.constants import ActiveDataGroupTopN
from app.services.stores.embeddings import embed_text
from app.services.stores.score_utils import cosine_similarity, dumps_vector, loads_vector


class DataGroupStore:
    def __init__(self, provider, source_id: str):
        self.provider = provider
        self.source_id = source_id

    def upsert(
        self,
        group_name: str,
        description: str,
        keywords: List[str],
        members: List[str],
        group_id: Optional[str] = None,
    ) -> str:
        group_id = group_id or f"[{self.source_id}].[{group_name}]"
        now = datetime.now(timezone.utc).isoformat()
        self.provider.upsert(
            "data_group_metadata",
            [{
                "data_source_id": self.source_id,
                "group_id": group_id,
                "group_name": group_name,
                "description": description,
                "keywords_json": json.dumps(keywords),
                "members_json": json.dumps(members),
                "updated_at_utc": now,
            }],
        )
        semantic = embed_text(description or group_name, self.provider, self.source_id)
        functional = embed_text(" ".join(keywords), self.provider, self.source_id)
        object_vec = embed_text(" ".join(members), self.provider, self.source_id)
        self.provider.upsert(
            "data_group_vectors_cache",
            [{
                "data_source_id": self.source_id,
                "group_id": group_id,
                "semantic_vector_json": dumps_vector(semantic),
                "functional_vector_json": dumps_vector(functional),
                "object_vector_json": dumps_vector(object_vec),
                "updated_at_utc": now,
            }],
        )
        return group_id

    def list(self) -> List[Dict]:
        rows = self.provider.fetch_all("data_group_metadata", self.source_id)
        for row in rows:
            try:
                row["keywords"] = json.loads(row.get("keywords_json") or "[]")
            except Exception:
                row["keywords"] = []
            try:
                row["members"] = json.loads(row.get("members_json") or "[]")
            except Exception:
                row["members"] = []
        return rows

    def search(self, query: str, top_n: int = ActiveDataGroupTopN, query_vector: Optional[List[float]] = None) -> List[Dict]:
        meta = {r["group_id"]: r for r in self.list()}
        cache = self.provider.fetch_all("data_group_vectors_cache", self.source_id)
        if query_vector is None:
            query_vector = embed_text(query, self.provider, self.source_id)
        scored = []
        for row in cache:
            vec = loads_vector(row.get("semantic_vector_json"))
            if not vec:
                continue
            sim = cosine_similarity(query_vector, vec)
            info = dict(meta.get(row["group_id"]) or {"group_id": row["group_id"]})
            info["score"] = sim
            scored.append(info)
        scored.sort(key=lambda g: g.get("score") or 0, reverse=True)
        return scored[:top_n]
