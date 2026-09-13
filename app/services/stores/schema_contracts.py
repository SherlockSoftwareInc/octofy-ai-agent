"""Vector-index schema contract. Built-in table names plus data_source_id only."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.constants import EmbeddingDimensions, VECTOR_SCHEMA_VERSION

SCHEMA_VERSION = VECTOR_SCHEMA_VERSION
VECTOR_DIM = EmbeddingDimensions
PARTITION_FIELD = "data_source_id"
METRIC = "COSINE"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    primary: bool = False
    vector_dim: Optional[int] = None
    not_null: bool = False
    default: Optional[str] = None


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    kind: str  # vector | scalar | json_vector
    fields: List[FieldSpec]
    vector_fields: List[str] = field(default_factory=list)
    unique_with_source: List[str] = field(default_factory=list)


def _ds() -> FieldSpec:
    return FieldSpec(PARTITION_FIELD, "TEXT", not_null=True)


COLLECTIONS: List[CollectionSpec] = [
    CollectionSpec(
        name="schemas",
        kind="vector",
        fields=[
            _ds(),
            FieldSpec("key", "TEXT", primary=True),
            FieldSpec("schema_name", "TEXT"),
            FieldSpec("object_name", "TEXT"),
            FieldSpec("object_type", "TEXT"),
            FieldSpec("entity_type", "TEXT"),
            FieldSpec("column_name", "TEXT"),
            FieldSpec("description", "TEXT"),
            FieldSpec("vector", "FLOAT_VECTOR", vector_dim=VECTOR_DIM),
        ],
        vector_fields=["vector"],
        unique_with_source=["key"],
    ),
    CollectionSpec(
        name="few_shots",
        kind="vector",
        fields=[
            _ds(),
            FieldSpec("key", "TEXT", primary=True),
            FieldSpec("question", "TEXT"),
            FieldSpec("sql", "TEXT"),
            FieldSpec("created_at_utc", "TEXT"),
            FieldSpec("vector", "FLOAT_VECTOR", vector_dim=VECTOR_DIM),
        ],
        vector_fields=["vector"],
        unique_with_source=["key"],
    ),
    CollectionSpec(
        name="contribution_library",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("key", "TEXT", primary=True),
            FieldSpec("question", "TEXT", not_null=True),
            FieldSpec("sql_query", "TEXT", not_null=True),
            FieldSpec("knowledge_type", "TEXT", not_null=True),
            FieldSpec("user_id", "TEXT"),
            FieldSpec("submitted_at", "TEXT"),
            FieldSpec("status", "TEXT", not_null=True),
        ],
        unique_with_source=["key"],
    ),
    CollectionSpec(
        name="value_index",
        kind="vector",
        fields=[
            _ds(),
            FieldSpec("key", "TEXT", primary=True),
            FieldSpec("value", "TEXT"),
            FieldSpec("plain_value", "TEXT"),
            FieldSpec("schema_name", "TEXT"),
            FieldSpec("table_name", "TEXT"),
            FieldSpec("column_name", "TEXT"),
            FieldSpec("vector", "FLOAT_VECTOR", vector_dim=VECTOR_DIM),
        ],
        vector_fields=["vector"],
        unique_with_source=["key"],
    ),
    CollectionSpec(
        name="data_group_metadata",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("group_id", "TEXT", primary=True),
            FieldSpec("group_name", "TEXT", not_null=True),
            FieldSpec("description", "TEXT", not_null=True),
            FieldSpec("keywords_json", "TEXT", not_null=True),
            FieldSpec("members_json", "TEXT", not_null=True),
            FieldSpec("updated_at_utc", "TEXT", not_null=True),
        ],
        unique_with_source=["group_id"],
    ),
    CollectionSpec(
        name="data_group_vectors_cache",
        kind="json_vector",
        fields=[
            _ds(),
            FieldSpec("group_id", "TEXT", primary=True),
            FieldSpec("semantic_vector_json", "TEXT", not_null=True),
            FieldSpec("functional_vector_json", "TEXT", not_null=True),
            FieldSpec("object_vector_json", "TEXT", not_null=True),
            FieldSpec("updated_at_utc", "TEXT", not_null=True),
        ],
        unique_with_source=["group_id"],
    ),
    CollectionSpec(
        name="data_group_vectors_map",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("group_id", "TEXT", primary=True),
            FieldSpec("vec_rowid", "INTEGER", not_null=True),
        ],
        unique_with_source=["group_id"],
    ),
    CollectionSpec(
        name="data_group_vectors_vec0",
        kind="vector",
        fields=[
            _ds(),
            FieldSpec("rowid", "INTEGER", primary=True),
            FieldSpec("semantic_vector", "FLOAT_VECTOR", vector_dim=VECTOR_DIM),
            FieldSpec("functional_vector", "FLOAT_VECTOR", vector_dim=VECTOR_DIM),
            FieldSpec("object_vector", "FLOAT_VECTOR", vector_dim=VECTOR_DIM),
        ],
        vector_fields=["semantic_vector", "functional_vector", "object_vector"],
    ),
    CollectionSpec(
        name="vec_data_group_queries",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("query_id", "TEXT", primary=True),
            FieldSpec("group_name", "TEXT", not_null=True),
            FieldSpec("group_file_name", "TEXT", not_null=True),
            FieldSpec("question", "TEXT", not_null=True),
            FieldSpec("sql_query", "TEXT", not_null=True),
            FieldSpec("smq_query", "TEXT", default="''"),
            FieldSpec("status", "TEXT", not_null=True),
            FieldSpec("updated_at_utc", "TEXT", not_null=True),
        ],
        unique_with_source=["query_id"],
    ),
    CollectionSpec(
        name="vec_data_group_query_vectors_cache",
        kind="json_vector",
        fields=[
            _ds(),
            FieldSpec("query_id", "TEXT", primary=True),
            FieldSpec("question_vector_json", "TEXT", not_null=True),
            FieldSpec("updated_at_utc", "TEXT", not_null=True),
        ],
        unique_with_source=["query_id"],
    ),
    CollectionSpec(
        name="embedding_cache",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("text_hash", "TEXT", primary=True),
            FieldSpec("text_content", "TEXT", not_null=True),
            FieldSpec("embedding_json", "TEXT", not_null=True),
            FieldSpec("embedding_model", "TEXT", not_null=True),
            FieldSpec("created_at_utc", "TEXT", not_null=True),
            FieldSpec("last_accessed_utc", "TEXT", not_null=True),
            FieldSpec("access_count", "INTEGER", default="1"),
        ],
        unique_with_source=["text_hash"],
    ),
    CollectionSpec(
        name="semantic_models",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("model_id", "TEXT", primary=True),
            FieldSpec("label", "TEXT", not_null=True),
            FieldSpec("is_active", "INTEGER", not_null=True, default="1"),
            FieldSpec("updated_at_utc", "TEXT", not_null=True),
        ],
        unique_with_source=["model_id"],
    ),
    CollectionSpec(
        name="semantic_measures",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("model_id", "TEXT", not_null=True),
            FieldSpec("measure_name", "TEXT", not_null=True),
            FieldSpec("expression", "TEXT", not_null=True),
            FieldSpec("description", "TEXT", not_null=True),
        ],
        unique_with_source=["model_id", "measure_name"],
    ),
    CollectionSpec(
        name="semantic_dimensions",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("model_id", "TEXT", not_null=True),
            FieldSpec("dimension_name", "TEXT", not_null=True),
            FieldSpec("column_name", "TEXT", not_null=True),
            FieldSpec("table_name", "TEXT", not_null=True),
            FieldSpec("description", "TEXT", not_null=True),
        ],
        unique_with_source=["model_id", "dimension_name"],
    ),
    CollectionSpec(
        name="semantic_joins",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("model_id", "TEXT", not_null=True),
            FieldSpec("from_table", "TEXT", not_null=True),
            FieldSpec("to_table", "TEXT", not_null=True),
            FieldSpec("join_expression", "TEXT", not_null=True),
            FieldSpec("join_type", "TEXT", not_null=True),
        ],
        unique_with_source=["model_id", "from_table", "to_table", "join_expression"],
    ),
    CollectionSpec(
        name="semantic_governance_predicates",
        kind="scalar",
        fields=[
            _ds(),
            FieldSpec("model_id", "TEXT", not_null=True),
            FieldSpec("predicate", "TEXT", not_null=True),
            FieldSpec("description", "TEXT", default="''"),
        ],
    ),
    CollectionSpec(
        name="semantic_embeddings",
        kind="json_vector",
        fields=[
            _ds(),
            FieldSpec("model_id", "TEXT", primary=True),
            FieldSpec("embedding_json", "TEXT", not_null=True),
            FieldSpec("updated_at_utc", "TEXT", not_null=True),
        ],
        unique_with_source=["model_id"],
    ),
]

COLLECTION_BY_NAME: Dict[str, CollectionSpec] = {c.name: c for c in COLLECTIONS}

# Collections the runtime must be able to read/write after ensure_schema.
RUNTIME_VECTOR_COLLECTIONS = (
    "schemas",
    "few_shots",
    "value_index",
    "contribution_library",
)

# Dropped from the contract; providers remove leftover tables/collections on ensure_schema.
RETIRED_COLLECTIONS = ("few_shots_meta",)

ADDED_FIELDS_VS_BUILTIN = (PARTITION_FIELD,)


def sqlite_ddl(spec: CollectionSpec) -> str:
    cols = []
    pk_fields = [f.name for f in spec.fields if f.primary]
    for f in spec.fields:
        sql_type = "BLOB" if f.type == "FLOAT_VECTOR" else f.type
        if sql_type == "INTEGER" and f.primary and len(pk_fields) == 1:
            piece = f"{f.name} INTEGER PRIMARY KEY"
        else:
            piece = f"{f.name} {sql_type}"
            if f.not_null:
                piece += " NOT NULL"
            if f.default is not None:
                piece += f" DEFAULT {f.default}"
        cols.append(piece)
    unique_cols = [PARTITION_FIELD] + list(spec.unique_with_source) if spec.unique_with_source else []
    extras = []
    if pk_fields == ["rowid"]:
        pass
    elif unique_cols:
        extras.append(f"PRIMARY KEY ({', '.join(unique_cols)})")
    elif pk_fields:
        extras.append(f"PRIMARY KEY ({', '.join(pk_fields)})")
    body = ",\n  ".join(cols + extras)
    return f"CREATE TABLE IF NOT EXISTS {spec.name} (\n  {body}\n)"


def schema_object_key(
    data_source_id: str,
    schema_name: str,
    object_name: str,
    column_name: str = "",
) -> str:
    key = f"[{data_source_id}].[{schema_name}].[{object_name}]"
    if column_name:
        return f"{key}.[{column_name}]"
    return key


def normalize_object_type(raw: Optional[str]) -> str:
    value = (raw or "Table").strip()
    if value in {"Table", "View", "Function"}:
        return value
    mapping = {
        "table": "Table",
        "view": "View",
        "function": "Function",
        "stored_procedure": "Function",
        "storedprocedure": "Function",
    }
    return mapping.get(value.lower(), "Table")


def object_type_to_table_type(object_type: str) -> str:
    mapping = {"Table": "table", "View": "view", "Function": "function"}
    return mapping.get(object_type, (object_type or "table").lower())


def parent_embedding_text(object_type: str, object_name: str, description: str) -> str:
    entity = object_type if object_type in {"Table", "View", "Function"} else "Table"
    return f"Entity: {entity} | Name: {object_name} | Description: {description or ''}"


def column_embedding_text(object_name: str, column_name: str, data_type: str, description: str, values: str = "") -> str:
    payload = (
        f"Entity: Column | Table: {object_name} | Name: {column_name} | "
        f"Type: {data_type or ''} | Description: {description or ''}"
    )
    if values:
        payload += f" | Values: {values}"
    return payload


def column_name_first_embedding(column_name: str, description: str, values: str = "") -> str:
    text = f"{column_name} | {description or ''}"
    if values:
        text += f" | Values: {values}"
    return text


def semantic_embedding_source(label: str, measures, dimensions, governance) -> str:
    meas = " ".join(
        f"measure({m.name}:{m.description}:{m.expression})" for m in measures
    )
    dims = " ".join(
        f"dimension({d.name}:{d.description}:{d.table}.{d.column})" for d in dimensions
    )
    gov = " ".join(f"governance({g})" for g in governance)
    return f"{label} | {meas} | {dims} | {gov}"
