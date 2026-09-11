from unittest.mock import patch

from app.models.schemas import ColumnInfo, TableSchema
from app.services.stores.schema_contracts import schema_object_key
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.services.vector_store import MilvusVectorStore


class _Emb:
    dimensions = 1536
    provider = "openai"
    model = "text-embedding-3-small"
    api_key = None
    base_url = None


class _Settings:
    embedding_config = _Emb()


def _store(tmp_path, source_id="src1"):
    provider = SqliteVecProvider(tmp_path / "v.sqlite")
    provider._connected = True
    with patch("app.services.vector_store.get_vector_provider", return_value=provider), \
         patch("app.services.vector_store.load_settings", return_value=_Settings()), \
         patch("app.services.vector_store.EmbeddingFactory.create_client", side_effect=Exception("no embed")), \
         patch.object(MilvusVectorStore, "_ensure_contributions_collection", lambda self: None), \
         patch.object(MilvusVectorStore, "_resolve_default_source_guid", lambda self: source_id):
        store = MilvusVectorStore()
        store.provider = provider
        store._connected = True
        store._resolve_default_source_guid = lambda: source_id
        return store, provider


def test_insert_schema_writes_parent_and_column_contract_fields(tmp_path):
    store, provider = _store(tmp_path)
    schema = TableSchema(
        schema_name="dbo",
        table_name="Customers",
        table_type="table",
        description="Customer master",
        columns=[ColumnInfo(name="Country", data_type="nvarchar", description="ISO country")],
        source_guid="src1",
    )
    store.insert_schema_embedding(schema, "Customer master")
    rows = provider.fetch_all("schemas", "src1")
    assert rows
    for row in rows:
        assert row["data_source_id"] == "src1"
        assert "source_guid" not in row or row.get("source_guid") in (None, "", "src1")
        assert "embedding" not in row or row.get("embedding") in (None, "")
        assert row.get("key")
        assert row.get("object_name") == "Customers"
    entities = {row["entity_type"] for row in rows}
    assert "Table" in entities
    assert "Column" in entities
    col = next(r for r in rows if r["entity_type"] == "Column")
    assert col["column_name"] == "Country"
    assert col["key"] == schema_object_key("src1", "dbo", "Customers", "Country")


def test_fewshot_upsert_uses_sql_and_key_not_sql_query(tmp_path):
    store, provider = _store(tmp_path)
    store.insert_fewshot_item("How many customers?", "SELECT COUNT(*) FROM dbo.Customers", source_guid="src1")
    rows = provider.fetch_all("few_shots", "src1")
    assert len(rows) == 1
    assert rows[0]["sql"] == "SELECT COUNT(*) FROM dbo.Customers"
    assert "sql_query" not in rows[0] or rows[0].get("sql_query") in (None, "")
    assert rows[0]["key"]
    listed = store.get_all_fewshots()
    assert listed[0]["sql_query"] == "SELECT COUNT(*) FROM dbo.Customers"
    assert listed[0]["id"] == rows[0]["key"]
    store.delete_fewshot_item(rows[0]["key"])
    assert provider.fetch_all("few_shots", "src1") == []


def test_value_index_substring_and_delete_by_key(tmp_path):
    store, provider = _store(tmp_path)
    store.insert_value_item("USA", "dbo", "Customers", "Country", source_guid="src1")
    rows = provider.fetch_all("value_index", "src1")
    assert len(rows) == 1
    assert rows[0]["plain_value"] == "usa"
    assert rows[0]["data_source_id"] == "src1"
    hits = store.search_values("usa")
    assert hits and hits[0]["value"] == "USA"
    listed = store.get_all_values()
    store.delete_value_item(listed[0]["id"])
    assert provider.fetch_all("value_index", "src1") == []


def test_facade_has_no_legacy_ensure_droppers():
    assert not hasattr(MilvusVectorStore, "_ensure_values_collection")
    assert not hasattr(MilvusVectorStore, "_ensure_schema_collection")
    assert not hasattr(MilvusVectorStore, "_ensure_fewshot_collection")
    assert not hasattr(MilvusVectorStore, "_ensure_schema_v2_collection")
