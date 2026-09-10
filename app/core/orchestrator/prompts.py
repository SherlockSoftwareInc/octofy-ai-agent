"""System/user prompt builders including semantic-mode variant."""

from __future__ import annotations

from typing import List, Optional

from app.models.pipeline import AgentContext, DiscoveryResult, FewShotExample, QueryAnalysis


def build_system_prompt(
    context: AgentContext,
    discovery: DiscoveryResult,
    semantic: bool = False,
    semantic_models_json: str = "[]",
    attempt_history: str = "",
) -> str:
    dbms = context.dbms_type or "SQL Server"
    if semantic:
        return (
            f"DBMS CONTEXT (SEMANTIC MODE)\nYou compile Semantic Model Queries for {dbms}.\n"
            f"AVAILABLE SEMANTIC MODELS (JSON)\n{semantic_models_json}\n"
            "SEMANTIC OUTPUT FORMAT (STRICT)\n"
            "Reply with a fenced ```smq block containing "
            '{"metrics":[],"dimensions":[],"filters":[],"timeframes":[]}. '
            "Use only model names. No reasoning, view, or scripting sections."
        )
    analysis = discovery.query_analysis
    examples = _format_examples(discovery.few_shot_examples, analysis)
    mappings = discovery.value_mappings
    mapping_text = "\n".join(
        f"- {m.get('value')} → {m.get('table')}.{m.get('column')}" for m in mappings
    ) or "(none)"
    return f"""DBMS CONTEXT (STRICT)
Target dialect: {dbms}. Use dialect-specific identifier quoting. Do not emit cross-dialect syntax.
PostgreSQL: LIMIT not TOP; CASE not IF(); explicit casts; schema-qualify objects.

GENERATION MODE
{context.generation_mode.value}

QUERY ANALYSIS
complexity={analysis.complexity}; keywords={', '.join(analysis.keywords)}; entities={', '.join(analysis.entities)}

ACTIVE BUSINESS CONTEXT
{discovery.active_groups.summary or '(none)'}

KNOWLEDGE BASE EXAMPLES
{examples}

VERIFIED DATA MAPPINGS
{mapping_text}

AVAILABLE SCHEMAS
{discovery.schema_context or discovery.selected_object_context}

SUPPLEMENTARY SCHEMAS
{discovery.supplementary_objects}

ATTEMPT HISTORY
{attempt_history or '(first attempt)'}

OUTPUT FORMAT
Optionally include a /* reasoning */ block, then fenced SQL. Return a single valid {dbms} statement.
"""


def build_user_prompt(context: AgentContext) -> str:
    req = context.request
    parts = [f"User request:\n{context.combined_query or req.query}"]
    if req.existing_code:
        parts.append(f"Existing SQL:\n{req.existing_code}")
    if req.error_message:
        parts.append(f"Error to fix:\n{req.error_message}")
    if req.database_objects:
        parts.append("Pinned objects: " + ", ".join(req.database_objects))
    return "\n\n".join(parts)


def _format_examples(examples: List[FewShotExample], analysis: QueryAnalysis) -> str:
    if not examples:
        return "(none)"
    # complexity-matched, precomputed prepended already; cap 5
    lines = []
    for ex in examples[:5]:
        payload = ex.smq_query or ex.sql
        lines.append(f"Q: {ex.question}\nSQL:\n{payload}")
    return "\n\n".join(lines)


def critic_prompt(sql: str, schema_for_validation: str, query: str, semantic_json: Optional[str] = None) -> List[dict]:
    if semantic_json:
        system = (
            "Validate the SMQ/SQL against the semantic model. "
            "Return JSON {requirements_satisfied:bool, schema_valid:bool, feedback:str, "
            "status:str|null, canonical_question:str|null, missing_objects:[]}."
        )
        user = f"MODEL:\n{semantic_json}\nQUERY:\n{query}\nSQL:\n{sql}"
    else:
        system = (
            "You are a SQL critic. Check requirements satisfaction and schema adherence. "
            "Return JSON {requirements_satisfied:bool, schema_valid:bool, feedback:str, "
            "status:str|null, canonical_question:str|null, missing_objects:[]}. "
            "canonical_question is <= 25 words, same language, only when both flags are true."
        )
        user = f"USER QUERY:\n{query}\nSCHEMA:\n{schema_for_validation}\nSQL:\n{sql}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
