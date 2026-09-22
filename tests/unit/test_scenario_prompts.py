"""Prompt split: strict optimization rules vs. authorized refinement scope expansion."""

from app.core.branch_taxonomy import GenerationMode
from app.core.orchestrator.preprocessing import preprocess
from app.core.orchestrator.prompts import (
    OPTIMIZATION_INSTRUCTIONS,
    REFINEMENT_INSTRUCTIONS,
    SCOPE_GUARD,
    build_optimization_system_prompt,
    build_system_prompt,
    build_user_prompt,
    scenario_rules,
)
from app.models.pipeline import ActiveFilter, AgentRequest, DiscoveryResult

EXISTING_SQL = (
    "SELECT p.ProductName, SUM(od.Quantity) AS Qty "
    "FROM dbo.Products p JOIN dbo.[Order Details] od ON p.ProductID = od.ProductID "
    "GROUP BY p.ProductName"
)

CHOCOLATE = ActiveFilter(
    entity="Products", attribute="ProductName", operator="LIKE", value="'%chocolate%'", origin_turn=1
)


def _context(query: str, existing_code=None):
    return preprocess(AgentRequest(query=query, existing_code=existing_code))


def _discovery():
    return DiscoveryResult(
        branch="dual_prong",
        selected_object_context="## dbo.Products\n| ProductID | ProductName |",
        schema_context="## dbo.Products\n| ProductID | ProductName |",
    )


def test_optimization_prompt_forbids_schema_and_scope_changes():
    context = _context("make it faster", EXISTING_SQL)
    context.generation_mode = GenerationMode.OPTIMIZATION
    prompt = build_optimization_system_prompt(context, EXISTING_SQL)
    assert OPTIMIZATION_INSTRUCTIONS in prompt
    assert "Do NOT consult any catalog" in prompt
    assert "Do NOT invent, add, or remove tables or columns" in prompt
    assert "AVAILABLE SCHEMAS" not in prompt
    assert "REFINEMENT INSTRUCTIONS" not in prompt
    assert EXISTING_SQL in prompt


def test_full_prompt_for_optimization_carries_the_same_strict_rules():
    context = _context("convert this to a CTE", EXISTING_SQL)
    context.generation_mode = GenerationMode.OPTIMIZATION
    prompt = build_system_prompt(context, _discovery())
    assert "GENERATION MODE\noptimization" in prompt
    assert OPTIMIZATION_INSTRUCTIONS in prompt
    assert REFINEMENT_INSTRUCTIONS not in prompt


def test_refinement_prompt_authorizes_scope_expansion_and_preserves_filters():
    context = _context("I need all order details", EXISTING_SQL)
    context.generation_mode = GenerationMode.REFINEMENT
    context.active_filters = [CHOCOLATE]
    context.filter_state_text = "- ProductName LIKE '%chocolate%'"
    prompt = build_system_prompt(context, _discovery())
    assert REFINEMENT_INSTRUCTIONS in prompt
    assert "you are authorized to query base tables and establish appropriate foreign key joins" in prompt
    assert "Filter Preservation" in prompt
    assert SCOPE_GUARD in prompt
    assert "Preserve all active filters from preceding turns" in prompt
    assert "ProductName LIKE '%chocolate%'" in prompt
    assert OPTIMIZATION_INSTRUCTIONS not in prompt
    # The editor SQL's own objects stay in the schema context (base context anchor).
    assert "dbo.Products" in prompt


def test_scope_guard_only_appears_when_filters_exist():
    context = _context("add shipping date", EXISTING_SQL)
    context.generation_mode = GenerationMode.REFINEMENT
    prompt = build_system_prompt(context, _discovery())
    assert SCOPE_GUARD not in prompt


def test_fresh_start_prompt_has_no_scenario_rules():
    context = _context("show total sales by country")
    context.generation_mode = GenerationMode.FRESH_START
    prompt = build_system_prompt(context, _discovery())
    assert OPTIMIZATION_INSTRUCTIONS not in prompt
    assert REFINEMENT_INSTRUCTIONS not in prompt
    assert "GENERATION MODE\nfresh_start" in prompt


def test_scenario_rules_helper():
    context = _context("make it faster", EXISTING_SQL)
    context.generation_mode = GenerationMode.OPTIMIZATION
    assert scenario_rules(context) == OPTIMIZATION_INSTRUCTIONS
    context.generation_mode = GenerationMode.DRILL_DOWN
    assert scenario_rules(context) == REFINEMENT_INSTRUCTIONS
    context.generation_mode = GenerationMode.FRESH_START
    assert scenario_rules(context) == ""


def test_user_prompt_carries_the_combined_conversation():
    context = _context("I need all order details", EXISTING_SQL)
    context.rewritten_query = "I need all order details for chocolate Products"
    context.combined_query = "I need all order details for chocolate Products\nQ: previous | A: previous answer"
    prompt = build_user_prompt(context)
    assert "for chocolate Products" in prompt
    assert "Existing SQL" in prompt
