"""Live object listing / existence checks per source (TTL 300s)."""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from app.core.constants import CatalogCacheTtlSeconds

_cache: Dict[str, Tuple[float, List[dict]]] = {}


class DatabaseCatalog:
    def __init__(self, source_id: str):
        self.source_id = source_id

    def list_objects(self, force: bool = False) -> List[dict]:
        now = time.time()
        hit = _cache.get(self.source_id)
        if not force and hit and (now - hit[0]) < CatalogCacheTtlSeconds:
            return hit[1]
        objects = self._load_live()
        _cache[self.source_id] = (now, objects)
        return objects

    def object_exists(self, schema_name: str, object_name: str) -> bool:
        target = f"{schema_name}.{object_name}".lower()
        for obj in self.list_objects():
            qualified = f"{obj.get('schema_name')}.{obj.get('object_name')}".lower()
            if qualified == target:
                return True
        return False

    def find_closest(self, name: str, limit: int = 5) -> List[dict]:
        from difflib import SequenceMatcher

        needle = name.lower().replace("[", "").replace("]", "")
        scored = []
        for obj in self.list_objects():
            candidate = f"{obj.get('schema_name')}.{obj.get('object_name')}".lower()
            ratio = SequenceMatcher(None, needle, candidate).ratio()
            bare = SequenceMatcher(None, needle.split(".")[-1], (obj.get("object_name") or "").lower()).ratio()
            score = max(ratio, bare)
            scored.append((score, obj))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"confidence": s, **o} for s, o in scored[:limit]]

    def _load_live(self) -> List[dict]:
        try:
            from app.core.database import get_database_engine
            from sqlalchemy import text

            engine = get_database_engine(self.source_id)
            sql = """
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            """
            rows = []
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                for schema, name, typ in result:
                    rows.append({
                        "schema_name": schema,
                        "object_name": name,
                        "object_type": "View" if "VIEW" in (typ or "").upper() else "Table",
                    })
            return rows
        except Exception:
            try:
                from app.services.vector_store import get_vector_store

                vs = get_vector_store()
                objects = vs.get_all_objects_v2(self.source_id) or []
                return [
                    {
                        "schema_name": o.get("schema_name"),
                        "object_name": o.get("object_name"),
                        "object_type": o.get("object_type") or "Table",
                    }
                    for o in objects
                ]
            except Exception:
                return []
