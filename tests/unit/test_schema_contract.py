from pathlib import Path
import tempfile

from app.core.constants import VECTOR_SCHEMA_VERSION
from app.services.stores.schema_contracts import ADDED_FIELDS_VS_BUILTIN, COLLECTIONS, COLLECTION_BY_NAME, PARTITION_FIELD, RETIRED_COLLECTIONS, RUNTIME_VECTOR_COLLECTIONS, sqlite_ddl, schema_object_key
from app.services.stores.sqlite_vec_provider import SqliteVecProvider


REQUIRED = {
    "schemas",
    "few_shots",
    "contribution_library",
    "value_index",
    "data_group_metadata",
    "data_group_vectors_cache",
    "vec_data_group_queries",
    "semantic_models",
    "embedding_cache",
}


def test_schema_contract_adds_only_data_source_id():
    assert ADDED_FIELDS_VS_BUILTIN == (PARTITION_FIELD,)
    names = {c.name for c in COLLECTIONS}
    assert REQUIRED.issubset(names)
    assert "few_shots_meta" not in names
    assert "few_shots_meta" in RETIRED_COLLECTIONS
    assert set(RUNTIME_VECTOR_COLLECTIONS).issubset(names)
    for spec in COLLECTIONS:
        assert spec.fields[0].name == PARTITION_FIELD
        ddl = sqlite_ddl(spec)
        assert PARTITION_FIELD in ddl
        assert VECTOR_SCHEMA_VERSION


def test_schemas_has_column_entity_fields():
    schemas = COLLECTION_BY_NAME["schemas"]
    field_names = [f.name for f in schemas.fields]
    assert "entity_type" in field_names
    assert "column_name" in field_names
    assert any(f.vector_dim == 1536 for f in schemas.fields)


def test_sqlite_isolation_two_sources(tmp_path):
    provider = SqliteVecProvider(tmp_path / "v.sqlite")
    provider.upsert(
        "few_shots",
        [
            {"data_source_id": "A", "key": "1", "question": "q", "sql": "SELECT 1", "created_at_utc": "t", "vector": ""},
            {"data_source_id": "B", "key": "1", "question": "q", "sql": "SELECT 2", "created_at_utc": "t", "vector": ""},
        ],
    )
    a = provider.fetch_all("few_shots", "A")
    b = provider.fetch_all("few_shots", "B")
    assert len(a) == 1 and a[0]["sql"] == "SELECT 1"
    assert len(b) == 1 and b[0]["sql"] == "SELECT 2"
    provider.delete("few_shots", "A", "key", "1")
    assert provider.fetch_all("few_shots", "A") == []
    assert len(provider.fetch_all("few_shots", "B")) == 1


def test_sqlite_ensure_schema_drops_retired_few_shots_meta(tmp_path):
    provider = SqliteVecProvider(tmp_path / "v.sqlite")
    provider.execute("CREATE TABLE few_shots_meta (key TEXT)")
    assert provider.has_collection("few_shots_meta")
    provider.ensure_schema()
    assert not provider.has_collection("few_shots_meta")


def test_schema_object_key_matches_builtin_format():
    assert schema_object_key("nw", "dbo", "Customers") == "[nw].[dbo].[Customers]"
    assert schema_object_key("nw", "dbo", "Customers", "Country") == "[nw].[dbo].[Customers].[Country]"
