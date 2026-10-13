"""Session-level semantic context: filter extraction, lifecycle and inheritance."""

import pytest

from app.core.orchestrator.session_context import (
    SessionContextStore,
    apply_conversation_context,
    apply_filter_lifecycle,
    extract_filters_from_sql,
    extract_grain_from_sql,
    prepare_conversation_context,
    record_generation_outcome,
)
from app.core.orchestrator.preprocessing import preprocess
from app.core.orchestrator.prompts import grain_prompt_line
from app.models.pipeline import AgentRequest, SessionSemanticContext

SUMMARY_SQL = (
    "SELECT p.ProductName, SUM(od.Quantity) AS Qty "
    "FROM dbo.Orders o "
    "JOIN dbo.[Order Details] od ON o.OrderID = od.OrderID "
    "JOIN dbo.Products p ON od.ProductID = p.ProductID "
    "WHERE p.ProductName LIKE '%chocolate%' AND o.OrderDate >= '1997-01-01' "
    "GROUP BY p.ProductName"
)


def test_extracts_literal_predicates_only():
    filters = extract_filters_from_sql(SUMMARY_SQL)
    rendered = {f.render() for f in filters}
    assert "ProductName LIKE '%chocolate%'" in rendered
    assert "OrderDate >= '1997-01-01'" in rendered
    # Join conditions (identifier = identifier) must never become filters.
    assert not any("OrderID" in f.attribute for f in filters)


def test_extracts_entity_from_alias():
    by_attribute = {f.attribute: f for f in extract_filters_from_sql(SUMMARY_SQL)}
    assert by_attribute["ProductName"].entity == "Products"
    assert by_attribute["OrderDate"].entity == "Orders"


def test_filter_value_is_preserved_verbatim():
    filters = {f.attribute: f for f in extract_filters_from_sql(SUMMARY_SQL)}
    assert filters["ProductName"].value == "'%chocolate%'"
    assert filters["ProductName"].operator == "LIKE"
    assert filters["ProductName"].phrase() == "chocolate Products"


def test_empty_sql_has_no_filters():
    assert extract_filters_from_sql("") == []
    assert extract_filters_from_sql(None) == []


def test_inheritance_replacement_and_clearing():
    filters = extract_filters_from_sql(SUMMARY_SQL, turn_index=1)

    inherited, cleared, replaced, _ = apply_filter_lifecycle(filters, "add the region", 2)
    assert cleared is False and replaced is False
    assert {f.render() for f in inherited} == {f.render() for f in filters}

    replaced_filters, cleared, replaced, notes = apply_filter_lifecycle(filters, "now do this for coffee", 3)
    assert replaced is True and cleared is False
    assert "ProductName LIKE '%coffee%'" in {f.render() for f in replaced_filters}
    assert "OrderDate >= '1997-01-01'" in {f.render() for f in replaced_filters}
    assert notes

    cleared_filters, cleared, replaced, notes = apply_filter_lifecycle(filters, "for all products", 4)
    assert cleared is True and cleared_filters == []
    assert notes


def test_session_context_inherits_across_turns():
    store = SessionContextStore()
    first = AgentRequest(query="show chocolate sales by product", existing_code=SUMMARY_SQL, session_id="chat-1")
    result = prepare_conversation_context(first, store=store)
    assert {f.render() for f in result.active_filters} == {
        "ProductName LIKE '%chocolate%'",
        "OrderDate >= '1997-01-01'",
    }
    stored = store.get("session:chat-1")
    assert stored is not None and stored.turn_index == 1

    second = AgentRequest(query="I need all order details", existing_code=SUMMARY_SQL, session_id="chat-1")
    carried = prepare_conversation_context(second, store=store)
    assert carried.rewritten_query == "I need all order details for chocolate Products"
    assert store.get("session:chat-1").turn_index == 2


def test_replacement_then_clear_across_turns():
    store = SessionContextStore()
    prepare_conversation_context(
        AgentRequest(query="show chocolate sales", existing_code=SUMMARY_SQL, session_id="chat-2"), store=store
    )
    replaced = prepare_conversation_context(
        AgentRequest(query="now do this for coffee", existing_code=SUMMARY_SQL, session_id="chat-2"), store=store
    )
    assert "ProductName LIKE '%coffee%'" in {f.render() for f in replaced.active_filters}
    assert replaced.replacement_applied is True

    cleared = prepare_conversation_context(
        AgentRequest(query="for all products", existing_code=SUMMARY_SQL, session_id="chat-2"), store=store
    )
    assert cleared.active_filters == []
    assert cleared.filters_cleared is True
    assert store.get("session:chat-2").active_filters == []


def test_without_session_id_filters_still_come_from_editor_sql():
    result = prepare_conversation_context(AgentRequest(query="I need all order details", existing_code=SUMMARY_SQL))
    assert result.session_id is None
    assert "ProductName LIKE '%chocolate%'" in {f.render() for f in result.active_filters}
    assert "chocolate" in result.rewritten_query


def test_record_generation_outcome_feeds_the_next_turn():
    store = SessionContextStore()
    request = AgentRequest(query="show sales", existing_code=None, session_id="chat-3")
    context = preprocess(request)
    context.session_id = "session:chat-3"
    record_generation_outcome(
        context,
        "SELECT * FROM dbo.Products WHERE ProductName LIKE '%chocolate%'",
        store=store,
    )
    stored = store.get("session:chat-3")
    assert stored is not None
    assert "ProductName LIKE '%chocolate%'" in {f.render() for f in stored.active_filters}

    follow_up = prepare_conversation_context(
        AgentRequest(query="I need all order details", session_id="chat-3"), store=store
    )
    assert "chocolate" in follow_up.rewritten_query


def test_grain_is_read_out_of_the_generated_sql():
    assert extract_grain_from_sql(SUMMARY_SQL) == "p.ProductName"
    # A statement without GROUP BY is at its natural row-level grain, which is not carried.
    assert extract_grain_from_sql("SELECT * FROM dbo.Products") == ""
    assert extract_grain_from_sql(None) == ""
    # The outer grouping is the statement's grain, not the subquery's.
    assert (
        extract_grain_from_sql(
            "SELECT s.x, COUNT(*) FROM (SELECT x FROM t GROUP BY x) s GROUP BY s.x ORDER BY s.x"
        )
        == "s.x"
    )
    # HAVING and ORDER BY are not part of the grain.
    assert extract_grain_from_sql("SELECT a, b FROM t GROUP BY a, b HAVING COUNT(*) > 1") == "a, b"
    # A pathological grouping is dropped rather than quoted into the prompt.
    assert extract_grain_from_sql("SELECT 1 FROM t GROUP BY " + ", ".join(f"c{i}" for i in range(200))) == ""


def test_record_generation_outcome_carries_the_grain_to_the_next_turn():
    store = SessionContextStore()
    context = preprocess(AgentRequest(query="show sales", session_id="chat-9"))
    context.session_id = "session:chat-9"
    record_generation_outcome(context, SUMMARY_SQL, store=store)
    assert store.get("session:chat-9").target_grain == "p.ProductName"

    follow_up_request = AgentRequest(query="keep the same breakdown", session_id="chat-9")
    follow_up = prepare_conversation_context(follow_up_request, store=store)
    assert follow_up.target_grain == "p.ProductName"

    next_context = preprocess(follow_up_request)
    apply_conversation_context(next_context, follow_up)
    assert grain_prompt_line(next_context) == "Current target grain: p.ProductName"


def test_full_reset_drops_the_carried_grain():
    store = SessionContextStore()
    context = preprocess(AgentRequest(query="show sales", session_id="chat-10"))
    context.session_id = "session:chat-10"
    record_generation_outcome(context, SUMMARY_SQL, store=store)
    assert store.get("session:chat-10").target_grain == "p.ProductName"

    reset = prepare_conversation_context(
        AgentRequest(query="start over", session_id="chat-10"), store=store
    )
    assert reset.filters_cleared is True
    assert reset.target_grain is None
    assert store.get("session:chat-10").target_grain is None


def test_a_bare_filter_clear_keeps_the_carried_grain():
    store = SessionContextStore()
    context = preprocess(AgentRequest(query="show sales", session_id="chat-11"))
    context.session_id = "session:chat-11"
    record_generation_outcome(context, SUMMARY_SQL, store=store)

    cleared = prepare_conversation_context(
        AgentRequest(query="for all products", session_id="chat-11"), store=store
    )
    assert cleared.filters_cleared is True
    assert cleared.target_grain == "p.ProductName"


def test_store_is_bounded():
    store = SessionContextStore(max_entries=2)
    for i in range(5):
        store.put(SessionSemanticContext(session_id=f"s{i}", turn_index=i))
    assert store.get("s0") is None
    assert store.get("s4") is not None
    store.clear()
    assert store.get("s4") is None


@pytest.mark.parametrize("query", ["start over", "new query"])
def test_full_reset_clears_session_state(query):
    store = SessionContextStore()
    prepare_conversation_context(
        AgentRequest(query="show chocolate sales", existing_code=SUMMARY_SQL, session_id="chat-4"), store=store
    )
    reset = prepare_conversation_context(
        AgentRequest(query=query, existing_code=SUMMARY_SQL, session_id="chat-4"), store=store
    )
    assert reset.filters_cleared is True
    assert reset.active_filters == []
    assert reset.was_rewritten is False
