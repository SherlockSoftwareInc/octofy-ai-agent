"""Hashing helpers for cache keys and embedding text."""

import hashlib
import re
from typing import Any, Iterable, Optional


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def as_text_token(value: Any) -> str:
    """Coerce LLM/JSON list items to a cacheable string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "entity", "value", "text", "label", "keyword", "column"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        for inner in value.values():
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        return ""
    return str(value).strip()


def normalize_question(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", (text or "").strip().lower())
    return collapsed


def question_lookup_key(text: str) -> str:
    return normalize_question(text)


def discovery_cache_key(
    entities: Iterable[str],
    complexity: str,
    top_k: int,
    extracted_columns: Optional[Iterable[str]] = None,
) -> str:
    entity_part = ",".join(sorted(t.lower() for t in (as_text_token(e) for e in entities) if t))
    key = f"{entity_part}|{complexity}|{top_k}"
    if extracted_columns:
        cols = ",".join(sorted(t.lower() for t in (as_text_token(c) for c in extracted_columns) if t))
        key = f"{key}|cols:{sha256_text(cols)}"
    return key


def query_analysis_cache_key(combined_query: str, existing_code: Optional[str]) -> str:
    raw = f"{(combined_query or '').strip()}|{(existing_code or '').strip()}"
    if len(raw) > 512:
        return sha256_text(raw)
    return raw
