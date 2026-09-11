"""Bounded retry loop with frozen validation order."""

from __future__ import annotations

import json
import time
from typing import Callable, Dict, List, Optional, Tuple

from app.core.branch_taxonomy import PipelineStage
from app.core.constants import (
    HallucinationExitThreshold,
    HallucinationExitThresholdWithBreaker,
    MaxGenerationTimeMs,
    MaxRecoveryExpansion,
    MaxRetries,
    MissingGroupMemberValidationStatus,
    MissingObjectBreakThreshold,
    PresencePenaltyAfterLoop,
    SemanticCompilationTimeoutMs,
    SemanticSmqParseRetryOnFailure,
)
from app.core.errors import (
    ErrorCategory,
    build_detailed_failure_result,
    build_failure_report,
)
from app.core.orchestrator.prompts import (
    build_python_system_prompt,
    build_python_user_prompt,
    build_system_prompt,
    build_user_prompt,
    critic_prompt,
    python_critic_prompt,
)
from app.models.pipeline import (
    AgentContext,
    BuiltInAttemptReport,
    BuiltInGenerateResult,
    CombinedValidationResult,
    DiscoveryResult,
    ScoredObject,
    SmqPayload,
)
from app.services.python_interceptor import PythonInterceptor
from app.services.query_interceptor import QueryInterceptor
from app.services.semantic_compiler import SemanticCompilationError, SemanticCompiler
from app.services.sql_error_classifier import SqlErrorClassifier
from app.services.sql_validator import SqlValidator
from app.utils.python_normalization import (
    extract_python_body,
    extract_sql_from_python,
    structural_python_hash,
    syntax_check_python,
)
from app.utils.regexes import parse_validation_sentinels
from app.utils.sql_normalization import extract_sql_body, structural_sql_hash


def run_attempt_loop(
    context: AgentContext,
    discovery: DiscoveryResult,
    stores,
    llm,
    emit: Callable,
    *,
    time_budget_ms: int = MaxGenerationTimeMs,
    semantic_mode: bool = False,
    started_at: Optional[float] = None,
    target_language: str = "sql",
) -> BuiltInGenerateResult:
    started_at = started_at or time.time()
    interceptor = QueryInterceptor()
    python_interceptor = PythonInterceptor()
    validator = SqlValidator(context.request.source_id, context.dbms_type)
    python_mode = target_language == "python"
    if python_mode:
        semantic_mode = False
    classifier = SqlErrorClassifier()
    compiler = SemanticCompiler()
    attempt_reports: List[BuiltInAttemptReport] = []
    hash_history: List[str] = []
    missing_counts: Dict[str, int] = {}
    missing_cat_counts: Dict[Tuple[str, str], int] = {}
    pending_recovery: List[ScoredObject] = []
    loop_breaker = False
    circuit_breaker = False
    broadened = False
    hallucination_count = 0
    agentic_retry = 0
    last_sql = ""
    last_error = ""
    last_prompt = ""
    canonical = None
    active_model = stores.semantic.get_active_model() if semantic_mode else None
    semantic_json = active_model.model_dump_json() if active_model else "[]"
    smq_retry_used = False

    for attempt in range(1, MaxRetries + 1):
        elapsed_ms = int((time.time() - started_at) * 1000)
        if elapsed_ms > time_budget_ms:
            report = build_failure_report(
                summary="Generation timed out",
                resolution_plan=["Retry with a narrower question", "Pin specific tables"],
                attempts=attempt_reports,
                final_guidance="The 120s generation budget was exceeded.",
            )
            return build_detailed_failure_result(
                message="Generation timed out",
                error_category=ErrorCategory.TIMEOUT,
                discovery_branch=discovery.branch,
                attempts=attempt,
                token_usage=llm.token_usage.as_dict() if llm else {},
                processing_time_ms=elapsed_ms,
                hallucination_count=hallucination_count,
                agentic_retry_count=agentic_retry,
                failure_report=report,
                source_id=context.request.source_id,
            )

        emit(PipelineStage.ATTEMPT, f"Generation attempt {attempt}/{MaxRetries}", attempt=attempt)

        if pending_recovery or loop_breaker:
            discovery.objects = _merge_recovery(discovery.objects, pending_recovery)
            pending_recovery = []
            loop_breaker = False
            agentic_retry += 1

        history_text = _compact_history(attempt_reports)
        system = build_system_prompt(
            context,
            discovery,
            semantic=semantic_mode,
            semantic_models_json=semantic_json,
            attempt_history=history_text,
        )
        user = build_user_prompt(context)
        last_prompt = system + "\n" + user
        penalty = PresencePenaltyAfterLoop if hallucination_count else None
        try:
            raw = llm.complete(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                presence_penalty=penalty,
            )
        except Exception as exc:
            attempt_reports.append(
                BuiltInAttemptReport(attempt_number=attempt, stage="generation", what_was_tried="LLM call", why_it_failed=str(exc))
            )
            continue

        sql = extract_sql_body(raw)
        if semantic_mode:
            smq = _extract_smq(raw)
            if smq is None:
                if SemanticSmqParseRetryOnFailure and not smq_retry_used:
                    smq_retry_used = True
                    attempt_reports.append(
                        BuiltInAttemptReport(attempt_number=attempt, stage="semantic_compilation", what_was_tried="parse SMQ", why_it_failed="missing payload")
                    )
                    continue
                from app.core.constants import SemanticCompilationFallbackToRawSql

                if not SemanticCompilationFallbackToRawSql:
                    return _fail(
                        "semantic_compilation",
                        "Missing SMQ payload",
                        attempt,
                        attempt_reports,
                        discovery,
                        llm,
                        started_at,
                        hallucination_count,
                        agentic_retry,
                        context,
                    )
            else:
                try:
                    sql = compiler.compile(smq, active_model, context.dbms_type, timeout_ms=SemanticCompilationTimeoutMs)
                except SemanticCompilationError as exc:
                    attempt_reports.append(
                        BuiltInAttemptReport(
                            attempt_number=attempt,
                            stage="semantic_compilation",
                            what_was_tried="compile SMQ",
                            why_it_failed=str(exc),
                        )
                    )
                    continue

        if not sql:
            attempt_reports.append(
                BuiltInAttemptReport(attempt_number=attempt, stage="generation", what_was_tried="LLM output", why_it_failed="empty")
            )
            continue
        last_sql = sql

        # 1. Safety
        user_write = bool(context.request.is_user_code and any(w in (context.request.query or "").lower() for w in ("insert", "update", "delete", "drop")))
        ok, reason = interceptor.check(sql, user_requested_write=user_write)
        if not ok:
            return _fail(ErrorCategory.SAFETY, reason or "blocked", attempt, attempt_reports, discovery, llm, started_at, hallucination_count, agentic_retry, context, sql)

        # 2. Sentinels
        table_err, col_err = parse_validation_sentinels(raw)
        if table_err or col_err:
            objs = _expand_missing(table_err or col_err, stores, exact_columns=context.request and discovery.query_analysis.extracted_columns if col_err else None)
            pending_recovery.extend(objs[:MaxRecoveryExpansion])
            _bump_missing(missing_counts, missing_cat_counts, table_err or col_err, "sentinel")
            if _breaker_tripped(missing_counts):
                circuit_breaker = True
                return _fail(ErrorCategory.DETERMINISTIC_MISSING_OBJECT, table_err or col_err, attempt, attempt_reports, discovery, llm, started_at, hallucination_count, agentic_retry, context, sql)
            continue

        # 3. Structural hash
        digest = structural_sql_hash(sql)
        if digest in hash_history:
            hallucination_count += 1
            loop_breaker = True
            threshold = HallucinationExitThresholdWithBreaker if circuit_breaker else HallucinationExitThreshold
            if hallucination_count >= threshold:
                return _fail(
                    "hallucination_loop",
                    "Repeated SQL structure detected",
                    attempt,
                    attempt_reports,
                    discovery,
                    llm,
                    started_at,
                    hallucination_count,
                    agentic_retry,
                    context,
                    sql,
                )
        hash_history.append(digest)

        allowed = [f"{o.schema_name}.{o.object_name}" for o in discovery.objects]
        db_ok, db_err, db_missing = False, "", []
        skip_critic = False

        # 4. Attempt-1 DB pre-check before critic
        if attempt == 1:
            emit(PipelineStage.DB_VALIDATION, "Database pre-check (attempt 1)")
            db_ok, db_err, db_missing = validator.validate(sql, allowed)
            if db_ok:
                skip_critic = True

        critic_result = CombinedValidationResult()
        if not skip_critic:
            emit(PipelineStage.CRITIC, "LLM critic")
            critic_result = _run_critic(llm, sql, discovery.schema_context_for_validation, context.combined_query, semantic_json if semantic_mode else None)
            if critic_result.canonical_question:
                canonical = critic_result.canonical_question
            if not critic_result.requirements_satisfied:
                attempt_reports.append(
                    BuiltInAttemptReport(attempt_number=attempt, stage="critic", what_was_tried="requirements", why_it_failed=critic_result.feedback)
                )
                continue
            if not critic_result.schema_valid:
                if critic_result.status == MissingGroupMemberValidationStatus and not broadened:
                    broadened = True
                    emit(PipelineStage.RECOVERY, "Broadened group-member recovery")
                    continue
                pending_recovery.extend(_expand_missing(",".join(critic_result.missing_objects), stores)[:MaxRecoveryExpansion])
                continue

        if not skip_critic:
            emit(PipelineStage.DB_VALIDATION, "Database validation")
            db_ok, db_err, db_missing = validator.validate(sql, allowed)

        if db_ok:
            elapsed_ms = int((time.time() - started_at) * 1000)
            return BuiltInGenerateResult(
                success=True,
                sql=sql,
                message="OK",
                discovery_branch=discovery.branch,
                attempts=attempt,
                token_usage=llm.token_usage.as_dict() if llm else {},
                processing_time_ms=elapsed_ms,
                hallucination_count=hallucination_count,
                agentic_retry_count=agentic_retry,
                canonical_question=canonical,
                context_text=last_prompt,
                source_id=context.request.source_id,
            )

        last_error = db_err
        category = classifier.classify(db_err)
        missing_obj = classifier.extract_missing_object(db_err)
        if missing_obj:
            _bump_missing(missing_counts, missing_cat_counts, missing_obj, category)
            pending_recovery.extend(_expand_missing(missing_obj, stores)[:MaxRecoveryExpansion])
            if _breaker_tripped(missing_counts):
                circuit_breaker = True
                return _fail(ErrorCategory.DETERMINISTIC_MISSING_OBJECT, missing_obj, attempt, attempt_reports, discovery, llm, started_at, hallucination_count, agentic_retry, context, sql)
        if db_err.upper().startswith("TABLE_VALIDATION_ERROR"):
            pending_recovery.extend(_expand_missing(db_err, stores)[:MaxRecoveryExpansion])
        attempt_reports.append(
            BuiltInAttemptReport(
                attempt_number=attempt,
                stage="db_validation",
                what_was_tried=sql[:500],
                why_it_failed=db_err,
                recovery_action="expand missing objects",
                candidate_objects=db_missing,
            )
        )

    elapsed_ms = int((time.time() - started_at) * 1000)
    report = build_failure_report(
        summary=last_error or "Failed after max retries",
        resolution_plan=["Review missing objects", "Add few-shot examples", "Pin tables"],
        attempts=attempt_reports,
        final_guidance="All generation attempts were exhausted.",
        candidates=discovery.objects,
    )
    return build_detailed_failure_result(
        message=last_error or "Failed after max retries",
        error_category=ErrorCategory.VALIDATION,
        discovery_branch=discovery.branch,
        attempts=MaxRetries,
        token_usage=llm.token_usage.as_dict() if llm else {},
        processing_time_ms=elapsed_ms,
        hallucination_count=hallucination_count,
        agentic_retry_count=agentic_retry,
        failure_report=report,
        source_id=context.request.source_id,
        context_text=last_prompt,
    )


def _run_critic(llm, sql, schema, query, semantic_json) -> CombinedValidationResult:
    if llm is None:
        return CombinedValidationResult()
    try:
        data = llm.complete_json(critic_prompt(sql, schema, query, semantic_json))
        return CombinedValidationResult(
            requirements_satisfied=bool(data.get("requirements_satisfied", True)),
            schema_valid=bool(data.get("schema_valid", True)),
            feedback=data.get("feedback") or "",
            status=data.get("status"),
            canonical_question=data.get("canonical_question"),
            missing_objects=list(data.get("missing_objects") or []),
        )
    except Exception:
        return CombinedValidationResult()


def _extract_smq(raw: str) -> Optional[SmqPayload]:
    import re

    fence = re.search(r"```smq\s*([\s\S]*?)```", raw or "", re.IGNORECASE)
    text = fence.group(1) if fence else raw
    start = (text or "").find('{"metrics"')
    if start < 0:
        start = (text or "").find("{")
    if start < 0:
        return None
    end = text.rfind("}")
    try:
        data = json.loads(text[start : end + 1])
        return SmqPayload.model_validate(data)
    except Exception:
        return None


def _expand_missing(token: str, stores, exact_columns=None) -> List[ScoredObject]:
    from app.models.pipeline import ScoredObject

    q = token or ""
    objs = stores.vector_search.search_objects(q, top_k=5)
    if exact_columns:
        for col in exact_columns:
            objs.extend(stores.vector_search.search_objects(col, top_k=3))
    models = stores.semantic.search_models(q, top_k=2)
    for m in models:
        objs.insert(0, ScoredObject(schema_name="semantic", object_name=m.label, object_type="SemanticModel", required=True, score=1.0))
    return objs


def _merge_recovery(current, extra):
    from app.utils.rrf import merge_and_dedup

    return merge_and_dedup(list(current) + list(extra))


def _bump_missing(counts, cat_counts, obj, category):
    key = (obj or "").lower()
    counts[key] = counts.get(key, 0) + 1
    cat_counts[(key, category)] = cat_counts.get((key, category), 0) + 1


def _breaker_tripped(counts) -> bool:
    return any(v >= MissingObjectBreakThreshold for v in counts.values())


def _compact_history(reports: List[BuiltInAttemptReport]) -> str:
    if not reports:
        return ""
    lines = []
    for i, r in enumerate(reports):
        if i == len(reports) - 1:
            lines.append(r.model_dump_json())
        else:
            lines.append(f"attempt {r.attempt_number} {r.stage}: {r.why_it_failed}")
    return "\n".join(lines)


def _fail(category, message, attempt, reports, discovery, llm, started_at, hallu, agentic, context, sql=""):
    elapsed = int((time.time() - started_at) * 1000)
    report = build_failure_report(
        summary=message,
        resolution_plan=["Inspect candidates", "Adjust pins"],
        attempts=reports,
        final_guidance=message,
        candidates=discovery.objects,
    )
    result = build_detailed_failure_result(
        message=message,
        error_category=category,
        discovery_branch=discovery.branch,
        attempts=attempt,
        token_usage=llm.token_usage.as_dict() if llm else {},
        processing_time_ms=elapsed,
        hallucination_count=hallu,
        agentic_retry_count=agentic,
        failure_report=report,
        source_id=context.request.source_id,
    )
    if sql:
        result.sql = result.sql  # keep comment wrapper from builder
    return result
