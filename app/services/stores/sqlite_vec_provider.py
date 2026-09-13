"""Per-source SQLite sidecar / shared-file adapter. JSON vectors + in-process cosine."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.core.config import settings
from app.services.stores.schema_contracts import COLLECTIONS, RETIRED_COLLECTIONS, sqlite_ddl
from app.services.stores.score_utils import cosine_distance, dumps_vector, loads_vector


def default_sqlite_path() -> Path:
    configured = getattr(settings, "VECTOR_SQLITE_PATH", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "data" / "vector-index.sqlite"


class SqliteVecProvider:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else default_sqlite_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for spec in COLLECTIONS:
                cur.execute(sqlite_ddl(spec))
            for retired in RETIRED_COLLECTIONS:
                cur.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (retired,),
                )
                if cur.fetchone():
                    cur.execute(f'DROP TABLE IF EXISTS "{retired}"')
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_value_plain "
                "ON value_index (data_source_id, plain_value)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_embedding_lru "
                "ON embedding_cache (data_source_id, last_accessed_utc)"
            )
            self._conn.commit()

    def has_collection(self, name: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            )
            return cur.fetchone() is not None

    def drop_collection_if_exists(self, name: str) -> bool:
        if not self.has_collection(name):
            return False
        with self._lock:
            self._conn.execute(f'DROP TABLE IF EXISTS "{name}"')
            self._conn.commit()
        return True

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def upsert(self, collection: str, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        with self._lock:
            cur = self._conn.cursor()
            for rec in records:
                row = dict(rec)
                for key, value in list(row.items()):
                    if isinstance(value, (list, tuple)) and (
                        key == "vector" or key.endswith("vector") or key.endswith("_json")
                    ):
                        if value and isinstance(value[0], (int, float)):
                            row[key] = dumps_vector(value)
                cols = list(row.keys())
                placeholders = ", ".join(["?"] * len(cols))
                sql = f"INSERT OR REPLACE INTO {collection} ({', '.join(cols)}) VALUES ({placeholders})"
                cur.execute(sql, [row[c] for c in cols])
            self._conn.commit()

    def delete(self, collection: str, data_source_id: str, key_field: str, key: str) -> None:
        with self._lock:
            self._conn.execute(
                f"DELETE FROM {collection} WHERE data_source_id = ? AND {key_field} = ?",
                (data_source_id, key),
            )
            self._conn.commit()

    def delete_source(self, collection: str, data_source_id: str) -> None:
        with self._lock:
            self._conn.execute(
                f"DELETE FROM {collection} WHERE data_source_id = ?",
                (data_source_id,),
            )
            self._conn.commit()

    def fetch_all(self, collection: str, data_source_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM {collection} WHERE data_source_id = ?",
                (data_source_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def fetch_all_rows(self, collection: str) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                cur = self._conn.execute(f"SELECT * FROM {collection}")
            except sqlite3.OperationalError:
                return []
            return [dict(r) for r in cur.fetchall()]

    def list_data_source_ids(self) -> List[str]:
        with self._lock:
            try:
                cur = self._conn.execute("SELECT DISTINCT data_source_id FROM schemas")
            except sqlite3.OperationalError:
                return []
            return [row[0] for row in cur.fetchall() if row[0]]

    def fetch_one(self, collection: str, data_source_id: str, key_field: str, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM {collection} WHERE data_source_id = ? AND {key_field} = ?",
                (data_source_id, key),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def search_vector(
        self,
        collection: str,
        data_source_id: str,
        query_vector: Sequence[float],
        top_k: int = 8,
        vector_field: str = "vector",
        extra_where: str = "",
        extra_params: Sequence[Any] = (),
        min_score: Optional[float] = None,
        filter_fn=None,
    ) -> List[Dict[str, Any]]:
        sql = f"SELECT * FROM {collection} WHERE data_source_id = ?"
        params: List[Any] = [data_source_id]
        if extra_where:
            sql += f" AND {extra_where}"
            params.extend(extra_params)
        with self._lock:
            rows = [dict(r) for r in self._conn.execute(sql, params).fetchall()]
        scored = []
        for row in rows:
            if filter_fn and not filter_fn(row):
                continue
            vec = loads_vector(row.get(vector_field) or row.get(f"{vector_field}_json"))
            if not vec:
                raw = row.get(vector_field)
                if isinstance(raw, str) and raw.startswith("["):
                    vec = loads_vector(raw)
            if not vec:
                continue
            dist = cosine_distance(query_vector, vec)
            if min_score is not None and dist > min_score:
                continue
            item = dict(row)
            item["_distance"] = dist
            scored.append(item)
        scored.sort(key=lambda r: r["_distance"])
        return scored[:top_k]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            if cur.description is None:
                self._conn.commit()
                return []
            return [dict(r) for r in cur.fetchall()]
