"""Prepare SQLite rows and copy every contract table into Milvus."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.stores.schema_contracts import COLLECTIONS, COLLECTION_BY_NAME, CollectionSpec, PARTITION_FIELD
from app.services.stores.score_utils import dumps_vector, loads_vector

logger = logging.getLogger(__name__)

MAX_VARCHAR = 65535
UPSERT_BATCH = 50
# Milvus requires at least one FLOAT_VECTOR field on every collection.
DUMMY_VECTOR_FIELD = "_pad_vector"
DUMMY_VECTOR_DIM = 2
DUMMY_VECTOR = [0.0, 0.0]


def uses_native_vector(spec: CollectionSpec) -> bool:
    """Milvus standalone can index only one FLOAT_VECTOR field per collection."""
    return spec.kind == "vector" and len(spec.vector_fields) == 1


def needs_dummy_vector(spec: CollectionSpec) -> bool:
    return not uses_native_vector(spec)


def resolve_data_source_id(row: Dict[str, Any]) -> str:
    for key in (PARTITION_FIELD, "source_id", "source_guid"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def milvus_schema_field_names(spec: CollectionSpec) -> List[str]:
    """Every Milvus collection is pk + data_source_id + contract fields (except rowid)."""
    names = ["pk", PARTITION_FIELD]
    for field in spec.fields:
        if field.name in {PARTITION_FIELD, "rowid"}:
            continue
        names.append(field.name)
    if needs_dummy_vector(spec):
        names.append(DUMMY_VECTOR_FIELD)
    return names


def row_pk(spec: CollectionSpec, row: Dict[str, Any]) -> str:
    if spec.unique_with_source:
        parts = [str(row.get(PARTITION_FIELD) or "")]
        parts.extend(str(row.get(name) or "") for name in spec.unique_with_source)
        return "|".join(parts)[:1024]
    for candidate in ("key", "query_id", "group_id", "model_id", "text_hash", "rowid", "pk"):
        if row.get(candidate) is not None and row.get(candidate) != "":
            return str(row[candidate])[:1024]
    return "|".join(str(row.get(f.name) or "") for f in spec.fields)[:1024]


def _as_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_varchar(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if len(text) > MAX_VARCHAR:
        return text[:MAX_VARCHAR]
    return text


def _as_vector(value: Any) -> List[float]:
    if isinstance(value, list):
        return [float(x) for x in value]
    return loads_vector(value)


def prepare_milvus_row(spec: CollectionSpec, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one SQLite row to the Milvus field set. Returns None if a required vector is missing."""
    source_id = resolve_data_source_id(row)
    if not source_id:
        return None
    native = uses_native_vector(spec)
    out: Dict[str, Any] = {PARTITION_FIELD: source_id}
    for field in spec.fields:
        if field.name in {PARTITION_FIELD, "rowid"}:
            continue
        value = row.get(field.name)
        if field.type == "FLOAT_VECTOR":
            if native and field.name in spec.vector_fields:
                vec = _as_vector(value)
                if not vec:
                    return None
                out[field.name] = vec
            elif isinstance(value, list):
                out[field.name] = dumps_vector(value)
            else:
                out[field.name] = _as_varchar(value or "[]")
        elif field.type == "INTEGER":
            out[field.name] = _as_int(value)
        else:
            out[field.name] = _as_varchar(value)
    out["pk"] = row_pk(spec, {**row, PARTITION_FIELD: source_id})
    if needs_dummy_vector(spec):
        out[DUMMY_VECTOR_FIELD] = list(DUMMY_VECTOR)
    return out


def replicate_sqlite_to_milvus(sqlite, milvus) -> Dict[str, int]:
    """Drop is the caller's job. Copy every SQLite contract table into Milvus."""
    counts: Dict[str, int] = {}
    for spec in COLLECTIONS:
        try:
            raw_rows = sqlite.fetch_all_rows(spec.name)
        except Exception as exc:
            logger.warning("read sqlite %s failed: %s", spec.name, exc)
            counts[spec.name] = 0
            continue
        prepared: List[Dict[str, Any]] = []
        for row in raw_rows:
            rec = prepare_milvus_row(spec, row)
            if rec:
                prepared.append(rec)
        if prepared:
            for start in range(0, len(prepared), UPSERT_BATCH):
                milvus.upsert(spec.name, prepared[start : start + UPSERT_BATCH])
        counts[spec.name] = len(prepared)
        logger.info("replicated %s: %s rows", spec.name, len(prepared))
    return counts


def collection_spec(name: str) -> Optional[CollectionSpec]:
    return COLLECTION_BY_NAME.get(name)
