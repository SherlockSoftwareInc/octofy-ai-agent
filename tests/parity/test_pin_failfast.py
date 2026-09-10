from app.core.orchestrator.builtin_sql_generator import generate_sql_builtin
from app.models.schemas import GenerateSQLRequest
from app.services.stores.bundle import build_source_stores
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.models.pipeline import TokenUsage


class FakeLlm:
    token_usage = TokenUsage()

    def complete(self, messages, **kwargs):
        return "```sql\nSELECT 1\n```"

    def complete_json(self, messages, **kwargs):
        return {}


def test_priority_validation_failed(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "pins.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.catalog.list_objects = lambda force=False: []
    stores.catalog.object_exists = lambda s, n: False
    stores.catalog.find_closest = lambda name, limit=5: []
    req = GenerateSQLRequest(query="show customers", database_objects=["dbo.NoSuchTable"])
    events = list(generate_sql_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "priority_validation_failed"
    assert payload["success"] is False
    assert payload["error_category"] == "priority_validation_failed"
