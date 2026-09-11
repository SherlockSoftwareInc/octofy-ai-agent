from app.core.orchestrator.builtin_sql_generator import generate_r_builtin
from app.models.schemas import GenerateSQLRequest
from app.services.stores.bundle import build_source_stores
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.models.pipeline import TokenUsage
from app.utils.r_normalization import extract_sql_from_r, looks_like_r, wrap_sql_as_r


class FakeLlm:
    token_usage = TokenUsage()

    def complete(self, messages, **kwargs):
        return "```r\nlibrary(DBI)\nresult <- data.frame()\n```"

    def complete_json(self, messages, **kwargs):
        return {"intent": "off_topic"}


def test_r_kb_exact_wraps_sql(tmp_path):
    provider = SqliteVecProvider(tmp_path / "r.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.fewshots.upsert("count customers", "SELECT COUNT(*) FROM dbo.Customers")
    req = GenerateSQLRequest(query="count customers")
    events = list(generate_r_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "kb_exact"
    assert payload["attempts"] == 0
    assert payload["success"] is True
    assert payload["query_type"] == "r_code"
    assert "COUNT(*)" in payload["sql"]
    assert "dbGetQuery" in payload["sql"]
    assert "library(DBI)" in payload["sql"]
    assert any(e.get("type") == "done" for e in events)


def test_r_force_general_conversational(tmp_path):
    provider = SqliteVecProvider(tmp_path / "r2.sqlite")
    stores = build_source_stores("s1", provider=provider)
    req = GenerateSQLRequest(query="tell me a joke", forceGeneral=True)
    events = list(generate_r_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "off_topic"
    assert payload["query_type"] == "general"


def test_r_priority_validation_failed(tmp_path):
    provider = SqliteVecProvider(tmp_path / "rpins.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.catalog.list_objects = lambda force=False: []
    stores.catalog.object_exists = lambda s, n: False
    stores.catalog.find_closest = lambda name, limit=5: []
    req = GenerateSQLRequest(query="show customers", database_objects=["dbo.NoSuchTable"])
    events = list(generate_r_builtin(req, stores, llm=FakeLlm()))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]
    assert payload["discovery_branch"] == "priority_validation_failed"
    assert payload["success"] is False
    assert payload["error_category"] == "priority_validation_failed"
    assert payload["query_type"] == "r_code"


def test_wrap_sql_as_r_extracts_sql():
    sql = "SELECT COUNT(*) FROM dbo.Customers"
    code = wrap_sql_as_r(sql)
    assert looks_like_r(code)
    extracted = extract_sql_from_r(code)[0].replace("\n", " ").strip()
    assert "SELECT COUNT(*)" in extracted
    assert "dbo.Customers" in extracted
