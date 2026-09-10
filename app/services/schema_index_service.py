"""Keyword schema index over on-disk markdown / in-memory object catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from app.models.pipeline import ScoredObject


class SchemaIndexService:
    def __init__(self, source_id: str, skills_root: Optional[Path] = None):
        self.source_id = source_id
        self.skills_root = skills_root
        self._objects: List[ScoredObject] = []
        self._keyword_map: Dict[str, List[ScoredObject]] = {}

    def load_from_rows(self, rows: List[dict]) -> None:
        objects: Dict[str, ScoredObject] = {}
        for row in rows:
            if (row.get("entity_type") or "Table") == "Column":
                continue
            key = f"{row.get('schema_name')}|{row.get('object_name')}".lower()
            objects[key] = ScoredObject(
                schema_name=row.get("schema_name") or "dbo",
                object_name=row.get("object_name") or "",
                object_type=row.get("object_type") or "Table",
                description=row.get("description"),
            )
        self._objects = list(objects.values())
        self._rebuild_keywords()

    def _rebuild_keywords(self) -> None:
        self._keyword_map = {}
        for obj in self._objects:
            tokens = re.findall(r"[A-Za-z0-9]+", f"{obj.object_name} {obj.description or ''}")
            for tok in tokens:
                self._keyword_map.setdefault(tok.lower(), []).append(obj)

    def search_keywords(self, query: str, top_k: int = 8) -> List[ScoredObject]:
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", query or "")]
        scores: Dict[str, float] = {}
        objs: Dict[str, ScoredObject] = {}
        for tok in tokens:
            for obj in self._keyword_map.get(tok, []):
                key = obj.merge_key()
                scores[key] = scores.get(key, 0.0) + 1.0
                objs[key] = obj.model_copy(deep=True)
        ranked = sorted(objs.values(), key=lambda o: scores[o.merge_key()], reverse=True)
        for obj in ranked:
            obj.score = scores[obj.merge_key()]
        return ranked[:top_k]

    def score_data_group_keywords(self, query: str, groups: List[dict]) -> List[dict]:
        q_tokens = set(t.lower() for t in re.findall(r"[A-Za-z0-9]+", query or ""))
        scored = []
        for group in groups:
            keywords = group.get("keywords") or []
            if isinstance(keywords, str):
                try:
                    keywords = json.loads(keywords)
                except Exception:
                    keywords = [keywords]
            g_tokens = set(str(k).lower() for k in keywords)
            if not q_tokens:
                overlap = 0.0
            else:
                overlap = len(q_tokens & g_tokens) / max(len(q_tokens), 1)
            scored.append({**group, "overlap": overlap})
        scored.sort(key=lambda g: g["overlap"], reverse=True)
        return scored
