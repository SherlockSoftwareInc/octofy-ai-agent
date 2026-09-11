"""Object context assembly under token budget, column pruning, MatchedColumns."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from app.core.constants import PromptContextDiscoveryCap, SchemaContextTokenBudget
from app.models.pipeline import ScoredObject
from app.utils.dialect import quote_qualified


def _estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


class SqlContextHydrator:
    def __init__(self, token_budget: int = SchemaContextTokenBudget, cap: int = PromptContextDiscoveryCap):
        self.token_budget = token_budget
        self.cap = cap
        self.value_mappings: List[dict] = []

    def set_value_mappings(self, mappings: List[dict]) -> None:
        self.value_mappings = mappings or []

    def cap_objects(self, objects: Sequence[ScoredObject]) -> List[ScoredObject]:
        required = [o for o in objects if o.required or o.priority or o.matched_columns or o.object_type == "SemanticModel"]
        rest = [o for o in objects if o not in required]
        if rest:
            best = max((o.score for o in rest), default=0.0)
            floor = best * 0.05 if best else 0.0
            rest = [o for o in rest if o.score >= floor]
        merged = required + rest
        seen = set()
        unique = []
        for obj in merged:
            key = obj.merge_key()
            if key in seen:
                continue
            seen.add(key)
            unique.append(obj)
        return unique[: self.cap]

    def build_contexts(
        self,
        objects: Sequence[ScoredObject],
        markdown_lookup: Optional[Dict[str, str]] = None,
        dbms: str = "SQL Server",
    ) -> Tuple[str, str, str, str]:
        capped = self.cap_objects(objects)
        markdown_lookup = markdown_lookup or {}
        selected_parts = []
        supplementary_parts = []
        schema_parts = []
        validation_parts = []
        used = 0
        for obj in capped:
            key = f"{obj.schema_name}.{obj.object_name}".lower()
            body = obj.markdown or markdown_lookup.get(key) or self._fallback_markdown(obj, dbms)
            tokens = _estimate_tokens(body)
            evidence = ""
            if obj.matched_columns:
                cols = ", ".join(
                    f"{quote_qualified(obj.schema_name, obj.object_name, dbms)}.{c}"
                    for c in obj.matched_columns
                )
                evidence = f"-- Matched column evidence: {cols}\n"
            block = body if body.startswith("#") else f"## {obj.schema_name}.{obj.object_name}\n{body}"
            if obj.priority or obj.required:
                selected_parts.append(block)
                schema_parts.append(block)
                validation_parts.append(evidence + block)
                used += tokens
            elif used + tokens <= self.token_budget:
                supplementary_parts.append(block)
                schema_parts.append(block)
                validation_parts.append(evidence + block)
                used += tokens
            else:
                pruned = self._prune_columns(block, obj.matched_columns)
                supplementary_parts.append(pruned)
                validation_parts.append(evidence + pruned)
                used += _estimate_tokens(pruned)
        return (
            "\n\n".join(selected_parts),
            "\n\n".join(supplementary_parts),
            "\n\n".join(schema_parts),
            "\n\n".join(validation_parts),
        )

    def _fallback_markdown(self, obj: ScoredObject, dbms: str) -> str:
        desc = obj.description or ""
        if " | Description: " in desc:
            desc = desc.split(" | Description: ", 1)[1]
        if desc.lstrip().startswith("#") or "## Columns" in desc:
            return desc
        cols = ", ".join(obj.matched_columns) if obj.matched_columns else ""
        extra = f"\nColumns of interest: {cols}" if cols else ""
        return f"{quote_qualified(obj.schema_name, obj.object_name, dbms)} ({obj.object_type}){extra}\n{desc}"

    def _prune_columns(self, markdown: str, keep: Sequence[str]) -> str:
        if not keep:
            lines = markdown.splitlines()
            return "\n".join(lines[:12])
        keep_l = {c.lower() for c in keep}
        kept = []
        for line in markdown.splitlines():
            if line.strip().startswith("|") and not any(c in line.lower() for c in keep_l) and "name" not in line.lower():
                continue
            kept.append(line)
        return "\n".join(kept)
