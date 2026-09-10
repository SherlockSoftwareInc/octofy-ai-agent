"""Fuzzy and qualified name normalization against the live catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.core.constants import FuzzyMatchMinConfidence
from app.services.database_catalog import DatabaseCatalog


@dataclass
class ResolvedName:
    original: str
    qualified: Optional[str]
    status: str  # exact | fuzzy | missing
    confidence: float
    candidates: List[dict]


class ObjectNameResolver:
    def __init__(self, catalog: DatabaseCatalog):
        self.catalog = catalog

    def parse(self, raw: str) -> tuple[str, str]:
        cleaned = (raw or "").strip().replace("[", "").replace("]", "")
        parts = [p for p in cleaned.split(".") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]
        if parts:
            return "dbo", parts[0]
        return "dbo", ""

    def resolve(self, raw: str) -> ResolvedName:
        schema, name = self.parse(raw)
        if not name:
            return ResolvedName(raw, None, "missing", 0.0, [])
        if self.catalog.object_exists(schema, name):
            return ResolvedName(raw, f"{schema}.{name}", "exact", 1.0, [])
        # try unqualified match
        objects = self.catalog.list_objects()
        for obj in objects:
            if (obj.get("object_name") or "").lower() == name.lower():
                q = f"{obj.get('schema_name')}.{obj.get('object_name')}"
                return ResolvedName(raw, q, "exact", 1.0, [])
        closest = self.catalog.find_closest(raw)
        if closest and closest[0]["confidence"] >= FuzzyMatchMinConfidence:
            best = closest[0]
            q = f"{best.get('schema_name')}.{best.get('object_name')}"
            return ResolvedName(raw, q, "fuzzy", best["confidence"], closest)
        return ResolvedName(raw, None, "missing", closest[0]["confidence"] if closest else 0.0, closest)

    def resolve_many(self, names: List[str]) -> List[ResolvedName]:
        return [self.resolve(n) for n in names]
