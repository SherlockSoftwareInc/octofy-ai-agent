"""Value index: case-insensitive substring search on plain_value (not vector)."""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import uuid4

from app.services.stores.embeddings import embed_text


class ValueIndexService:
    def __init__(self, provider, source_id: str):
        self.provider = provider
        self.source_id = source_id

    def upsert(
        self,
        value: str,
        schema_name: str,
        table_name: str,
        column_name: str,
        key: Optional[str] = None,
    ) -> str:
        key = key or str(uuid4())
        vector = embed_text(value, self.provider, self.source_id)
        self.provider.upsert(
            "value_index",
            [{
                "data_source_id": self.source_id,
                "key": key,
                "value": value,
                "plain_value": (value or "").lower(),
                "schema_name": schema_name,
                "table_name": table_name,
                "column_name": column_name,
                "vector": vector,
            }],
        )
        return key

    def search(self, query: str, top_k: int = 10, fetch_cap: int = 16384) -> List[Dict]:
        needle = (query or "").strip().lower()
        if not needle:
            return []
        rows = self.provider.fetch_all("value_index", self.source_id)[:fetch_cap]
        hits = []
        for row in rows:
            plain = (row.get("plain_value") or "").lower()
            if needle in plain:
                hits.append(row)
            if len(hits) >= top_k:
                break
        return hits[:top_k]

    def delete(self, key: str) -> None:
        self.provider.delete("value_index", self.source_id, "key", key)

    def list_all(self) -> List[Dict]:
        return self.provider.fetch_all("value_index", self.source_id)

    def clear(self) -> None:
        self.provider.delete_source("value_index", self.source_id)
