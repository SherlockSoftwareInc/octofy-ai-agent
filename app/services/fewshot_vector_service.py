"""Few-shot KB: deterministic few_shots_meta pre-check + vector search."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from app.core.constants import KbExactMatchThreshold, KbScoreThreshold
from app.models.pipeline import FewShotExample
from app.services.stores.embeddings import embed_text
from app.utils.hashing import question_lookup_key


class FewShotVectorService:
    def __init__(self, provider, source_id: str):
        self.provider = provider
        self.source_id = source_id

    def upsert(self, question: str, sql: str, key: Optional[str] = None) -> str:
        key = key or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        vector = embed_text(question, self.provider, self.source_id)
        rec = {
            "data_source_id": self.source_id,
            "key": key,
            "question": question,
            "sql": sql,
            "created_at_utc": now,
            "vector": vector,
        }
        self.provider.upsert("few_shots", [rec])
        self.provider.upsert(
            "few_shots_meta",
            [{
                "data_source_id": self.source_id,
                "key": key,
                "question": question,
                "sql": sql,
                "created_at": now,
            }],
        )
        return key

    def delete(self, key: str) -> None:
        self.provider.delete("few_shots", self.source_id, "key", key)
        self.provider.delete("few_shots_meta", self.source_id, "key", key)

    def try_get_exact(self, question: str) -> Optional[FewShotExample]:
        needle = question_lookup_key(question)
        rows = self.provider.fetch_all("few_shots_meta", self.source_id)
        for row in rows:
            if question_lookup_key(row.get("question") or "") == needle:
                return FewShotExample(
                    question=row["question"],
                    sql=row["sql"],
                    score=1.0,
                    is_exact_match=True,
                    source="few_shot",
                )
        return None

    def search(self, question: str, top_k: int = 3, max_distance: float = KbScoreThreshold) -> List[FewShotExample]:
        vector = embed_text(question, self.provider, self.source_id)
        hits = self.provider.search_vector(
            "few_shots",
            self.source_id,
            vector,
            top_k=top_k,
            min_score=max_distance,
        )
        return [
            FewShotExample(
                question=h.get("question") or "",
                sql=h.get("sql") or "",
                score=float(h.get("_distance") or 1.0),
                is_exact_match=float(h.get("_distance") or 1.0) <= KbExactMatchThreshold,
                source="few_shot",
            )
            for h in hits
        ]

    def list_all(self) -> List[dict]:
        return self.provider.fetch_all("few_shots", self.source_id)
