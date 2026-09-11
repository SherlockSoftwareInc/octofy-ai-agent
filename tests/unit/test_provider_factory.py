from unittest.mock import patch

from app.services.stores.provider_factory import get_vector_provider
from app.services.stores.sqlite_vec_provider import SqliteVecProvider


def test_factory_falls_back_to_sqlite_when_milvus_disconnected(tmp_path, monkeypatch):
    get_vector_provider.cache_clear()
    monkeypatch.setattr("app.core.config.settings.VECTOR_PROVIDER", "milvus")
    monkeypatch.setattr(
        "app.services.stores.sqlite_vec_provider.default_sqlite_path",
        lambda: tmp_path / "vector-index.sqlite",
    )

    class _Disconnected:
        _connected = False

    with patch("app.services.stores.milvus_provider.MilvusProvider", return_value=_Disconnected()):
        provider = get_vector_provider()

    try:
        assert isinstance(provider, SqliteVecProvider)
        assert provider._connected is True
        provider.upsert(
            "contribution_library",
            [{
                "data_source_id": "src1",
                "key": "c1",
                "question": "q",
                "sql_query": "SELECT 1",
                "knowledge_type": "sql_query",
                "user_id": "anonymous",
                "submitted_at": "2026-01-01T00:00:00+00:00",
                "status": "pending",
            }],
        )
        rows = provider.fetch_all("contribution_library", "src1")
        assert len(rows) == 1
        assert rows[0]["sql_query"] == "SELECT 1"
    finally:
        get_vector_provider.cache_clear()
