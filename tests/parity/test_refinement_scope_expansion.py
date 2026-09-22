"""Parity contract: optimization stays inside the editor SQL; refinement expands scope.

Plan success criteria under test:

* syntax/performance tuning touches only the editor SQL without any schema fetch;
* a drill-down/refinement turn preserves the inherited filters while adding the base tables
  (and any newly discovered objects) needed for the deeper grain.
"""

from app.core.orchestrator.builtin_sql_generator import generate_sql_builtin
from app.core.orchestrator.prompts import OPTIMIZATION_INSTRUCTIONS, REFINEMENT_INSTRUCTIONS, SCOPE_GUARD
from app.core.orchestrator.discovery_engine import DiscoveryEngine
from app.models.pipeline import DiscoveryResult, ScoredObject, TokenUsage
from app.models.schemas import GenerateSQLRequest
from app.services.stores.bundle import build_source_stores
from app.services.stores.sqlite_vec_provider import SqliteVecProvider

SUMMARY_SQL = (
    "SELECT p.ProductName, SUM(od.Quantity) AS Qty "
    "FROM dbo.Products p JOIN dbo.[Order Details] od ON p.ProductID = od.ProductID "
    "WHERE p.ProductName LIKE '%chocolate%' GROUP BY p.ProductName"
)


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


def _statuses(events):
    return [e.get("message") or (e.get("payload") or {}).get("message", "") for e in events if e.get("type") == "status"]


def _payload(events):
    return [e for e in events if e.get("type") == "result"][0]["payload"]


def test_optimization_turn_never_fetches_schema(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "opt.sqlite")
    stores = build_source_stores("s1", provider=provider)

    def _boom(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("discovery must not run for an optimization turn")

    monkeypatch.setattr(DiscoveryEngine, "discover", _boom)
    llm = RecordingLlm()
    request = GenerateSQLRequest(query="make it faster", existing_code=SUMMARY_SQL)

    events = list(generate_sql_builtin(request, stores, llm=llm))

    statuses = _statuses(events)
    assert any("No-discovery provided-code path" in message for message in statuses)
    assert not any("Discovering relevant objects" in message for message in statuses)
    assert not any("Refinement scope expansion" in message for message in statuses)

    systems = llm.system_prompts()
    assert systems, "the optimizer must call the model with the strict optimization prompt"
    assert any(OPTIMIZATION_INSTRUCTIONS in system for system in systems)
    assert all("AVAILABLE SCHEMAS" not in system for system in systems)
    assert all(REFINEMENT_INSTRUCTIONS not in system for system in systems)
    assert SUMMARY_SQL in systems[0]

    assert _payload(events)["discovery_branch"] == "no_discovery"


def test_refinement_turn_runs_discovery_with_base_and_new_objects(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "refine.sqlite")
    stores = build_source_stores("s1", provider=provider)
    discovered = ScoredObject(
        schema_name="dbo",
        object_name="Order Details",
        score=0.9,
        matched_columns=["OrderID", "ProductID"],
    )
    monkeypatch.setattr(
        DiscoveryEngine,
        "discover",
        lambda self, query, analysis, **kwargs: DiscoveryResult(
            objects=[discovered.model_copy(deep=True)], branch="dual_prong"
        ),
    )
    llm = RecordingLlm()
    request = GenerateSQLRequest(
        query="I need all order details",
        existing_code=SUMMARY_SQL,
        session_id="parity-refinement-1",
    )

    events = list(generate_sql_builtin(request, stores, llm=llm))

    statuses = _statuses(events)
    assert any("Resolved follow-up context" in message and "chocolate" in message for message in statuses)
    assert any("Discovering relevant objects" in message for message in statuses)
    assert not any("No-discovery provided-code path" in message for message in statuses)
    assert any("Refinement scope expansion" in message and "Products" in message for message in statuses)

    systems = llm.system_prompts()
    refinement_prompt = next((s for s in systems if REFINEMENT_INSTRUCTIONS in s), None)
    assert refinement_prompt is not None, "refinement turns must use the refinement prompt"
    # Base context from the editor SQL is preserved ...
    assert "Products" in refinement_prompt
    # ... the newly discovered grain-level object is added ...
    assert "Order Details" in refinement_prompt
    # ... and the inherited filter survives into the prompt.
    assert "chocolate" in refinement_prompt
    assert SCOPE_GUARD in refinement_prompt
    assert OPTIMIZATION_INSTRUCTIONS not in refinement_prompt

    assert _payload(events)["discovery_branch"].startswith("refinement/")


def test_refinement_bypasses_stored_exact_answer_when_filters_are_active(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "exact.sqlite")
    stores = build_source_stores("s1", provider=provider)
    stores.fewshots.upsert("I need all order details", "SELECT * FROM dbo.[Order Details]")
    monkeypatch.setattr(
        DiscoveryEngine,
        "discover",
        lambda self, query, analysis, **kwargs: DiscoveryResult(
            objects=[ScoredObject(schema_name="dbo", object_name="Order Details", score=0.9)],
            branch="dual_prong",
        ),
    )

    request = GenerateSQLRequest(query="I need all order details", existing_code=SUMMARY_SQL)
    events = list(generate_sql_builtin(request, stores, llm=RecordingLlm()))

    statuses = _statuses(events)
    assert any("Discovering relevant objects" in message for message in statuses)
    assert _payload(events)["discovery_branch"] != "kb_exact"
