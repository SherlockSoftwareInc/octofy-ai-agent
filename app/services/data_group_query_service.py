"""Precomputed pair generation + status workflow."""

from __future__ import annotations

from typing import List, Optional

from app.services.stores.precomputed_store import (
    APPROVED,
    ERROR,
    MODIFIED,
    PENDING,
    REJECTED,
    PrecomputedQueryStore,
)


class DataGroupQueryGenerationService:
    def __init__(self, store: PrecomputedQueryStore):
        self.store = store

    def generate_pairs(self, group_name: str, questions_sql: List[dict], status: str = PENDING) -> List[str]:
        ids = []
        for item in questions_sql:
            ids.append(
                self.store.upsert(
                    question=item["question"],
                    sql_query=item.get("sql_query") or item.get("sql") or "",
                    group_name=group_name,
                    group_file_name=item.get("group_file_name") or group_name,
                    smq_query=item.get("smq_query") or "",
                    status=status,
                )
            )
        return ids

    def approve(self, query_id: str) -> None:
        self.store.set_status(query_id, APPROVED)

    def reject(self, query_id: str) -> None:
        self.store.set_status(query_id, REJECTED)

    def mark_modified(self, query_id: str) -> None:
        self.store.set_status(query_id, MODIFIED)

    def mark_error(self, query_id: str) -> None:
        self.store.set_status(query_id, ERROR)
