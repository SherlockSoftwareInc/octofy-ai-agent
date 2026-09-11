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
    - Use ONLY tables and columns in AVAILABLE SCHEMAS.
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
    - Use ONLY tables and columns in AVAILABLE SCHEMAS.
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
    - Use ONLY tables and columns in AVAILABLE SCHEMAS.
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
