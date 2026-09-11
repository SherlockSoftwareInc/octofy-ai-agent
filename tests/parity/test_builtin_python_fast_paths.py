from app.core.orchestrator.builtin_sql_generator import generate_python_builtin
from app.models.schemas import GenerateSQLRequest
from app.services.stores.bundle import build_source_stores
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.models.pipeline import TokenUsage
from app.utils.python_normalization import extract_sql_from_python, looks_like_python, wrap_sql_as_python


class FakeLlm:
    token_usage = TokenUsage()

    def complete(self, messages, **kwargs):
        return '```python\nimport pandas as pd\nfinal_result_df = pd.DataFrame()\n```'

    def complete_json(self, messages, **kwargs):
        return {"intent": "off_topic"}


def test_python_kb_exact_wraps_sql(tmp_path):
    provider = SqliteVecProvider(tmp_path / "py.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.fewshots.upsert("count customers", "SELECT COUNT(*) FROM dbo.Customers")
    req = GenerateSQLRequest(query="count customers")
    events = list(generate_python_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "kb_exact"
    assert payload["attempts"] == 0
    assert payload["success"] is True
    assert payload["query_type"] == "python_code"
    assert "COUNT(*)" in payload["sql"]
    assert "pd.read_sql" in payload["sql"]
    assert "final_result_df" in payload["sql"]
    assert any(e.get("type") == "done" for e in events)


def test_python_force_general_conversational(tmp_path):
    provider = SqliteVecProvider(tmp_path / "py2.sqlite")
    stores = build_source_stores("s1", provider=provider)
    req = GenerateSQLRequest(query="tell me a joke", forceGeneral=True)
    events = list(generate_python_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "off_topic"
    assert payload["query_type"] == "general"


def test_python_priority_validation_failed(tmp_path):
    provider = SqliteVecProvider(tmp_path / "pypins.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.catalog.list_objects = lambda force=False: []
    stores.catalog.object_exists = lambda s, n: False
    stores.catalog.find_closest = lambda name, limit=5: []
    req = GenerateSQLRequest(query="show customers", database_objects=["dbo.NoSuchTable"])
    events = list(generate_python_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "priority_validation_failed"
    assert payload["success"] is False
    assert payload["error_category"] == "priority_validation_failed"
    assert payload["query_type"] == "python_code"


def test_wrap_sql_as_python_extracts_sql():
    sql = "SELECT COUNT(*) FROM dbo.Customers"
    code = wrap_sql_as_python(sql)
    assert looks_like_python(code)
    assert extract_sql_from_python(code)[0].replace("\n", " ").strip().startswith("SELECT COUNT(*)")
