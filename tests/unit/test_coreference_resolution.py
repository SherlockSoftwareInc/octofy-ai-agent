"""Coreference resolution: vague follow-ups inherit the session's filter state."""

from app.core.orchestrator.coreference import (
    is_vague_followup,
    merge_filters,
    needs_coreference,
    resolve_coreference,
)
from app.models.pipeline import ActiveFilter, ConversationTurn

CHOCOLATE = ActiveFilter(
    entity="Products",
    attribute="ProductName",
    operator="LIKE",
    value="'%chocolate%'",
    origin_turn=1,
)

HISTORY = [
    ConversationTurn(question="show chocolate sales by product", answer="Here are the results."),
]


class RewriteLlm:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        return self.payload


class BoomLlm:
    def complete_json(self, messages, **kwargs):
        raise RuntimeError("llm down")


def test_vague_followup_detection():
    assert is_vague_followup("I need all order details")
    assert is_vague_followup("more details")
    assert not is_vague_followup(
        "Show total sales by product for chocolate products in 1997 broken down by month"
    )


def test_self_contained_queries_are_not_rewritten():
    assert not needs_coreference("SELECT * FROM dbo.Orders", [CHOCOLATE], True)
    assert not needs_coreference("show total revenue by country", [CHOCOLATE], True)
    result = resolve_coreference("SELECT * FROM dbo.Orders", HISTORY, [CHOCOLATE])
    assert result.was_rewritten is False
    assert result.rewritten_query == "SELECT * FROM dbo.Orders"


def test_no_context_means_no_rewrite():
    result = resolve_coreference("I need all order details", [], [])
    assert result.was_rewritten is False
    assert result.rewritten_query == "I need all order details"


def test_deterministic_rewrite_carries_active_filter_without_llm():
    result = resolve_coreference("I need all order details", HISTORY, [CHOCOLATE])
    assert result.was_rewritten is True
    assert result.source == "deterministic"
    assert result.rewritten_query.startswith("I need all order details for chocolate")
    assert "chocolate" in result.rewritten_query


def test_llm_rewrite_is_used_and_carried_filters_are_parsed():
    llm = RewriteLlm(
        {
            "rewritten_query": "I need all order details for chocolate products",
            "carried_filters": [
                {"entity": "Products", "attribute": "ProductName", "operator": "LIKE", "value": "'%chocolate%'"}
            ],
            "changed": True,
        }
    )
    result = resolve_coreference("I need all order details", HISTORY, [CHOCOLATE], llm=llm)
    assert result.source == "llm"
    assert result.rewritten_query == "I need all order details for chocolate products"
    assert len(result.carried_filters) == 1
    assert result.carried_filters[0].attribute == "ProductName"
    assert result.carried_filters[0].source == "llm"
    assert llm.calls and "ACTIVE FILTERS" in llm.calls[0][1]["content"]


def test_invalid_llm_rewrite_falls_back_to_deterministic():
    for payload in (
        {"rewritten_query": "", "changed": True},
        {"rewritten_query": "I need all order details", "changed": True},
        {"rewritten_query": "x", "changed": True},
        {"rewritten_query": "y" * 900, "changed": True},
        "not-a-dict",
    ):
        result = resolve_coreference("I need all order details", HISTORY, [CHOCOLATE], llm=RewriteLlm(payload))
        assert result.source == "deterministic"
        assert "chocolate" in result.rewritten_query


def test_llm_exception_falls_back_to_deterministic():
    result = resolve_coreference("I need all order details", HISTORY, [CHOCOLATE], llm=BoomLlm())
    assert result.source == "deterministic"
    assert "chocolate" in result.rewritten_query


def test_date_and_numeric_filters_are_not_folded_into_sentences():
    date_filter = ActiveFilter(attribute="OrderDate", operator=">=", value="'1997-01-01'", entity="Orders")
    result = resolve_coreference("I need all order details", HISTORY, [CHOCOLATE, date_filter])
    assert "chocolate" in result.rewritten_query
    assert "1997-01-01" not in result.rewritten_query
    # The filter itself is still part of the session state.
    assert any(f.attribute == "OrderDate" for f in result.active_filters)


def test_restated_filter_is_not_appended_twice():
    coffee = ActiveFilter(
        entity="Products", attribute="ProductName", operator="LIKE", value="'%coffee%'", origin_turn=2
    )
    result = resolve_coreference("now do this for coffee", HISTORY, [coffee])
    assert result.rewritten_query.lower().count("coffee") == 1
    assert "chocolate" not in result.rewritten_query


def test_merge_filters_later_wins_on_same_attribute():
    updated = ActiveFilter(entity="Products", attribute="ProductName", operator="LIKE", value="'%coffee%'")
    merged = merge_filters([CHOCOLATE], [updated])
    assert len(merged) == 1
    assert merged[0].value == "'%coffee%'"
