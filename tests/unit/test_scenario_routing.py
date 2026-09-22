"""Scenario routing matrix: true optimization vs. refinement / drill-down.

Regression contract from the enhancement plan:

* an optimization turn touches only the editor SQL (no discovery, no schema fetch);
* a refinement/drill-down turn keeps discovery enabled so filters are preserved and the
  tables/joins for the requested grain can be discovered;
* an explicit reset drops the editor SQL context.
"""

import pytest

from app.core.branch_taxonomy import GenerationMode, RouteKind, is_refinement_scenario
from app.core.orchestrator.preprocessing import preprocess
from app.core.orchestrator.router import INTENT_LABELS, classify_intent, route
from app.core.orchestrator.scenario import classify_scenario, detect_filter_clear, detect_reset
from app.models.pipeline import AgentRequest, TokenUsage

EXISTING_SQL = (
    "SELECT p.ProductName, SUM(od.Quantity) AS Qty "
    "FROM dbo.Products p JOIN dbo.[Order Details] od ON p.ProductID = od.ProductID "
    "WHERE p.ProductName LIKE '%chocolate%' GROUP BY p.ProductName"
)

OPTIMIZATION_REQUESTS = [
    "make it faster",
    "format this",
    "add an index",
    "add indexing",
    "tune performance",
    "convert this to a CTE",
    "remove unused joins",
    "clean up the formatting",
    "add a comment",
    "parameterize the query",
]

REFINEMENT_REQUESTS = [
    "I need all order details",
    "add shipping date",
    "include the customer name",
    "also show the region",
    "now do this for coffee",
    "show me coffee instead",
    "change it to tea",
    "for all products",
    "clear filters",
]

DRILL_DOWN_REQUESTS = [
    "break this down by customer",
    "drill down into orders",
    "per employee",
    "group by country",
]


class LabelLlm:
    """Minimal LLM stub returning a fixed label for every completion."""

    token_usage = TokenUsage()

    def __init__(self, label: str = ""):
        self.label = label
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return self.label

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        return {}


def _context(query: str, existing_code=None):
    return preprocess(AgentRequest(query=query, existing_code=existing_code))


@pytest.mark.parametrize("query", OPTIMIZATION_REQUESTS)
def test_optimization_requests_keep_editor_sql_only(query):
    context = _context(query, EXISTING_SQL)
    decision = route(context)
    assert context.generation_mode == GenerationMode.OPTIMIZATION
    assert decision.route == RouteKind.OPTIMIZE
    assert decision.skip_discovery is True
    assert not is_refinement_scenario(context.generation_mode)


@pytest.mark.parametrize("query", REFINEMENT_REQUESTS)
def test_refinement_requests_enable_discovery_and_keep_context(query):
    context = _context(query, EXISTING_SQL)
    decision = route(context)
    assert context.generation_mode in {GenerationMode.REFINEMENT, GenerationMode.DRILL_DOWN}
    assert decision.route == RouteKind.REFINE
    assert decision.skip_discovery is False


@pytest.mark.parametrize("query", DRILL_DOWN_REQUESTS)
def test_drill_down_requests_enable_discovery(query):
    context = _context(query, EXISTING_SQL)
    decision = route(context)
    assert context.generation_mode == GenerationMode.DRILL_DOWN
    assert decision.route == RouteKind.REFINE
    assert decision.skip_discovery is False


def test_explicit_reset_drops_editor_sql_context():
    context = _context("start over with a new query", EXISTING_SQL)
    decision = route(context)
    assert context.generation_mode == GenerationMode.FRESH_START
    assert decision.route == RouteKind.GENERATE
    assert decision.skip_discovery is False


def test_no_existing_code_is_always_fresh_start():
    for query in ("make it faster", "I need all order details", "break this down by customer"):
        context = _context(query)
        route(context)
        assert context.generation_mode == GenerationMode.FRESH_START


def test_filter_negation_is_not_a_full_reset():
    assert detect_reset("for all products") is False
    assert detect_filter_clear("for all products") is True
    assert detect_reset("start over") is True
    context = _context("for all products", EXISTING_SQL)
    decision = route(context)
    assert context.generation_mode == GenerationMode.REFINEMENT
    assert decision.skip_discovery is False


def test_classifier_falls_back_to_llm_scenario_when_ambiguous():
    llm = LabelLlm("refinement")
    context = _context("give me the same again", EXISTING_SQL)
    decision = route(context, llm)
    assert context.generation_mode == GenerationMode.REFINEMENT
    assert decision.route == RouteKind.REFINE
    assert decision.skip_discovery is False

    llm = LabelLlm("optimization")
    context = _context("give me the same again", EXISTING_SQL)
    decision = route(context, llm)
    assert context.generation_mode == GenerationMode.OPTIMIZATION
    assert decision.route == RouteKind.OPTIMIZE
    assert decision.skip_discovery is True


def test_intent_labels_include_refine_query():
    assert INTENT_LABELS == ("db_query", "optimize_code", "refine_query", "app_feature", "off_topic")
    assert classify_intent("break this down by customer", LabelLlm("refine_query")) == "refine_query"
    assert classify_intent("make it faster", LabelLlm("optimize_code")) == "optimize_code"
    assert classify_intent("hello there", None) == "db_query"


def test_refine_query_label_routes_to_refinement_with_existing_code():
    # The deterministic classifier is intentionally bypassed here by asking the scenario
    # classifier for an ambiguous turn, then confirming the intent label is honored.
    llm = LabelLlm("refinement")
    context = _context("what about that", EXISTING_SQL)
    decision = route(context, llm)
    assert decision.route == RouteKind.REFINE


def test_scenario_decision_records_signals():
    decision = classify_scenario("break this down by customer", has_existing_code=True)
    assert decision.scenario == GenerationMode.DRILL_DOWN
    assert decision.source == "deterministic"
    assert decision.signals
    assert decision.is_refinement is True


def test_error_message_scenario_is_debugging():
    context = _context("fix this", EXISTING_SQL)
    context.request.error_message = "Invalid column name 'Foo'"
    decision = route(context)
    assert context.generation_mode == GenerationMode.DEBUGGING
    assert decision.route == RouteKind.CODE_FIXING
