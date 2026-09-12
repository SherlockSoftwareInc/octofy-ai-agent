"""Per-source semantic model CRUD + embeddings + activation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from app.models.pipeline import SemanticDimension, SemanticJoin, SemanticMeasure, SemanticModel
from app.services.stores.embeddings import embed_text
from app.services.stores.schema_contracts import semantic_embedding_source
from app.services.stores.score_utils import cosine_similarity, dumps_vector, loads_vector


class SemanticModelService:
    def __init__(self, provider, source_id: str, enable_flag: Optional[bool] = None):
        self.provider = provider
        self.source_id = source_id
        self.enable_flag = enable_flag

    def is_enabled(self, request_override: Optional[bool] = None) -> bool:
        if request_override is not None:
            return bool(request_override) and self.get_active_model() is not None
        flag = self.enable_flag
        if flag is None:
            from app.core.config import settings
            flag = settings.semantic_layer_enabled_for(self.source_id)
        if flag is False:
            return False
        if flag is True:
            return self.get_active_model() is not None
        return self.get_active_model() is not None

    def save(self, model: SemanticModel) -> SemanticModel:
        now = datetime.now(timezone.utc).isoformat()
        model_id = model.model_id or str(uuid4())
        self.provider.upsert(
            "semantic_models",
            [{
                "data_source_id": self.source_id,
                "model_id": model_id,
                "label": model.label,
                "is_active": 1 if model.is_active else 0,
                "updated_at_utc": now,
            }],
        )
        self._replace_children(model_id, model)
        source = semantic_embedding_source(
            model.label, model.measures, model.dimensions, model.governance_predicates
        )
        vec = embed_text(source, self.provider, self.source_id)
        self.provider.upsert(
            "semantic_embeddings",
            [{
                "data_source_id": self.source_id,
                "model_id": model_id,
                "embedding_json": dumps_vector(vec),
                "updated_at_utc": now,
            }],
        )
        model.model_id = model_id
        model.data_source_key = self.source_id
        return model

    def _replace_children(self, model_id: str, model: SemanticModel) -> None:
        for table, key in (
            ("semantic_measures", "measure_name"),
            ("semantic_dimensions", "dimension_name"),
            ("semantic_joins", "from_table"),
            ("semantic_governance_predicates", "predicate"),
        ):
            existing = [
                r for r in self.provider.fetch_all(table, self.source_id) if r.get("model_id") == model_id
            ]
            for row in existing:
                self.provider.delete(table, self.source_id, "model_id", model_id)
                break
        if model.measures:
            self.provider.upsert(
                "semantic_measures",
                [{
                    "data_source_id": self.source_id,
                    "model_id": model_id,
                    "measure_name": m.name,
                    "expression": m.expression,
                    "description": m.description or "",
                } for m in model.measures],
            )
        if model.dimensions:
            self.provider.upsert(
                "semantic_dimensions",
                [{
                    "data_source_id": self.source_id,
                    "model_id": model_id,
                    "dimension_name": d.name,
                    "column_name": d.column,
                    "table_name": d.table,
                    "description": d.description or "",
                } for d in model.dimensions],
            )
        if model.joins:
            self.provider.upsert(
                "semantic_joins",
                [{
                    "data_source_id": self.source_id,
                    "model_id": model_id,
                    "from_table": j.from_table,
                    "to_table": j.to_table,
                    "join_expression": j.join_expression,
                    "join_type": j.join_type or "INNER",
                } for j in model.joins],
            )
        if model.governance_predicates:
            self.provider.upsert(
                "semantic_governance_predicates",
                [{
                    "data_source_id": self.source_id,
                    "model_id": model_id,
                    "predicate": p,
                    "description": "",
                } for p in model.governance_predicates],
            )

    def list_models(self) -> List[SemanticModel]:
        headers = self.provider.fetch_all("semantic_models", self.source_id)
        return [self._hydrate(h) for h in headers]

    def get_active_model(self) -> Optional[SemanticModel]:
        headers = [
            h for h in self.provider.fetch_all("semantic_models", self.source_id) if int(h.get("is_active") or 0) == 1
        ]
        if not headers:
            return None
        headers.sort(key=lambda h: h.get("updated_at_utc") or "", reverse=True)
        return self._hydrate(headers[0])

    def search_models(self, query: str, top_k: int = 3) -> List[SemanticModel]:
        active = [m for m in self.list_models() if m.is_active]
        if not active:
            return []
        qv = embed_text(query, self.provider, self.source_id)
        scored = []
        embeddings = {
            r["model_id"]: loads_vector(r.get("embedding_json"))
            for r in self.provider.fetch_all("semantic_embeddings", self.source_id)
        }
        for model in active:
            vec = embeddings.get(model.model_id) or []
            sim = cosine_similarity(qv, vec) if vec else 0.0
            scored.append((sim, model))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    def _hydrate(self, header: dict) -> SemanticModel:
        mid = header["model_id"]
        measures = [
            SemanticMeasure(name=r["measure_name"], expression=r["expression"], description=r.get("description") or "")
            for r in self.provider.fetch_all("semantic_measures", self.source_id)
            if r.get("model_id") == mid
        ]
        dimensions = [
            SemanticDimension(
                name=r["dimension_name"],
                column=r["column_name"],
                table=r["table_name"],
                description=r.get("description") or "",
            )
            for r in self.provider.fetch_all("semantic_dimensions", self.source_id)
            if r.get("model_id") == mid
        ]
        joins = [
            SemanticJoin(
                from_table=r["from_table"],
                to_table=r["to_table"],
                join_expression=r["join_expression"],
                join_type=r.get("join_type") or "INNER",
            )
            for r in self.provider.fetch_all("semantic_joins", self.source_id)
            if r.get("model_id") == mid
        ]
        gov = [
            r.get("predicate") or ""
            for r in self.provider.fetch_all("semantic_governance_predicates", self.source_id)
            if r.get("model_id") == mid
        ]
        return SemanticModel(
            model_id=mid,
            data_source_key=self.source_id,
            label=header.get("label") or mid,
            is_active=bool(int(header.get("is_active") or 0)),
            measures=measures,
            dimensions=dimensions,
            joins=joins,
            governance_predicates=gov,
        )
