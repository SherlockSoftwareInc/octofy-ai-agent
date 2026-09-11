"""Built-in GenerateAsync port: stages A–F with SSE status events."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Generator, Optional, Union

from app.core.branch_taxonomy import DiscoveryBranch, PipelineStage, RouteKind
from app.core.constants import (
    DefaultPrecomputedQueryDirectMatchThreshold,
    FuzzyMatchMinConfidence,
    MaxGenerationTimeMs,
    NoDiscoveryTimeBudgetMs,
)
from app.core.errors import ErrorCategory, apply_language_result, build_detailed_failure_result, build_failure_report
from app.core.orchestrator.attempts import run_attempt_loop
from app.core.orchestrator.discovery_engine import DiscoveryEngine
from app.core.orchestrator.preprocessing import build_agent_request, preprocess
from app.core.orchestrator.router import route
from app.models.pipeline import BuiltInGenerateResult, DiscoveryResult, ScoredObject
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse
from app.services.llm_client import LlmClient
from app.services.object_name_resolver import ObjectNameResolver
from app.services.sql_context_hydrator import SqlContextHydrator
from app.services.sql_validator import SqlValidator
from app.services.stores.bundle import SourceStores, build_source_stores
from app.services.stores.skills_folder import markdown_lookup_for_objects
from app.utils.python_normalization import (
    extract_python_body,
    extract_sql_from_python,
    materialize_python_code,
    syntax_check_python,
)
from app.utils.r_normalization import (
    extract_r_body,
    extract_sql_from_r,
    materialize_r_code,
    syntax_check_r,
)
from app.utils.sas_normalization import (
    extract_sas_body,
    extract_sql_from_sas,
    materialize_sas_code,
    syntax_check_sas,
)
from app.utils.sse import sse_done, sse_result, sse_status

logger = logging.getLogger(__name__)


def generate_sql_builtin(
    request: GenerateSQLRequest,
    stores: SourceStores,
    llm: Optional[LlmClient] = None,
    *,
    target_language: str = "sql",
) -> Generator[Dict[str, Any], None, None]:
    started = time.time()
    llm = llm or LlmClient()
    source_id = stores.source_id
    python_mode = target_language == "python"
    r_mode = target_language == "r"
    sas_mode = target_language == "sas"
    script_mode = python_mode or r_mode or sas_mode
    step = 0

    def emit(stage: str, message: str, **extra):
        nonlocal step
        step += 1
        logger.info("source_id=%s stage=%s %s", source_id, stage, message)
        return sse_status(stage, message, step_id=step, source_id=source_id, **extra)

    def finalize(result: BuiltInGenerateResult) -> Dict[str, Any]:
        result = apply_language_result(result, target_language)
        return _to_http(result).model_dump(by_alias=True)

    def code_from_match(sql: str) -> str:
        if python_mode:
            return materialize_python_code(sql)
        if r_mode:
            return materialize_r_code(sql)
        if sas_mode:
            return materialize_sas_code(sql)
        return sql

    yield emit(PipelineStage.ROUTING, "Validating and routing request")
    agent_req = build_agent_request(request, source_id)
    context = preprocess(agent_req, stores)
    decision = route(context, llm)
    context = decision.context

    if decision.immediate_result:
        yield sse_result(finalize(decision.immediate_result), decision.immediate_result.message or "")
        yield sse_done()
        return

    # Stage B — pin validation
    pins = list(context.request.database_objects or [])
    if pins:
        yield emit(PipelineStage.VALIDATE_PINS, "Validating pinned objects")
        resolver = ObjectNameResolver(stores.catalog)
        resolved = resolver.resolve_many(pins)
        missing = [r for r in resolved if r.status == "missing"]
        notes = []
        new_pins = []
        for r in resolved:
            if r.status == "fuzzy" and r.qualified:
                notes.append(f"Substituted {r.original} → {r.qualified} (confidence {r.confidence:.2f})")
            if r.qualified:
                new_pins.append(r.qualified)
        context.request.database_objects = new_pins
        context.schema_metadata.resolution_notes.extend(notes)
        if missing:
            candidates = []
            for r in missing:
                for c in r.candidates:
                    candidates.append(
                        ScoredObject(
                            schema_name=c.get("schema_name") or "dbo",
                            object_name=c.get("object_name") or "",
                            score=float(c.get("confidence") or 0),
                        )
                    )
            report = build_failure_report(
                summary="Pinned objects could not be resolved",
                resolution_plan=["Check object names", "Use schema.object format"],
                attempts=[],
                final_guidance="priority_validation_failed",
                candidates=candidates,
            )
            result = build_detailed_failure_result(
                message="Pinned objects could not be resolved",
                error_category=ErrorCategory.PRIORITY_VALIDATION_FAILED,
                discovery_branch=DiscoveryBranch.PRIORITY_VALIDATION_FAILED,
                attempts=0,
                token_usage=llm.token_usage.as_dict(),
                processing_time_ms=int((time.time() - started) * 1000),
                hallucination_count=0,
                agentic_retry_count=0,
                failure_report=report,
                source_id=source_id,
            )
            payload = finalize(result)
            yield sse_result(payload, result.message or "")
            yield sse_done()
            return

    engine = DiscoveryEngine(stores, llm)
    engine.clear_analysis_cache()
    semantic_mode = False if script_mode else stores.semantic.is_enabled(context.request.semantic_mode)

    # No-discovery rewrite/optimize path
    if decision.skip_discovery and decision.route in {RouteKind.OPTIMIZE, RouteKind.GENERATE} and context.request.existing_code:
        yield emit(PipelineStage.PREANALYSIS, "No-discovery provided-code path")
        result = _generate_from_provided_sql(context, stores, llm, emit, started, target_language=target_language)
        yield sse_result(finalize(result), result.message or "")
        yield sse_done()
        return

    # Stage C phase 1 fast paths
    yield emit(PipelineStage.PREANALYSIS, "Running pre-analysis fast paths")
    kb_exact = engine.kb_exact(context.request.query)
    if kb_exact:
        result = BuiltInGenerateResult(
            success=True,
            sql=code_from_match(kb_exact.sql),
            message="KB exact match",
            discovery_branch=DiscoveryBranch.KB_EXACT,
            attempts=0,
            processing_time_ms=int((time.time() - started) * 1000),
            token_usage=llm.token_usage.as_dict(),
            source_id=source_id,
        )
        yield sse_result(finalize(result))
        yield sse_done()
        return

    pre_exact = engine.precomputed_exact(context.request.query)
    if pre_exact:
        sql = pre_exact.sql
        if semantic_mode and pre_exact.smq_query:
            from app.services.semantic_compiler import SemanticCompiler
            from app.models.pipeline import SmqPayload
            import json

            try:
                payload = SmqPayload.model_validate(json.loads(pre_exact.smq_query))
                sql = SemanticCompiler().compile(payload, stores.semantic.get_active_model(), context.dbms_type)
            except Exception:
                sql = pre_exact.sql
        result = BuiltInGenerateResult(
            success=True,
            sql=code_from_match(sql),
            message="Precomputed exact match",
            discovery_branch=DiscoveryBranch.PRECOMPUTED_EXACT,
            attempts=0,
            processing_time_ms=int((time.time() - started) * 1000),
            token_usage=llm.token_usage.as_dict(),
            source_id=source_id,
        )
        yield sse_result(finalize(result))
        yield sse_done()
        return

    # vector kb exact (0.05) after deterministic miss
    kb_top = engine.kb_vector_top1(context.request.query)
    if kb_top and kb_top.score <= Kb_distance_exact():
        result = BuiltInGenerateResult(
            success=True,
            sql=code_from_match(kb_top.sql),
            message="KB vector exact match",
            discovery_branch=DiscoveryBranch.KB_EXACT,
            attempts=0,
            processing_time_ms=int((time.time() - started) * 1000),
            token_usage=llm.token_usage.as_dict(),
            source_id=source_id,
        )
        yield sse_result(finalize(result))
        yield sse_done()
        return

    analysis = engine.analyze_query(
        context.combined_query,
        context.request.existing_code,
        skip=decision.skip_preanalysis,
    )
    groups = engine.resolve_active_data_groups(context.combined_query)

    yield emit(PipelineStage.DISCOVERY, "Discovering relevant objects")
    anchor = context.request.existing_code if context.is_error_recovery or context.request.existing_code else context.combined_query
    discovery = engine.discover(
        anchor,
        analysis,
        pins=context.request.database_objects,
        table_override=context.request.table_override,
        top_k=context.request.top_k,
        existing_sql=context.request.existing_code,
    )
    discovery.active_groups = groups
    discovery.query_analysis = analysis
    hydrator = SqlContextHydrator()
    hydrator.set_value_mappings(discovery.value_mappings)
    markdown_lookup = markdown_lookup_for_objects(source_id, discovery.objects)
    selected, supp, schema, validation = hydrator.build_contexts(
        discovery.objects, markdown_lookup=markdown_lookup
    )
    discovery.selected_object_context = selected
    discovery.supplementary_objects = supp
    discovery.schema_context = schema
    discovery.schema_context_for_validation = validation

    result = run_attempt_loop(
        context,
        discovery,
        stores,
        llm,
        lambda stage, msg, **kw: None,
        time_budget_ms=MaxGenerationTimeMs,
        semantic_mode=semantic_mode,
        started_at=started,
        target_language=target_language,
    )
    # re-emit attempt is inside loop without yield; emit a closing status
    yield emit(PipelineStage.ATTEMPT, f"Completed in {result.attempts} attempt(s)")
    payload = finalize(result)
    yield sse_result(payload, result.message or "")
    yield sse_done()


def generate_python_builtin(
    request: GenerateSQLRequest,
    stores: SourceStores,
    llm: Optional[LlmClient] = None,
) -> Generator[Dict[str, Any], None, None]:
    yield from generate_sql_builtin(request, stores, llm, target_language="python")


def generate_r_builtin(
    request: GenerateSQLRequest,
    stores: SourceStores,
    llm: Optional[LlmClient] = None,
) -> Generator[Dict[str, Any], None, None]:
    yield from generate_sql_builtin(request, stores, llm, target_language="r")


def generate_sas_builtin(
    request: GenerateSQLRequest,
    stores: SourceStores,
    llm: Optional[LlmClient] = None,
) -> Generator[Dict[str, Any], None, None]:
    yield from generate_sql_builtin(request, stores, llm, target_language="sas")


def Kb_distance_exact() -> float:
    from app.core.constants import KbExactMatchThreshold

    return KbExactMatchThreshold


def _generate_from_provided_sql(context, stores, llm, emit, started, target_language: str = "sql") -> BuiltInGenerateResult:
    python_mode = target_language == "python"
    r_mode = target_language == "r"
    sas_mode = target_language == "sas"
    existing = context.request.existing_code or ""
    validator = SqlValidator(context.request.source_id, context.dbms_type)
    deadline = started + (NoDiscoveryTimeBudgetMs / 1000.0)

    def _validate(code: str):
        if python_mode:
            ok, err = syntax_check_python(code)
            if not ok:
                return False, err
            sqls = extract_sql_from_python(code)
            if not sqls:
                return True, ""
            for sql in sqls:
                db_ok, db_err, _ = validator.validate(sql)
                if not db_ok:
                    return False, db_err
            return True, ""
        if r_mode:
            ok, err = syntax_check_r(code)
            if not ok:
                return False, err
            sqls = extract_sql_from_r(code)
            if not sqls:
                return True, ""
            for sql in sqls:
                db_ok, db_err, _ = validator.validate(sql)
                if not db_ok:
                    return False, db_err
            return True, ""
        if sas_mode:
            ok, err = syntax_check_sas(code)
            if not ok:
                return False, err
            sqls = extract_sql_from_sas(code)
            if not sqls:
                return True, ""
            for sql in sqls:
                db_ok, db_err, _ = validator.validate(sql)
                if not db_ok:
                    return False, db_err
            return True, ""
        return validator.validate(code)[:2]

    if python_mode:
        code = materialize_python_code(existing)
    elif r_mode:
        code = materialize_r_code(existing)
    elif sas_mode:
        code = materialize_sas_code(existing)
    else:
        code = existing
    ok, err = _validate(code)
    if ok:
        return BuiltInGenerateResult(
            success=True,
            sql=code,
            discovery_branch=DiscoveryBranch.NO_DISCOVERY,
            attempts=1,
            processing_time_ms=int((time.time() - started) * 1000),
            token_usage=llm.token_usage.as_dict(),
            source_id=context.request.source_id,
        )
    # one rewrite attempt with remaining budget
    if time.time() > deadline:
        report = build_failure_report(summary=err, resolution_plan=[], attempts=[], final_guidance="timeout")
        return build_detailed_failure_result(
            message=err or "timeout",
            error_category=ErrorCategory.TIMEOUT,
            discovery_branch=DiscoveryBranch.NO_DISCOVERY,
            attempts=1,
            token_usage=llm.token_usage.as_dict(),
            processing_time_ms=int((time.time() - started) * 1000),
            hallucination_count=0,
            agentic_retry_count=0,
            failure_report=report,
            source_id=context.request.source_id,
        )
    if python_mode:
        prompt = (
            f"Fix this Python pandas/sqlalchemy script for dialect {context.dbms_type}. "
            f"Error: {err}\nUser request: {context.combined_query}\nCode:\n{code}"
        )
    elif r_mode:
        prompt = (
            f"Fix this R tidyverse/DBI script for dialect {context.dbms_type}. "
            f"Error: {err}\nUser request: {context.combined_query}\nCode:\n{code}"
        )
    elif sas_mode:
        prompt = (
            f"Fix this SAS PROC SQL script for dialect {context.dbms_type}. "
            f"Error: {err}\nUser request: {context.combined_query}\nCode:\n{code}"
        )
    else:
        prompt = f"Fix this SQL for dialect {context.dbms_type}. Error: {err}\nSQL:\n{code}"
    try:
        raw = llm.complete([{"role": "user", "content": prompt}])
        from app.utils.sql_normalization import extract_sql_body

        if python_mode:
            fixed = extract_python_body(raw) or code
        elif r_mode:
            fixed = extract_r_body(raw) or code
        elif sas_mode:
            fixed = extract_sas_body(raw) or code
        else:
            fixed = extract_sql_body(raw) or code
        ok, err = _validate(fixed)
        if ok:
            code = fixed
    except Exception:
        pass
    if ok:
        return BuiltInGenerateResult(
            success=True,
            sql=code,
            discovery_branch=DiscoveryBranch.NO_DISCOVERY,
            attempts=2,
            processing_time_ms=int((time.time() - started) * 1000),
            token_usage=llm.token_usage.as_dict(),
            source_id=context.request.source_id,
        )
    report = build_failure_report(summary=err or "validation failed", resolution_plan=[], attempts=[], final_guidance=err or "")
    return build_detailed_failure_result(
        message=err or "validation failed",
        error_category=ErrorCategory.VALIDATION,
        discovery_branch=DiscoveryBranch.NO_DISCOVERY,
        attempts=2,
        token_usage=llm.token_usage.as_dict(),
        processing_time_ms=int((time.time() - started) * 1000),
        hallucination_count=0,
        agentic_retry_count=0,
        failure_report=report,
        source_id=context.request.source_id,
    )


def _to_http(result: BuiltInGenerateResult) -> GenerateSQLResponse:
    explanation = result.explanation or result.message
    if result.query_type == "python_code" and result.success:
        explanation = explanation or "The following Python code uses pandas to analyze your data."
    elif result.query_type == "r_code" and result.success:
        explanation = explanation or "The following R code uses tidyverse to analyze your data."
    elif result.query_type == "sas_code" and result.success:
        explanation = explanation or "The following SAS code may resolve your request."
    return GenerateSQLResponse(
        sql=result.sql or "",
        explanation=explanation,
        query_type=result.query_type,
        context_text=result.context_text,
        discovery_branch=result.discovery_branch,
        source_id=result.source_id,
        success=result.success,
        attempts=result.attempts,
        token_usage=result.token_usage,
        processing_time_ms=result.processing_time_ms,
        hallucination_count=result.hallucination_count,
        agentic_retry_count=result.agentic_retry_count,
        canonical_question=result.canonical_question,
        error_category=result.error_category,
        failure_report=result.failure_report.model_dump() if result.failure_report else None,
    )


def discover_for_api(query: str, stores: SourceStores, top_k: int = 5, llm: Optional[LlmClient] = None) -> DiscoveryResult:
    engine = DiscoveryEngine(stores, llm)
    analysis = engine.analyze_query(query, None)
    return engine.discover(query, analysis, top_k=top_k)
