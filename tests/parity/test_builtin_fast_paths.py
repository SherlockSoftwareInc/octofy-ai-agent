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
        return {"intent": "off_topic"}


def test_kb_exact_zero_attempts(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "gen.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.fewshots.upsert("count customers", "SELECT COUNT(*) FROM dbo.Customers")
    req = GenerateSQLRequest(query="count customers")
    events = list(generate_sql_builtin(req, stores, llm=FakeLlm()))
    result_events = [e for e in events if e.get("type") == "result"]
    assert result_events
    payload = result_events[0]["payload"]
    assert payload["discovery_branch"] == "kb_exact"
    assert payload["attempts"] == 0
    assert payload["success"] is True
    assert "COUNT(*)" in payload["sql"]
    assert any(e.get("type") == "done" for e in events)
    statuses = [e for e in events if e.get("type") == "status"]
    assert statuses and statuses[0]["payload"]["stage"] == "routing"


def test_force_general_conversational(tmp_path):
    provider = SqliteVecProvider(tmp_path / "gen2.sqlite")
    stores = build_source_stores("s1", provider=provider)
    req = GenerateSQLRequest(query="tell me a joke", forceGeneral=True)
    events = list(generate_sql_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "off_topic"
    assert payload["query_type"] == "general"
