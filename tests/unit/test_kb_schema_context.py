"""KB limit adaptation, schema re-hydration, and multi-word object recovery."""

from app.core.constants import KbRequiredObjectScore
from app.core.orchestrator.attempts import run_attempt_loop
from app.core.orchestrator.builtin_sql_generator import generate_sql_builtin
from app.core.orchestrator.discovery_engine import DiscoveryEngine
from app.models.pipeline import (
    AgentContext,
    AgentRequest,
    DiscoveryResult,
    FewShotExample,
    ScoredObject,
    TokenUsage,
)
from app.models.schemas import GenerateSQLRequest
from app.services.skills_service import SkillsService
from app.services.stores.bundle import build_source_stores
from app.services.stores.sqlite_vec_provider import SqliteVecProvider

VIEW_DDL = "KB_VIEW_DDL_Sales_by_Category"
CANDIDATE_SQL = "SELECT CategoryName FROM [dbo].[Sales by Category]"


class RecordingLlm:
    def __init__(self, sql: str = "SELECT 1 AS n"):
        self.token_usage = TokenUsage()
        self.calls = []
        self._sql = sql

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return f"```sql\n{self._sql}\n```"

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        return {}

    def system_prompts(self):
        return [m[0]["content"] for m in self.calls if m and m[0].get("role") == "system"]


class Catalog:
    def object_exists(self, schema_name, object_name):
        return (schema_name or "").lower() == "dbo" and object_name == "Sales by Category"

    def list_objects(self):
        return [{"schema_name": "dbo", "object_name": "Sales by Category", "object_type": "View"}]

    def find_closest(self, name, limit=5):
        return []


class VectorSearch:
    def __init__(self):
        self.queries = []

    def search_objects(self, query, top_k=8, **kwargs):
        self.queries.append(query)
        return []


class Semantic:
    def search_models(self, query, top_k=2):
        return []

    def is_enabled(self, flag=None):
        return False

    def get_active_model(self):
        return None


class Stores:
    def __init__(self):
        self.catalog = Catalog()
        self.vector_search = VectorSearch()
        self.semantic = Semantic()


def _drive(loop):
    while True:
        try:
            next(loop)
        except StopIteration as done:
            return done.value


def _lookup(source_id, objects):
    found = {}
    for obj in objects or []:
        if obj.object_name == "Sales by Category":
            found[f"{obj.schema_name}.{obj.object_name}".lower()] = VIEW_DDL
    return found


def test_limit_only_kb_hit_hydrates_from_objects_before_attempt_1(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "kb.sqlite")
    stores = build_source_stores("s1", provider=provider)
    provider.upsert(
        "few_shots",
        [{
            "data_source_id": "s1",
            "key": "k1",
            "question": "find top selling products",
            "sql": CANDIDATE_SQL,
            "created_at_utc": "2020-01-01T00:00:00+00:00",
            "vector": "",
        }],
    )
    monkeypatch.setattr(
        DiscoveryEngine,
        "discover",
        lambda self, query, analysis, **kwargs: DiscoveryResult(
            objects=[ScoredObject(schema_name="dbo", object_name="Category Sales for 1997", score=0.4)],
            branch="dual_prong",
        ),
    )
    monkeypatch.setattr(
        "app.core.orchestrator.builtin_sql_generator.markdown_lookup_for_objects",
        _lookup,
    )
    monkeypatch.setattr(
        "app.services.sql_validator.SqlValidator.validate",
        lambda self, sql, allowed_objects=None, skip_object_scope=False: (True, "", []),
    )
    llm = RecordingLlm(CANDIDATE_SQL)
    events = list(generate_sql_builtin(GenerateSQLRequest(query="find top 10 selling products"), stores, llm=llm))
    payload = [e for e in events if e.get("type") == "result"][0]["payload"]

    assert payload["discovery_branch"] != "kb_exact"
    assert payload["attempts"] != 0
    prompts = [text for text in llm.system_prompts() if "AVAILABLE SCHEMAS" in text]
    assert prompts
    assert VIEW_DDL in prompts[0]
    assert "Sales by Category" in prompts[0]


def test_recovery_rehydrates_schema_and_critic_context(monkeypatch):
    monkeypatch.setattr(
        "app.services.stores.skills_folder.markdown_lookup_for_objects",
        _lookup,
    )
    calls = {"n": 0}

    def fake_validate(self, sql, allowed_objects=None, skip_object_scope=False):
        calls["n"] += 1
        if calls["n"] <= 2:
            return False, "TABLE_VALIDATION_ERROR: [dbo].[Sales by Category]", []
        return True, "", []

    monkeypatch.setattr("app.services.sql_validator.SqlValidator.validate", fake_validate)
    discovery = DiscoveryResult(
        objects=[ScoredObject(schema_name="dbo", object_name="Category Sales for 1997", score=0.5)],
        branch="dual_prong",
        schema_context="ONLY_CATEGORY_SALES_1997",
        schema_context_for_validation="ONLY_CATEGORY_SALES_1997",
    )
    context = AgentContext(
        request=AgentRequest(query="find top 10 selling products", source_id="s1"),
        combined_query="find top 10 selling products",
        dbms_type="SQL Server",
    )
    llm = RecordingLlm(CANDIDATE_SQL)
    stores = Stores()
    result = _drive(
        run_attempt_loop(context, discovery, stores, llm, lambda *a, **k: None)
    )

    assert result.success
    assert VIEW_DDL in discovery.schema_context
    assert VIEW_DDL in discovery.schema_context_for_validation
    prompts = [text for text in llm.system_prompts() if "AVAILABLE SCHEMAS" in text]
    assert VIEW_DDL not in prompts[0]
    assert VIEW_DDL in prompts[1]
    critic_schemas = [
        m[1]["content"]
        for m in llm.calls
        if len(m) > 1 and m[1].get("role") == "user" and "SCHEMA:" in m[1].get("content", "")
    ]
    assert critic_schemas
    assert any(VIEW_DDL in text for text in critic_schemas)
    assert "TABLE_VALIDATION_ERROR" not in stores.vector_search.queries
    recovered = [o for o in discovery.objects if o.object_name == "Sales by Category"]
    assert recovered and recovered[0].required


def test_kb_example_object_is_authorized_in_the_prompt_and_the_whitelist(monkeypatch):
    """A view used by a KB example is in scope even when discovery never hydrated it."""
    monkeypatch.setattr(
        "app.services.sql_validator.SqlValidator._sql_server",
        lambda self, sql: (True, "", []),
    )
    discovery = DiscoveryResult(
        objects=[ScoredObject(schema_name="dbo", object_name="Category Sales for 1997", score=0.4)],
        branch="dual_prong",
        few_shot_examples=[
            FewShotExample(
                question="find top selling products",
                sql=CANDIDATE_SQL,
                source="precomputed",
            )
        ],
        schema_context="ONLY_CATEGORY_SALES_1997",
    )
    context = AgentContext(
        request=AgentRequest(query="find top 10 selling products", source_id="s1"),
        combined_query="find top 10 selling products",
        dbms_type="SQL Server",
    )
    llm = RecordingLlm(CANDIDATE_SQL)
    result = _drive(run_attempt_loop(context, discovery, Stores(), llm, lambda *a, **k: None))

    assert result.success
    assert result.attempts == 1
    prompt = llm.system_prompts()[0]
    assert "AUTHORIZED OBJECT SCOPE" in prompt
    assert "PRECOMPUTED Q&A" in prompt
    assert "fully authorized" in prompt
    assert "ZERO HALLUCINATION POLICY" in prompt
    assert "treat them as whitelisted" in prompt
    assert "only when its column list" not in prompt.lower()


def test_object_absent_from_schema_and_examples_stays_out_of_scope(monkeypatch):
    monkeypatch.setattr(
        "app.services.sql_validator.SqlValidator._sql_server",
        lambda self, sql: (True, "", []),
    )
    discovery = DiscoveryResult(
        objects=[ScoredObject(schema_name="dbo", object_name="Products", score=0.4)],
        branch="dual_prong",
        few_shot_examples=[FewShotExample(question="q", sql=CANDIDATE_SQL)],
    )
    context = AgentContext(
        request=AgentRequest(query="invent a table", source_id="s1"),
        combined_query="invent a table",
        dbms_type="SQL Server",
    )
    llm = RecordingLlm("SELECT 1 FROM dbo.InventedThing")
    result = _drive(run_attempt_loop(context, discovery, Stores(), llm, lambda *a, **k: None))

    assert result.success is False
    reasons = " ".join(a.why_it_failed or "" for a in result.failure_report.attempts)
    assert "TABLE_VALIDATION_ERROR" in reasons
    assert "InventedThing" in reasons


def test_skills_title_keeps_spaces_in_the_object_name(tmp_path):
    path = tmp_path / "dbo.Sales by Category.md"
    path.write_text("# Table: [dbo].[Sales by Category]\n\n**Type:** View\n", encoding="utf-8")
    schema = SkillsService(str(tmp_path))._parse_table_schema_file(path)
    assert schema is not None
    assert schema.schema_name == "dbo"
    assert schema.table_name == "Sales by Category"


def test_example_objects_are_hard_locked_into_the_pool():
    """Ranking must not be able to drop an object an injected example depends on."""
    engine = DiscoveryEngine(Stores())
    result = DiscoveryResult(
        objects=[ScoredObject(schema_name="dbo", object_name="Category Sales for 1997", score=0.9)],
        branch="dual_prong",
        few_shot_examples=[FewShotExample(question="q", sql=CANDIDATE_SQL)],
    )
    engine._lock_example_objects(result)

    locked = [o for o in result.objects if o.object_name == "Sales by Category"]
    assert locked
    assert locked[0].required and locked[0].priority
    assert locked[0].score == KbRequiredObjectScore
    assert any(o.object_name == "Category Sales for 1997" for o in result.objects)


def test_a_stale_example_object_is_not_locked_or_authorized():
    """The catalog decides: an example naming an object the database lacks locks nothing."""
    engine = DiscoveryEngine(Stores())
    result = DiscoveryResult(
        objects=[],
        branch="dual_prong",
        few_shot_examples=[FewShotExample(question="q", sql="SELECT 1 FROM dbo.NoSuchTable")],
    )
    engine._lock_example_objects(result)
    assert result.objects == []


def test_whitelist_drops_an_example_object_the_catalog_lacks(monkeypatch):
    seen = {}

    def fake_validate(self, sql, allowed_objects=None, skip_object_scope=False):
        seen["allowed"] = list(allowed_objects or [])
        return True, "", []

    monkeypatch.setattr("app.services.sql_validator.SqlValidator.validate", fake_validate)
    discovery = DiscoveryResult(
        objects=[ScoredObject(schema_name="dbo", object_name="Sales by Category", score=1.0)],
        branch="dual_prong",
        few_shot_examples=[
            FewShotExample(question="q", sql="SELECT 1 FROM dbo.NoSuchTable"),
            FewShotExample(question="q2", sql=CANDIDATE_SQL),
        ],
    )
    context = AgentContext(
        request=AgentRequest(query="find top 10 selling products", source_id="s1"),
        combined_query="find top 10 selling products",
        dbms_type="SQL Server",
    )
    result = _drive(run_attempt_loop(context, discovery, Stores(), RecordingLlm(CANDIDATE_SQL), lambda *a, **k: None))

    assert result.success
    allowed = [name.lower() for name in seen["allowed"]]
    assert "nosuchtable" not in " ".join(allowed)
    assert any("sales by category" in name for name in allowed)
