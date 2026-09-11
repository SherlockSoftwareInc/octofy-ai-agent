"""Build contract `schemas` rows (parent + columns) for ingest and the vector-store facade."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.services.stores.embeddings import embed_text
from app.services.stores.schema_contracts import (
    column_embedding_text,
    normalize_object_type,
    parent_embedding_text,
    schema_object_key,
)


def _column_parts(col: Any) -> tuple:
    if isinstance(col, dict):
        return (
            col.get("name") or col.get("column_name") or "",
            col.get("data_type") or col.get("type") or "",
            col.get("description") or col.get("comment") or "",
        )
    return (
        getattr(col, "name", "") or "",
        getattr(col, "data_type", "") or "",
        getattr(col, "description", "") or "",
    )


def build_schema_object_rows(
    provider,
    data_source_id: str,
    schema_name: str,
    object_name: str,
    object_type: str,
    description: str,
    columns: Optional[Iterable[Any]] = None,
) -> List[Dict[str, Any]]:
    object_type = normalize_object_type(object_type)
    parent_text = parent_embedding_text(object_type, object_name, description or "")
    rows: List[Dict[str, Any]] = [
        {
            "data_source_id": data_source_id,
            "key": schema_object_key(data_source_id, schema_name, object_name),
            "schema_name": schema_name,
            "object_name": object_name,
            "object_type": object_type,
            "entity_type": object_type,
            "column_name": "",
            "description": parent_text,
            "vector": embed_text(parent_text, provider, data_source_id),
        }
    ]
    for col in columns or []:
        col_name, col_type, col_desc = _column_parts(col)
        if not col_name:
            continue
        payload = column_embedding_text(object_name, col_name, col_type, col_desc)
        rows.append(
            {
                "data_source_id": data_source_id,
                "key": schema_object_key(data_source_id, schema_name, object_name, col_name),
                "schema_name": schema_name,
                "object_name": object_name,
                "object_type": object_type,
                "entity_type": "Column",
                "column_name": col_name,
                "description": payload,
                "vector": embed_text(payload, provider, data_source_id),
            }
        )
    return rows


def delete_schema_object_rows(provider, data_source_id: str, schema_name: str, object_name: str) -> None:
    rows = provider.fetch_all("schemas", data_source_id)
    for row in rows:
        if row.get("schema_name") == schema_name and row.get("object_name") == object_name:
            key = row.get("key")
            if key:
                provider.delete("schemas", data_source_id, "key", key)
