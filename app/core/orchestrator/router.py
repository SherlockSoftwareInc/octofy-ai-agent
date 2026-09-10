"""Deterministic fast paths + LLM intent classification."""

from __future__ import annotations

from typing import Optional

from app.core.branch_taxonomy import DiscoveryBranch, GenerationMode, RouteKind
from app.core.constants import (
    LikelyDbQueryMaxWords,
    SimplePreAnalysisMaxCollapsedChars,
    SimplePreAnalysisMaxWords,
)
from app.core.errors import ErrorCategory, build_detailed_failure_result, build_failure_report
from app.models.pipeline import AgentContext, BuiltInGenerateResult, RouteDecision
from app.utils.regexes import (
    CLAUSE_PAIR,
    SQL_STATEMENT_START,
    collapse_whitespace,
    complexity_tier,
    extract_inline_sql,
    word_count,
)


def has_strong_language_agnostic_db_signal(text: str) -> bool:
    if not text:
        return False
    if SQL_STATEMENT_START.search(text):
        return True
    if extract_inline_sql(text):
        return True
    if CLAUSE_PAIR.search(text):
        return True
    return False


def should_use_simple_preanalysis_fast_path(context: AgentContext) -> bool:
    req = context.request
    if req.existing_code or req.error_message:
        return False
    collapsed = collapse_whitespace(req.query)
    if len(collapsed) > SimplePreAnalysisMaxCollapsedChars:
        return False
    if word_count(collapsed) > SimplePreAnalysisMaxWords:
        return False
    if complexity_tier(collapsed) != "simple":
        return False
    lowered = f" {collapsed.lower()} "
    for kw in (" join ", " group by ", " having ", " union ", " except ", " intersect ", " compare ", " versus ", " vs "):
        if kw in lowered:
            return False
    return has_strong_language_agnostic_db_signal(collapsed)


def _conversational(context: AgentContext, branch: str, message: str) -> RouteDecision:
    result = BuiltInGenerateResult(
        success=True,
        sql="",
        message=message,
        explanation=message,
        query_type="general",
        discovery_branch=branch,
        attempts=0,
        source_id=context.request.source_id,
        error_category=branch,
    )
    return RouteDecision(route=RouteKind.CONVERSATIONAL, context=context, immediate_result=result, skip_discovery=True)


def route(context: AgentContext, llm=None) -> RouteDecision:
    req = context.request
    if req.force_general:
        return _conversational(context, DiscoveryBranch.OFF_TOPIC, "General response requested.")

    if req.error_message and req.existing_code:
        context.generation_mode = GenerationMode.DEBUGGING
        context.is_error_recovery = True
        context.intent = "db_query"
        return RouteDecision(route=RouteKind.CODE_FIXING, context=context)

    if req.database_objects:
        if req.existing_code and not req.error_message:
            context.generation_mode = GenerationMode.OPTIMIZATION
            return RouteDecision(route=RouteKind.OPTIMIZE, context=context, skip_discovery=False)
        return RouteDecision(route=RouteKind.GENERATE, context=context)

    if should_use_simple_preanalysis_fast_path(context):
        context.intent = "db_query"
        return RouteDecision(route=RouteKind.GENERATE, context=context, skip_preanalysis=True)

    if word_count(req.query) <= LikelyDbQueryMaxWords and has_strong_language_agnostic_db_signal(req.query):
        context.intent = "db_query"
        return RouteDecision(route=RouteKind.GENERATE, context=context)

    inline = extract_inline_sql(req.query)
    if req.existing_code and not req.error_message:
        context.generation_mode = GenerationMode.OPTIMIZATION
        return RouteDecision(route=RouteKind.OPTIMIZE, context=context, skip_discovery=True)

    if inline and not req.existing_code:
        return RouteDecision(route=RouteKind.GENERATE, context=context, skip_discovery=True)

    intent = classify_intent(req.query, llm)
    context.intent = intent
    if intent in {"app_feature", "off_topic"}:
        branch = DiscoveryBranch.APP_FEATURE if intent == "app_feature" else DiscoveryBranch.OFF_TOPIC
        return _conversational(context, branch, f"This request was classified as {intent}.")
    if intent == "optimize_code" and req.existing_code:
        context.generation_mode = GenerationMode.OPTIMIZATION
        return RouteDecision(route=RouteKind.OPTIMIZE, context=context, skip_discovery=True)
    return RouteDecision(route=RouteKind.GENERATE, context=context)


def classify_intent(query: str, llm=None) -> str:
    if llm is None:
        if has_strong_language_agnostic_db_signal(query):
            return "db_query"
        return "db_query"
    prompt = (
        "Classify the user request as one of: db_query, optimize_code, app_feature, off_topic. "
        "Reply with only the label.\n"
        f"USER: {query}"
    )
    try:
        text = llm.complete(
            [{"role": "system", "content": "You are an intent classifier."}, {"role": "user", "content": prompt}],
            max_tokens=16,
        )
        label = (text or "").strip().lower().replace(" ", "_")
        for candidate in ("db_query", "optimize_code", "app_feature", "off_topic"):
            if candidate in label:
                return candidate
    except Exception:
        pass
    return "db_query"
