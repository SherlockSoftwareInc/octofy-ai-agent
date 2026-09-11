"""Error taxonomy and structured failure-report builders."""

from typing import Any, Dict, List, Optional

from app.models.pipeline import BuiltInAttemptReport, BuiltInFailureReport, BuiltInGenerateResult, ScoredObject


class ErrorCategory:
    SAFETY = "safety"
    GENERATION = "generation"
    REQUIREMENT = "requirement"
    SCHEMA = "schema"
    VALIDATION = "validation"
    SYNTAX = "syntax"
    TIMEOUT = "timeout"
    DETERMINISTIC_MISSING_OBJECT = "deterministic_missing_object"
    PRIORITY_VALIDATION_FAILED = "priority_validation_failed"
    SEMANTIC_COMPILATION = "semantic_compilation"
    APP_FEATURE = "app_feature"
    OFF_TOPIC = "off_topic"


def build_failure_report(
    *,
    summary: str,
    resolution_plan: List[str],
    attempts: List[BuiltInAttemptReport],
    final_guidance: str,
    candidates: Optional[List[ScoredObject]] = None,
) -> BuiltInFailureReport:
    return BuiltInFailureReport(
        summary=summary,
        resolution_plan=resolution_plan,
        attempts=attempts,
        final_resolution_guidance=final_guidance,
        candidate_objects=candidates or [],
    )


def wrap_failure_sql_comment(message: str) -> str:
    body = message.replace("*/", "* /")
    return f"/*\n{body}\n*/"


def wrap_failure_python_comment(message: str) -> str:
    lines = (message or "").replace("\r\n", "\n").split("\n")
    return "\n".join(f"# {line}" if line else "#" for line in lines)


def wrap_failure_r_comment(message: str) -> str:
    return wrap_failure_python_comment(message)


_LANGUAGE_QUERY_TYPES = {
    "python": "python_code",
    "r": "r_code",
    "sas": "sas_code",
}


def apply_language_result(result: BuiltInGenerateResult, target_language: str) -> BuiltInGenerateResult:
    query_type = _LANGUAGE_QUERY_TYPES.get(target_language)
    if not query_type:
        return result
    if result.query_type == "database":
        result.query_type = query_type
    if not result.success and (result.sql or "").lstrip().startswith("/*"):
        if target_language == "python":
            result.sql = wrap_failure_python_comment(result.message or result.explanation or "")
        elif target_language == "r":
            result.sql = wrap_failure_r_comment(result.message or result.explanation or "")
    return result


def build_detailed_failure_result(
    *,
    message: str,
    error_category: str,
    discovery_branch: Optional[str],
    attempts: int,
    token_usage: Dict[str, int],
    processing_time_ms: int,
    hallucination_count: int,
    agentic_retry_count: int,
    failure_report: BuiltInFailureReport,
    source_id: Optional[str] = None,
    canonical_question: Optional[str] = None,
    context_text: Optional[str] = None,
) -> BuiltInGenerateResult:
    sql_comment = wrap_failure_sql_comment(message)
    return BuiltInGenerateResult(
        success=False,
        sql=sql_comment,
        message=message,
        discovery_branch=discovery_branch,
        attempts=attempts,
        token_usage=token_usage,
        processing_time_ms=processing_time_ms,
        hallucination_count=hallucination_count,
        agentic_retry_count=agentic_retry_count,
        canonical_question=canonical_question,
        context_text=context_text,
        failure_report=failure_report,
        error_category=error_category,
        source_id=source_id,
    )


def unknown_source_detail(source_id: str) -> Dict[str, Any]:
    return {"detail": "Resource not found", "source_id": source_id}
