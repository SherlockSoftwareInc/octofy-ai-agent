"""System/user prompt builders including semantic-mode variant."""

from __future__ import annotations

import json
from typing import Any, List, Optional

from app.core.branch_taxonomy import GenerationMode, is_refinement_scenario
from app.models.pipeline import AgentContext, DiscoveryResult, FewShotExample, QueryAnalysis
from app.services.semantic_smq import looks_like_smq
from app.utils.query_vocabulary import model_item_name, model_items

# Phase 3.1 — strict, schema-free rule for the optimization scenario.
OPTIMIZATION_INSTRUCTIONS = """### OPTIMIZATION INSTRUCTIONS
You MUST work exclusively from the SQL shown below. Do NOT consult any catalog, schema, or knowledge base.
Do NOT invent, add, or remove tables or columns that are not already present in the provided SQL.
Preserve every filter, join, entity and the output grain exactly as written.
Change only syntax, structure, formatting or performance characteristics."""

# Phase 3.2 — refinement scenario: scope expansion is authorized, filters must survive.
REFINEMENT_INSTRUCTIONS = """### REFINEMENT INSTRUCTIONS
1. Base Context: Build upon the query logic, filters, and entities established in the editor SQL and conversation history.
2. Scope Expansion: If the user requests deeper granularity (e.g., transaction-level line items vs. summary views), you are authorized to query base tables and establish appropriate foreign key joins.
3. Filter Preservation: Ensure established domain filters (e.g., specific products, categories, or date ranges) are maintained in the new query structure."""

SCOPE_GUARD = """### SCOPE GUARD
Preserve all active filters from preceding turns unless the user explicitly requests their removal."""

# Objects in verified examples are in scope even when their column list was not hydrated.
# Two blocks, not three: the authorization (which objects are in scope) and the prohibition
# (what may never be invented, and how to report a genuinely missing object) used to restate
# each other in a third "CRITICAL SQL RULES" fragment whose section numbers ran 1, then 5.
AUTHORIZED_OBJECT_SCOPE = """### AUTHORIZED OBJECT SCOPE
You are authorized to reference database objects (tables, views, functions, and columns) that appear in ANY of the following sources:
1. Objects explicitly defined in `AVAILABLE SCHEMAS` or `PRIORITY SELECTED OBJECTS`.
2. Objects referenced in verified SQL queries within `KNOWLEDGE BASE EXAMPLES` / `PRECOMPUTED Q&A`.

Objects appearing in Knowledge Base examples represent pre-verified, production-tested database assets. You are fully authorized to query them even if their complete schema definition is omitted from `AVAILABLE SCHEMAS`. When you adapt a Knowledge Base query, trust the table names, column names, and join predicates used in that example."""

ZERO_HALLUCINATION_POLICY = """### ZERO HALLUCINATION POLICY
- You MUST only use database objects (tables, views, functions, columns) that are:
  a) Explicitly documented in `AVAILABLE SCHEMAS` or `PRIORITY SELECTED OBJECTS`, OR
  b) Directly referenced in the provided `KNOWLEDGE BASE EXAMPLES`.
- Objects referenced in `KNOWLEDGE BASE EXAMPLES` are pre-validated, so treat them as whitelisted: never report them as missing tables, and do NOT emit `TABLE_VALIDATION_ERROR` or `COLUMN_VALIDATION_ERROR` for objects or columns that appear in KB reference SQL.
- Never invent hypothetical table names or columns that appear in NEITHER the schema blocks NOR the Knowledge Base examples.
- Only return `TABLE_VALIDATION_ERROR: [MissingTableName]` if a required object cannot be found in `AVAILABLE SCHEMAS` AND is absent from the provided `KNOWLEDGE BASE EXAMPLES`."""

KNOWLEDGE_BASE_EXAMPLES_HEADER = """### KNOWLEDGE BASE EXAMPLES
The following are verified reference queries from the Knowledge Base.
- You may adapt these queries, reuse their join structures, and directly query any tables or views they reference.
- Adapt row limits, filters, date ranges, and projections to match the Target Request, but consider all referenced tables and columns as fully authorized."""

# Semantic mode retry correction: the previous attempt did not produce a usable payload.
SEMANTIC_OUTPUT_CORRECTION = """### SEMANTIC OUTPUT CORRECTION
The previous attempt did not produce a usable Semantic Model Query. Return only a fenced smq
code block. "metrics" and "dimensions" must be arrays of PLAIN STRINGS, never an array of
objects such as [{"metric":"row_count"}]. Use names that exist in the semantic model above.
Do not return SQL."""


def scenario_rules(context: AgentContext) -> str:
    """Scenario-specific rule block injected into every system prompt (Phase 3)."""
    mode = context.generation_mode
    if mode == GenerationMode.OPTIMIZATION:
        return OPTIMIZATION_INSTRUCTIONS
    if is_refinement_scenario(mode):
        return REFINEMENT_INSTRUCTIONS
    return ""


def _filter_block(context: AgentContext) -> str:
    lines = context.filter_state_text or "(none)"
    blocks = [f"ACTIVE SESSION FILTERS (inherited from preceding turns)\n{lines}"]
    if context.filter_state_text and context.filter_state_text != "(none)":
        blocks.append(SCOPE_GUARD)
    return "\n\n".join(blocks)


def grain_prompt_line(context: AgentContext) -> str:
    """Session grain line. Advisory when this turn fell back from semantic mode to SQL.

    The grain was captured while a semantic model was in force, so it is not guaranteed
    to still name an object this request can reference. A model that reads it as an
    identifier can emit ``GROUP BY <grain>`` against a column that does not exist.
    """
    grain = (getattr(context, "target_grain", None) or "").strip()
    if not grain:
        return ""
    if getattr(context, "grain_is_advisory", False):
        return (
            f"Target grain carried from conversational context: {grain} "
            "(advisory only: map it to the grain of this request rather than treating it "
            "as an object name. Do not use this text as a table, column, alias, or GROUP BY "
            "target. It may be referenced only where it names an object authorized above.)"
        )
    return f"Current target grain: {grain}"


def _first_model_name(model: Any, collection: str) -> str:
    """First named item in the model's ``measures``/``dimensions``, or ``""``."""
    for item in model_items(model, collection):
        name = model_item_name(item)
        if name:
            return name
    return ""


def _semantic_output_format(model: Any) -> str:
    """Strict SMQ contract, with a worked example that uses this model's real names."""
    metric = _first_model_name(model, "measures") or "<metric_name>"
    dimension = _first_model_name(model, "dimensions") or "<dimension_name>"
    example = json.dumps(
        {"metrics": [metric], "dimensions": [dimension], "filters": [], "timeframes": []},
        separators=(",", ":"),
    )
    return (
        "SEMANTIC OUTPUT FORMAT (STRICT)\n"
        "Return a fenced `smq` code block containing only JSON. A `smq` block is the ONLY "
        "accepted output in this mode: never answer with SQL, and never add prose, explanations, "
        "or extra keys.\n"
        "\n"
        "The block must contain exactly these four keys, with these exact types:\n"
        '{"metrics":["<metric_name>"],"dimensions":["<dimension_name>"],"filters":[],"timeframes":[]}\n'
        "\n"
        "Worked example using the metric and dimension names this model actually exposes:\n"
        f"{example}\n"
        "\n"
        'CRITICAL TYPE RULE: "metrics" and "dimensions" must be arrays of PLAIN STRINGS.\n'
        '- WRONG (rejected): {"metrics":[{"metric":"row_count"}],"dimensions":[{"dimension":"model"}]}\n'
        '- RIGHT (accepted): {"metrics":["row_count"],"dimensions":["model"]}\n'
        "\n"
        "Rules:\n"
        "- Use only metric names and dimension names present in AVAILABLE SEMANTIC MODELS. "
        "Never invent a metric.\n"
        '- Do not wrap a name in an object, and do not rename it with a key such as "metric", '
        '"measure", "name", or "dimension".\n'
        "- Preserve user intent, date scopes, and filters in SMQ form.\n"
    )


def _scenario_section(context: AgentContext) -> str:
    rules = scenario_rules(context)
    parts = [f"GENERATION MODE\n{context.generation_mode.value}"]
    if rules:
        parts.append(rules)
    if context.filter_state_text and context.filter_state_text != "(none)":
        parts.append(_filter_block(context))
    return "\n\n".join(parts)


def build_system_prompt(
    context: AgentContext,
    discovery: DiscoveryResult,
    semantic: bool = False,
    semantic_models_json: str = "[]",
    attempt_history: str = "",
    semantic_model: Any = None,
) -> str:
    dbms = context.dbms_type or "SQL Server"
    if semantic:
        semantic_blocks = [f"GENERATION MODE\n{context.generation_mode.value}"]
        if context.filter_state_text and context.filter_state_text != "(none)":
            semantic_blocks.append(_filter_block(context))
        grain = grain_prompt_line(context)
        if grain:
            semantic_blocks.append(grain)
        # Attempt history is the corrective signal. It is scanned for an SMQ payload so a
        # reply that drifted back to an unusable shape is called out explicitly.
        semantic_blocks.append(f"ATTEMPT HISTORY\n{attempt_history or '(first attempt)'}")
        if any(looks_like_smq(block) for block in semantic_blocks if block):
            semantic_blocks.append(SEMANTIC_OUTPUT_CORRECTION)
        semantic_extra = "\n\n".join(semantic_blocks)
        return (
            f"DBMS CONTEXT (SEMANTIC MODE)\nYou compile Semantic Model Queries for {dbms}.\n"
            f"AVAILABLE SEMANTIC MODELS (JSON)\n{semantic_models_json}\n"
            f"{semantic_extra}\n"
            f"{_semantic_output_format(semantic_model)}"
        )
    analysis = discovery.query_analysis
    examples = _format_examples(discovery.few_shot_examples, analysis)
    mappings = discovery.value_mappings
    mapping_text = "\n".join(
        f"- {m.get('value')} → {m.get('table')}.{m.get('column')}" for m in mappings
    ) or "(none)"
    grain = grain_prompt_line(context)
    grain_block = f"\n{grain}\n" if grain else ""
    return f"""DBMS CONTEXT (STRICT)
Target dialect: {dbms}. Use dialect-specific identifier quoting. Do not emit cross-dialect syntax.
PostgreSQL: LIMIT not TOP; CASE not IF(); explicit casts; schema-qualify objects.

{_scenario_section(context)}
{grain_block}
QUERY ANALYSIS
complexity={analysis.complexity}; keywords={', '.join(analysis.keywords)}; entities={', '.join(analysis.entities)}

ACTIVE BUSINESS CONTEXT
{discovery.active_groups.summary or '(none)'}

{AUTHORIZED_OBJECT_SCOPE}

{KNOWLEDGE_BASE_EXAMPLES_HEADER}
{examples}

VERIFIED DATA MAPPINGS
{mapping_text}

AVAILABLE SCHEMAS
{discovery.schema_context or discovery.selected_object_context}

SUPPLEMENTARY SCHEMAS
{discovery.supplementary_objects}

{ZERO_HALLUCINATION_POLICY}

ATTEMPT HISTORY
{attempt_history or '(first attempt)'}

OUTPUT FORMAT
Reasoning stays inside a /* ... */ comment block; the executable statement goes in a fenced SQL
block directly below it, in that order. Return a single valid {dbms} statement. Your reply must
match this layout exactly (the query body below is illustrative -- emit the real query):

/* Reasoning:
- [intent and decomposition]
- [tables, joins and filters]
*/

```sql
SELECT ...
```
"""


def build_refinement_system_prompt(
    context: AgentContext,
    discovery: DiscoveryResult,
    attempt_history: str = "",
) -> str:
    """Refinement prompt: anchored on the editor SQL, authorized to expand scope."""
    return build_system_prompt(context, discovery, attempt_history=attempt_history)


def build_optimization_system_prompt(
    context: AgentContext,
    existing_code: str,
    error_message: Optional[str] = None,
    target_language: str = "sql",
) -> str:
    """Schema-free rewrite prompt used by the no-discovery optimization path.

    Mirrors the built-in engine contract: the editor code is the *only* input allowed, so
    the model may not widen scope, consult the catalog, or change the result grain.
    """
    language = {"python": "Python", "r": "R", "sas": "SAS", "sql": (context.dbms_type or "SQL Server")}.get(
        target_language, "SQL"
    )
    error_block = f"\nERROR TO FIX\n{error_message}\n" if error_message else ""
    return f"""DBMS CONTEXT (STRICT)
Target dialect: {context.dbms_type or "SQL Server"}.

{scenario_rules(context) or OPTIMIZATION_INSTRUCTIONS}

GENERATION MODE
{context.generation_mode.value}

EDITOR {language.upper()} (the only permitted source of tables, columns and filters)
{existing_code}
{error_block}
OUTPUT FORMAT
Return only the rewritten {language} code, in place of the editor code above: no commentary, no
catalog lookups, no new objects, no markdown fence. The reply is exactly the code, starting at its
first line:

<rewritten {language} code>
"""


def build_optimization_user_prompt(
    context: AgentContext,
    existing_code: str,
    error_message: Optional[str] = None,
) -> str:
    parts = [f"User request:\n{context.combined_query or context.request.query}"]
    if error_message:
        parts.append(f"Error to fix:\n{error_message}")
    parts.append(f"Rewrite this code in place:\n{existing_code}")
    return "\n\n".join(parts)



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


PYTHON_CODE_GUIDELINES = """
PYTHON CODE GUIDELINES
- Connectivity:
    - A Python variable named DB_CONNECTION_STRING is already defined in the execution scope.
    - Use that variable directly. Do NOT read os.environ, os.getenv, or any environment variable.
    - Do NOT assign DB_CONNECTION_STRING from os.environ.
    - Do NOT hardcode server names, database names, or credentials.
    - Include a commented example, then create the engine from the injected variable:
      # DB_CONNECTION_STRING = ("mssql+pyodbc://@your_server_name/your_database_name?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes")
      engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)
    - MANDATORY pattern (no context managers, no engine.connect()):
      conn = engine.raw_connection()
      try:
          df = pd.read_sql("SELECT ...", conn)
      finally:
          conn.close()
- Data retrieval:
    - Use tables and columns documented in AVAILABLE SCHEMAS, or referenced in KNOWLEDGE BASE EXAMPLES. Objects in those examples are pre-validated; do not treat them as missing.
    - Embedded SQL MUST schema-qualify every table/view (dbo.Categories or [dbo].[Categories]). Never use a bare name like Categories.
    - Pay attention to VERIFIED DATA MAPPINGS for exact string values.
- Data manipulation:
    - Use pandas for filtering, aggregation, and transformation.
    - Assign the final DataFrame to final_result_df.
    - Write top-level code (do NOT wrap in def main()).
- Output format:
    - Start with # comments explaining the approach.
    - Return ONLY executable Python. No markdown fences, no standalone `python` line, no shell commands.
"""


def build_python_system_prompt(
    context: AgentContext,
    discovery: DiscoveryResult,
    attempt_history: str = "",
) -> str:
    analysis = discovery.query_analysis
    examples = _format_python_examples(discovery.few_shot_examples)
    mappings = discovery.value_mappings
    mapping_text = "\n".join(
        f"- {m.get('value')} → {m.get('table')}.{m.get('column')}" for m in mappings
    ) or "(none)"
    return f"""You are an expert Python programmer and data scientist specializing in pandas and sqlalchemy.
Generate production-ready Python that answers the user request against the target database.

DBMS CONTEXT
Target dialect: {context.dbms_type or "SQL Server"}. Embedded SQL must use this dialect.

{_scenario_section(context)}

QUERY ANALYSIS
complexity={analysis.complexity}; keywords={', '.join(analysis.keywords)}; entities={', '.join(analysis.entities)}

ACTIVE BUSINESS CONTEXT
{discovery.active_groups.summary or '(none)'}

{AUTHORIZED_OBJECT_SCOPE}

{KNOWLEDGE_BASE_EXAMPLES_HEADER}
{examples}

VERIFIED DATA MAPPINGS
{mapping_text}

AVAILABLE SCHEMAS
{discovery.schema_context or discovery.selected_object_context}

SUPPLEMENTARY SCHEMAS
{discovery.supplementary_objects}

ATTEMPT HISTORY
{attempt_history or '(first attempt)'}
{PYTHON_CODE_GUIDELINES}
"""


def build_python_user_prompt(context: AgentContext) -> str:
    req = context.request
    parts = [f"User request:\n{context.combined_query or req.query}"]
    if req.existing_code:
        parts.append(f"Existing Python or SQL:\n{req.existing_code}")
    if req.error_message:
        parts.append(f"Error to fix:\n{req.error_message}")
    if req.database_objects:
        parts.append("Pinned objects: " + ", ".join(req.database_objects))
    return "\n\n".join(parts)


def _format_python_examples(examples: List[FewShotExample]) -> str:
    if not examples:
        return "(none)"
    from app.utils.python_normalization import looks_like_python

    lines = []
    for ex in examples[:5]:
        if looks_like_python(ex.sql):
            lines.append(f"Q: {ex.question}\nPython:\n{ex.sql}")
        else:
            payload = ex.smq_query or ex.sql
            lines.append(f"Q: {ex.question}\nSQL (embed via pd.read_sql):\n{payload}")
    return "\n\n".join(lines)


def python_critic_prompt(code: str, schema_for_validation: str, query: str) -> List[dict]:
    system = (
        "You are a Python/pandas critic. Check that the script satisfies the user request "
        "and that every embedded SQL statement uses only the provided schema. "
        "Return JSON {requirements_satisfied:bool, schema_valid:bool, feedback:str, "
        "status:str|null, canonical_question:str|null, missing_objects:[]}. "
        "canonical_question is <= 25 words, same language, only when both flags are true."
    )
    user = f"USER QUERY:\n{query}\nSCHEMA:\n{schema_for_validation}\nPYTHON:\n{code}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


R_CODE_GUIDELINES = """
R CODE GUIDELINES
- Libraries: Always include library(DBI), library(odbc), library(dplyr), and library(ggplot2) when plotting.
- Database connectivity:
    - Use dbConnect(odbc::odbc(), ...) with Server = "your_server_name" and Database = "your_database_name".
    - Use Windows authentication with Trusted_Connection = "Yes" and do NOT include UID or PWD.
    - Use Driver = "SQL Server" as the default placeholder.
    - Do NOT hardcode credentials.
- Data retrieval:
    - Use tables and columns documented in AVAILABLE SCHEMAS, or referenced in KNOWLEDGE BASE EXAMPLES. Objects in those examples are pre-validated; do not treat them as missing.
    - Embedded SQL MUST schema-qualify every table/view (dbo.Categories or [dbo].[Categories]). Never use a bare name like Categories.
    - Prefer dbGetQuery(con, "SELECT ...") for filtered retrieval, or dbReadTable(con, Id(schema="schema", table="table")) for full tables.
    - Pay attention to VERIFIED DATA MAPPINGS for exact string values.
- Data manipulation:
    - Perform joins, filtering, and aggregation with dplyr (left_join, filter, group_by, summarise).
    - Use snake_case for variables.
- Execution flow:
    1. Library imports
    2. Connection
    3. Data ingestion
    4. Data transformation
    5. Connection closure with dbDisconnect(con) in a tryCatch finally block
- Output:
    - Print the result data frame or show the plot.
    - Start with # comments explaining the approach.
    - Return ONLY executable R. No markdown fences, no standalone `R` line, no shell commands.
"""


def build_r_system_prompt(
    context: AgentContext,
    discovery: DiscoveryResult,
    attempt_history: str = "",
) -> str:
    analysis = discovery.query_analysis
    examples = _format_r_examples(discovery.few_shot_examples)
    mappings = discovery.value_mappings
    mapping_text = "\n".join(
        f"- {m.get('value')} → {m.get('table')}.{m.get('column')}" for m in mappings
    ) or "(none)"
    return f"""You are an expert R programmer and data engineer specializing in the tidyverse.
Generate production-ready R that answers the user request against the target database.

DBMS CONTEXT
Target dialect: {context.dbms_type or "SQL Server"}. Embedded SQL must use this dialect.

{_scenario_section(context)}

QUERY ANALYSIS
complexity={analysis.complexity}; keywords={', '.join(analysis.keywords)}; entities={', '.join(analysis.entities)}

ACTIVE BUSINESS CONTEXT
{discovery.active_groups.summary or '(none)'}

{AUTHORIZED_OBJECT_SCOPE}

{KNOWLEDGE_BASE_EXAMPLES_HEADER}
{examples}

VERIFIED DATA MAPPINGS
{mapping_text}

AVAILABLE SCHEMAS
{discovery.schema_context or discovery.selected_object_context}

SUPPLEMENTARY SCHEMAS
{discovery.supplementary_objects}

ATTEMPT HISTORY
{attempt_history or '(first attempt)'}
{R_CODE_GUIDELINES}
"""


def build_r_user_prompt(context: AgentContext) -> str:
    req = context.request
    parts = [f"User request:\n{context.combined_query or req.query}"]
    if req.existing_code:
        parts.append(f"Existing R or SQL:\n{req.existing_code}")
    if req.error_message:
        parts.append(f"Error to fix:\n{req.error_message}")
    if req.database_objects:
        parts.append("Pinned objects: " + ", ".join(req.database_objects))
    return "\n\n".join(parts)


def _format_r_examples(examples: List[FewShotExample]) -> str:
    if not examples:
        return "(none)"
    from app.utils.r_normalization import looks_like_r

    lines = []
    for ex in examples[:5]:
        if looks_like_r(ex.sql):
            lines.append(f"Q: {ex.question}\nR:\n{ex.sql}")
        else:
            payload = ex.smq_query or ex.sql
            lines.append(f"Q: {ex.question}\nSQL (embed via dbGetQuery):\n{payload}")
    return "\n\n".join(lines)


def r_critic_prompt(code: str, schema_for_validation: str, query: str) -> List[dict]:
    system = (
        "You are an R/tidyverse critic. Check that the script satisfies the user request "
        "and that every embedded SQL statement uses only the provided schema. "
        "Return JSON {requirements_satisfied:bool, schema_valid:bool, feedback:str, "
        "status:str|null, canonical_question:str|null, missing_objects:[]}. "
        "canonical_question is <= 25 words, same language, only when both flags are true."
    )
    user = f"USER QUERY:\n{query}\nSCHEMA:\n{schema_for_validation}\nR:\n{code}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


SAS_CODE_GUIDELINES = """
SAS CODE GUIDELINES
- Connectivity:
    - Prefer PROC SQL pass-through: CONNECT TO ODBC AS dbcon (NOPROMPT="Driver={SQL Server};Server=your_server_name;Database=your_database_name;Trusted_Connection=Yes;").
    - Use Windows authentication. Do NOT include UID or PWD.
    - Alternatively LIBNAME dbdata ODBC with the same server/database placeholders.
    - Always DISCONNECT FROM the alias (or clear the libref) when finished.
- Data retrieval:
    - Use tables and columns documented in AVAILABLE SCHEMAS, or referenced in KNOWLEDGE BASE EXAMPLES. Objects in those examples are pre-validated; do not treat them as missing.
    - Embedded SQL MUST schema-qualify every table/view (dbo.Categories or [dbo].[Categories]). Never use a bare name like Categories.
    - Pay attention to VERIFIED DATA MAPPINGS for exact string values.
- Data manipulation (the SAS way):
    - Use PROC SQL for joins, filtering, and aggregation.
    - Use DATA steps for row-by-row logic or derived flags.
    - Use PROC FREQ / PROC MEANS / PROC SUMMARY / PROC RANK for analysis.
    - Use PROC SGPLOT for requested visualizations.
- Code quality:
    - Start with a /* comment */ explaining the approach.
    - Use TITLE statements to label outputs.
    - Handle SAS missing values (. or blank).
    - End steps with QUIT; or RUN;.
    - Return ONLY executable SAS. No markdown fences, no standalone `sas` line, no shell commands.
"""


def build_sas_system_prompt(
    context: AgentContext,
    discovery: DiscoveryResult,
    attempt_history: str = "",
) -> str:
    analysis = discovery.query_analysis
    examples = _format_sas_examples(discovery.few_shot_examples)
    mappings = discovery.value_mappings
    mapping_text = "\n".join(
        f"- {m.get('value')} → {m.get('table')}.{m.get('column')}" for m in mappings
    ) or "(none)"
    return f"""You are an expert SAS programmer and data analyst.
Generate production-ready SAS that answers the user request against the target database.

DBMS CONTEXT
Target dialect: {context.dbms_type or "SQL Server"}. Embedded SQL must use this dialect.

{_scenario_section(context)}

QUERY ANALYSIS
complexity={analysis.complexity}; keywords={', '.join(analysis.keywords)}; entities={', '.join(analysis.entities)}

ACTIVE BUSINESS CONTEXT
{discovery.active_groups.summary or '(none)'}

{AUTHORIZED_OBJECT_SCOPE}

{KNOWLEDGE_BASE_EXAMPLES_HEADER}
{examples}

VERIFIED DATA MAPPINGS
{mapping_text}

AVAILABLE SCHEMAS
{discovery.schema_context or discovery.selected_object_context}

SUPPLEMENTARY SCHEMAS
{discovery.supplementary_objects}

ATTEMPT HISTORY
{attempt_history or '(first attempt)'}
{SAS_CODE_GUIDELINES}
"""


def build_sas_user_prompt(context: AgentContext) -> str:
    req = context.request
    parts = [f"User request:\n{context.combined_query or req.query}"]
    if req.existing_code:
        parts.append(f"Existing SAS or SQL:\n{req.existing_code}")
    if req.error_message:
        parts.append(f"Error to fix:\n{req.error_message}")
    if req.database_objects:
        parts.append("Pinned objects: " + ", ".join(req.database_objects))
    return "\n\n".join(parts)


def _format_sas_examples(examples: List[FewShotExample]) -> str:
    if not examples:
        return "(none)"
    from app.utils.sas_normalization import looks_like_sas

    lines = []
    for ex in examples[:5]:
        if looks_like_sas(ex.sql):
            lines.append(f"Q: {ex.question}\nSAS:\n{ex.sql}")
        else:
            payload = ex.smq_query or ex.sql
            lines.append(f"Q: {ex.question}\nSQL (embed via CONNECTION TO):\n{payload}")
    return "\n\n".join(lines)


def sas_critic_prompt(code: str, schema_for_validation: str, query: str) -> List[dict]:
    system = (
        "You are a SAS/PROC SQL critic. Check that the script satisfies the user request "
        "and that every embedded SQL statement uses only the provided schema. "
        "Return JSON {requirements_satisfied:bool, schema_valid:bool, feedback:str, "
        "status:str|null, canonical_question:str|null, missing_objects:[]}. "
        "canonical_question is <= 25 words, same language, only when both flags are true."
    )
    user = f"USER QUERY:\n{query}\nSCHEMA:\n{schema_for_validation}\nSAS:\n{code}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


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
