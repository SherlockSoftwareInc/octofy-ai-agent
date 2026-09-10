"""Precomputed data-group Q&A store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from app.services.stores.embeddings import embed_text
from app.services.stores.score_utils import dumps_vector


APPROVED = "Approved"
MODIFIED = "Modified"
PENDING = "Pending"
REJECTED = "Rejected"
ERROR = "Error"


class PrecomputedQueryStore:
    def __init__(self, provider, source_id: str):
        self.provider = provider
        self.source_id = source_id

    def upsert(
        self,
        question: str,
        sql_query: str,
        group_name: str,
        group_file_name: str = "",
        smq_query: str = "",
        status: str = PENDING,
        query_id: Optional[str] = None,
    ) -> str:
        query_id = query_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.provider.upsert(
            "vec_data_group_queries",
            [{
                "data_source_id": self.source_id,
                "query_id": query_id,
                "group_name": group_name,
                "group_file_name": group_file_name or group_name,
                "question": question,
                "sql_query": sql_query,
                "smq_query": smq_query or "",
                "status": status,
                "updated_at_utc": now,
            }],
        )
        vector = embed_text(question, self.provider, self.source_id)
        self.provider.upsert(
            "vec_data_group_query_vectors_cache",
            [{
                "data_source_id": self.source_id,
                "query_id": query_id,
                "question_vector_json": dumps_vector(vector),
                "updated_at_utc": now,
            }],
        )
        return query_id

    def list(self, status: Optional[str] = None) -> List[Dict]:
        rows = self.provider.fetch_all("vec_data_group_queries", self.source_id)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return rows

    def set_status(self, query_id: str, status: str) -> None:
        row = self.provider.fetch_one("vec_data_group_queries", self.source_id, "query_id", query_id)
        if not row:
            return
        row["status"] = status
        row["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        self.provider.upsert("vec_data_group_queries", [row])

    def delete(self, query_id: str) -> None:
        self.provider.delete("vec_data_group_queries", self.source_id, "query_id", query_id)
        self.provider.delete("vec_data_group_query_vectors_cache", self.source_id, "query_id", query_id)
