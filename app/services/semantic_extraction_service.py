"""LLM-first / SQL-parse fallback semantic model extraction. Guarantees ≥1 measure."""

from __future__ import annotations

import json
import re
from typing import Optional
from uuid import uuid4

from app.models.pipeline import SemanticDimension, SemanticJoin, SemanticMeasure, SemanticModel
from app.services.llm_client import LlmClient


class SemanticModelExtractionService:
    def __init__(self, llm: Optional[LlmClient] = None):
        self.llm = llm or LlmClient()

    def extract(self, schema_text: str, sql: Optional[str] = None, label: str = "Model") -> SemanticModel:
        model = None
        try:
            model = self._llm_extract(schema_text, label)
        except Exception:
            model = None
        if model is None and sql:
            model = self._sql_parse_fallback(sql, label)
        if model is None:
            model = SemanticModel(model_id=str(uuid4()), label=label, measures=[], dimensions=[], joins=[])
        if not model.measures:
            model.measures.append(
                SemanticMeasure(name="row_count", expression="COUNT(*)", description="Row count")
            )
        return model

    def _llm_extract(self, schema_text: str, label: str) -> Optional[SemanticModel]:
        prompt = (
            "Extract a semantic model JSON with keys measures, dimensions, joins. "
            "measures must be a non-empty array of {name, expression, description} using full schema.table.column "
            "references (no aliases). Infer defaults: row_count=COUNT(*), COUNT(DISTINCT ...), SUM/AVG over numeric columns.\n"
            f"LABEL: {label}\nSCHEMA:\n{schema_text[:8000]}"
        )
        data = self.llm.complete_json(
            [{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": prompt}]
        )
        if not data:
            return None
        measures = [
            SemanticMeasure(name=m.get("name"), expression=m.get("expression"), description=m.get("description") or "")
            for m in data.get("measures") or []
            if m.get("name") and m.get("expression")
        ]
        dimensions = [
            SemanticDimension(
                name=d.get("name"),
                column=d.get("column") or d.get("column_name"),
                table=d.get("table") or d.get("table_name"),
                description=d.get("description") or "",
            )
            for d in data.get("dimensions") or []
            if d.get("name")
        ]
        joins = [
            SemanticJoin(
                from_table=j.get("from_table"),
                to_table=j.get("to_table"),
                join_expression=j.get("join_expression") or j.get("on"),
                join_type=j.get("join_type") or "INNER",
            )
            for j in data.get("joins") or []
            if j.get("from_table") and j.get("to_table")
        ]
        return SemanticModel(
            model_id=str(uuid4()),
            label=label,
            measures=measures,
            dimensions=dimensions,
            joins=joins,
        )

    def _sql_parse_fallback(self, sql: str, label: str) -> SemanticModel:
        measures = []
        for match in re.finditer(r"(COUNT|SUM|AVG|MIN|MAX)\s*\(([^)]+)\)", sql or "", flags=re.IGNORECASE):
            expr = match.group(0)
            measures.append(SemanticMeasure(name=match.group(1).lower(), expression=expr, description=expr))
        return SemanticModel(model_id=str(uuid4()), label=label, measures=measures)
