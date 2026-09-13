"""Few-shot KB: deterministic exact pre-check on few_shots + vector search."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from app.core.constants import KbExactMatchThreshold, KbScoreThreshold
from app.models.pipeline import FewShotExample
from app.services.stores.embeddings import embed_text, try_embed_text
from app.utils.hashing import question_lookup_key

logger = logging.getLogger(__name__)

DATA_TABLE_NAME = "few_shots"
LEGACY_META_TABLE_NAME = "few_shots_meta"


class FewShotVectorService:
    def __init__(self, provider, source_id: str):
        self.provider = provider
        self.source_id = source_id
        self._legacy_meta_checked = False

    @classmethod
    def try_create_local(cls, vector_db_path: Optional[str], source_id: str) -> Optional["FewShotVectorService"]:
        """Build a service against a local SQLite file. No embedding provider is required."""
        if not vector_db_path:
            return None
        path = Path(vector_db_path)
        if not path.exists() and not path.parent.exists():
            return None
        from app.services.stores.sqlite_vec_provider import SqliteVecProvider

        return cls(SqliteVecProvider(path), source_id)

    def upsert(self, question: str, sql: str, key: Optional[str] = None) -> str:
        self._ensure_legacy_meta_dropped()
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
        self.provider.upsert(DATA_TABLE_NAME, [rec])
        return key

    def replace(self, key: str, question: str, sql: str) -> bool:
        """Update question/sql in place, keeping ``key`` and ``created_at_utc``.

        Returns True when a vector was regenerated. When no embedding is
        available the scalars are still written and the stored vector is left
        as-is (exact match is unaffected; similarity keeps the previous vector).
        """
        self._ensure_legacy_meta_dropped()
        created_at = self._try_get_created_at_utc(key)
        vector = try_embed_text(question, self.provider, self.source_id)
        if vector:
            self.provider.upsert(
                DATA_TABLE_NAME,
                [{
                    "data_source_id": self.source_id,
                    "key": key,
                    "question": question,
                    "sql": sql,
                    "created_at_utc": created_at or datetime.now(timezone.utc).isoformat(),
                    "vector": vector,
                }],
            )
            return True
        self._update_scalars_without_vector(key, question, sql)
        return False

    def delete(self, key: str) -> None:
        self._ensure_legacy_meta_dropped()
        self.provider.delete(DATA_TABLE_NAME, self.source_id, "key", key)

    def try_get_exact(self, question: str) -> Optional[FewShotExample]:
        """Normalized question scan of the plain ``few_shots`` table.

        Vector-free: uses ``fetch_all`` / a sqlite_master probe and never
        calls ``search_vector``. First match wins; rows with empty SQL are skipped.
        """
        self._ensure_legacy_meta_dropped()
        if not self._collection_exists(DATA_TABLE_NAME):
            return None
        try:
            rows = self.provider.fetch_all(DATA_TABLE_NAME, self.source_id)
        except Exception:
            return None
        needle = question_lookup_key(question)
        for row in rows:
            sql = (row.get("sql") or "").strip()
            if not sql:
                continue
            if question_lookup_key(row.get("question") or "") == needle:
                return FewShotExample(
                    question=row.get("question") or "",
                    sql=sql,
                    score=1.0,
                    is_exact_match=True,
                    source="few_shot",
                )
        return None

    def search(self, question: str, top_k: int = 3, max_distance: float = KbScoreThreshold) -> List[FewShotExample]:
        self._ensure_legacy_meta_dropped()
        vector = embed_text(question, self.provider, self.source_id)
        hits = self.provider.search_vector(
            DATA_TABLE_NAME,
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
        self._ensure_legacy_meta_dropped()
        if not self._collection_exists(DATA_TABLE_NAME):
            return []
        return self.provider.fetch_all(DATA_TABLE_NAME, self.source_id)

    def _ensure_legacy_meta_dropped(self) -> None:
        if self._legacy_meta_checked:
            return
        self._legacy_meta_checked = True
        dropped = False
        if hasattr(self.provider, "drop_collection_if_exists"):
            try:
                dropped = bool(self.provider.drop_collection_if_exists(LEGACY_META_TABLE_NAME))
            except Exception:
                dropped = False
        elif hasattr(self.provider, "execute"):
            try:
                rows = self.provider.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (LEGACY_META_TABLE_NAME,),
                )
                if rows:
                    self.provider.execute(f'DROP TABLE IF EXISTS "{LEGACY_META_TABLE_NAME}"')
                    dropped = True
            except Exception:
                dropped = False
        if dropped:
            logger.debug("Dropped legacy table %s", LEGACY_META_TABLE_NAME)

    def _collection_exists(self, name: str) -> bool:
        if hasattr(self.provider, "has_collection"):
            try:
                return bool(self.provider.has_collection(name))
            except Exception:
                return False
        if hasattr(self.provider, "execute"):
            try:
                rows = self.provider.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (name,),
                )
                return bool(rows)
            except Exception:
                return False
        return True

    def _try_get_created_at_utc(self, key: str) -> Optional[str]:
        try:
            row = self.provider.fetch_one(DATA_TABLE_NAME, self.source_id, "key", key)
        except Exception:
            return None
        if not row:
            return None
        value = row.get("created_at_utc")
        return str(value) if value else None

    def _update_scalars_without_vector(self, key: str, question: str, sql: str) -> None:
        try:
            row = self.provider.fetch_one(DATA_TABLE_NAME, self.source_id, "key", key)
        except Exception:
            row = None
        if not row:
            return
        row["question"] = question
        row["sql"] = sql
        self.provider.upsert(DATA_TABLE_NAME, [row])
