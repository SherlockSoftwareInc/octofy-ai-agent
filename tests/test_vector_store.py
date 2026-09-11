import pytest
from unittest.mock import patch

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


class TestInsertFewshotItem:
    """Few-shot writes go through the contract few_shots collection."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        provider = SqliteVecProvider(tmp_path / "v.sqlite")
        provider._connected = True
        with patch("app.services.vector_store.get_vector_provider", return_value=provider), \
             patch("app.services.vector_store.load_settings", return_value=_Settings()), \
             patch("app.services.vector_store.EmbeddingFactory.create_client", side_effect=Exception("no embed")), \
             patch.object(MilvusVectorStore, "_resolve_default_source_guid", lambda self: "src1"):
            store = MilvusVectorStore()
            store.provider = provider
            store._connected = True
            store._resolve_default_source_guid = lambda: "src1"
            store._test_provider = provider
            return store

    def test_insert_fewshot_item_success(self, vector_store):
        question = "What is the total sales for last month?"
        sql_query = "SELECT SUM(amount) FROM sales WHERE date >= DATEADD(MONTH, -1, GETDATE())"
        vector_store.insert_fewshot_item(question, sql_query)
        rows = vector_store._test_provider.fetch_all("few_shots", "src1")
        assert len(rows) == 1
        assert rows[0]["question"] == question
        assert rows[0]["sql"] == sql_query
        assert rows[0]["data_source_id"] == "src1"

    def test_insert_fewshot_item_with_special_characters(self, vector_store):
        question = "Find customers with email containing '@gmail.com'?"
        sql_query = "SELECT * FROM customers WHERE email LIKE '%@gmail.com%'"
        vector_store.insert_fewshot_item(question, sql_query)
        rows = vector_store._test_provider.fetch_all("few_shots", "src1")
        assert rows[0]["sql"] == sql_query

    def test_insert_fewshot_item_empty_strings(self, vector_store):
        vector_store.insert_fewshot_item("", "", source_guid="src1")
        rows = vector_store._test_provider.fetch_all("few_shots", "src1")
        assert len(rows) == 1

    def test_insert_fewshot_item_uses_few_shots_collection(self, vector_store):
        vector_store.insert_fewshot_item("Test question", "SELECT 1", source_guid="src1")
        names = {c.name for c in vector_store._test_provider.fetch_all("few_shots", "src1") and []}
        rows = vector_store._test_provider.fetch_all("few_shots", "src1")
        assert rows
        assert "sql" in rows[0]
        assert "vector" in rows[0]
