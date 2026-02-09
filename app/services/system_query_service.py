"""
System Query Service - Handles SQL Server system metadata queries.

Provides LLM-based intent classification (data_query / system_metadata / off_topic)
and a specialized prompt builder for system catalog queries.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# The three valid intent categories
VALID_INTENTS = {"data_query", "system_metadata", "off_topic"}

# Base classification prompt — kept minimal to reduce latency and token cost.
# Database context is appended dynamically by _build_classification_prompt().
CLASSIFICATION_SYSTEM_PROMPT_BASE = """You are a query intent classifier for a SQL Server database assistant.

Classify the user's message into exactly ONE of these categories:

- **data_query** — The user wants to retrieve, analyze, or aggregate BUSINESS DATA stored in the database (e.g., sales figures, customer counts, revenue trends, employee records).
- **system_metadata** — The user wants information about the DATABASE STRUCTURE or SERVER itself (e.g., list tables, show columns, table row counts, SQL Server version, indexes, schemas, which tables have a certain column).
- **off_topic** — The user's message is NOT related to querying or exploring the database at all (e.g., greetings, general knowledge questions, jokes, SQL syntax explanations). This includes requests about business data that does NOT exist in this database."""


CLASSIFICATION_DB_CONTEXT_TEMPLATE = """
This database is: {db_name} — {db_description}
It contains data about: {db_keywords}.
If the user asks about data that clearly does NOT relate to these topics, classify it as off_topic."""

CLASSIFICATION_MULTI_SOURCE_CONTEXT_TEMPLATE = """
Available data sources:
{data_sources}
If the user's request is about business data, identify which data source(s) match the topic."""

CLASSIFICATION_REPLY_INSTRUCTION = """
Reply with a compact JSON object using this exact shape:
{"intent":"data_query|system_metadata|off_topic","related_sources":["Data Source Name"]}
Use ONLY data source names from the list above. If none apply, use an empty list.
Do NOT include any other text."""


def _get_source_field(source: Any, field: str) -> Optional[Any]:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field)
    return getattr(source, field, None)


def _build_source_name_map(data_sources: Optional[List[Any]]) -> Dict[str, str]:
    name_map: Dict[str, str] = {}
    for source in data_sources or []:
        name = _get_source_field(source, "name")
        if not name:
            continue
        name_map[str(name).strip().lower()] = str(name).strip()
    return name_map


def _format_data_sources_context(data_sources: Optional[List[Any]]) -> str:
    lines: List[str] = []
    for source in data_sources or []:
        name = _get_source_field(source, "name")
        if not name:
            continue
        description = _get_source_field(source, "description") or "No description provided"
        keywords = _get_source_field(source, "keywords") or []
        keywords_str = ", ".join(keywords) if keywords else "various topics"
        lines.append(f"- {name}: {description} Keywords: {keywords_str}.")

    if not lines:
        return ""

    return CLASSIFICATION_MULTI_SOURCE_CONTEXT_TEMPLATE.format(
        data_sources="\n".join(lines)
    )


def _normalize_related_sources(
    related_sources: Any,
    source_name_map: Dict[str, str],
) -> List[str]:
    if not related_sources:
        return []
    if isinstance(related_sources, str):
        related_sources = [related_sources]
    if not isinstance(related_sources, list):
        return []

    normalized: List[str] = []
    seen = set()
    for source in related_sources:
        if source is None:
            continue
        source_name = str(source).strip()
        if not source_name:
            continue
        canonical = source_name_map.get(source_name.lower())
        if not canonical or canonical in seen:
            continue
        normalized.append(canonical)
        seen.add(canonical)
    return normalized


def _parse_classification_response(
    response: Optional[str],
    source_name_map: Dict[str, str],
) -> Dict[str, Any]:
    raw = (response or "").strip()
    if not raw:
        return {"intent": "", "related_sources": []}

    try:
        parsed = json.loads(raw)
    except Exception:
        return {"intent": raw.lower(), "related_sources": []}

    if isinstance(parsed, dict):
        intent = str(parsed.get("intent", "")).strip().lower()
        related_sources = _normalize_related_sources(
            parsed.get("related_sources", []),
            source_name_map,
        )
        return {"intent": intent, "related_sources": related_sources}

    if isinstance(parsed, str):
        return {"intent": parsed.strip().lower(), "related_sources": []}

    return {"intent": "", "related_sources": []}


def _build_classification_prompt(
    db_name: Optional[str] = None,
    db_description: Optional[str] = None,
    db_keywords: Optional[List[str]] = None,
    data_sources: Optional[List[Any]] = None,
) -> str:
    """
    Build the classification system prompt, optionally including database context.

    When database context is provided, the LLM can distinguish between relevant
    business queries and queries about data that doesn't exist in this database
    (classifying the latter as off_topic).

    Args:
        db_name: Friendly name of the database (e.g., "Northwind Database").
        db_description: Short description of the database's domain.
        db_keywords: List of topic keywords (e.g., ["sales", "customers"]).

    Returns:
        A complete system prompt string for the classifier.
    """
    prompt = CLASSIFICATION_SYSTEM_PROMPT_BASE

    data_sources_context = _format_data_sources_context(data_sources)
    if data_sources_context:
        prompt += data_sources_context
    elif db_name and db_description:
        keywords_str = ", ".join(db_keywords) if db_keywords else "various topics"
        prompt += CLASSIFICATION_DB_CONTEXT_TEMPLATE.format(
            db_name=db_name,
            db_description=db_description,
            db_keywords=keywords_str,
        )

    prompt += CLASSIFICATION_REPLY_INSTRUCTION
    return prompt


def classify_query_intent(
    query: str,
    llm_service,
    db_name: Optional[str] = None,
    db_description: Optional[str] = None,
    db_keywords: Optional[List[str]] = None,
    data_sources: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Classify user query intent using the LLM.

    Args:
        query: The user's natural language query.
        llm_service: An LLM service instance with a chat_completion() method.
        db_name: Optional friendly name of the database.
        db_description: Optional description of the database's domain.
        db_keywords: Optional list of topic keywords for the database.

    Returns:
        Dict with keys: "intent" and "related_sources".
        Defaults to intent "data_query" on any error (safest fallback — lets the
        existing pipeline handle it), and an empty related_sources list.
    """
    if not query or not query.strip():
        return {"intent": "off_topic", "related_sources": []}

    try:
        system_prompt = _build_classification_prompt(
            db_name,
            db_description,
            db_keywords,
            data_sources,
        )

        source_guid_map = {}
        name_to_guid_map = {}
        for source in data_sources or []:
            name = _get_source_field(source, "name")
            guid = _get_source_field(source, "source_id")
            if name and guid:
                source_guid_map[str(guid).strip()] = str(name).strip()
                name_to_guid_map[str(name).strip().lower()] = str(guid).strip()

        if source_guid_map:
            source_lines = "\n".join(
                [f"- {name} (guid: {guid})" for guid, name in source_guid_map.items()]
            )
            system_prompt += f"""

Available data sources (use guid values only):
{source_lines}

IGNORE any earlier reply format. Reply with a compact JSON object using this exact shape:
{{"intent":"data_query|system_metadata|off_topic","related_source_guids":["source_guid"]}}
Use ONLY source_guid values from the list above. If none apply, use an empty list.
Do NOT include any other text."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        response = llm_service.chat_completion(messages, temperature=0)
        source_name_map = _build_source_name_map(data_sources)
        raw = (response or "").strip()
        intent = ""
        related_sources = []
        related_source_guids: List[str] = []
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                intent = str(parsed.get("intent", "")).strip().lower()
                related_source_guids = [
                    g for g in (parsed.get("related_source_guids") or []) if g in source_guid_map
                ]
                related_sources = [source_guid_map[g] for g in related_source_guids]
            else:
                parsed = _parse_classification_response(response, source_name_map)
                intent = parsed.get("intent", "").strip().lower()
                related_sources = parsed.get("related_sources", [])
                related_source_guids = [
                    name_to_guid_map[n.lower()] for n in related_sources if n.lower() in name_to_guid_map
                ]

        if intent in VALID_INTENTS:
            logger.info(f"Query classified as '{intent}': {query[:80]}")
            return {
                "intent": intent,
                "related_sources": related_sources,
                "related_source_guids": related_source_guids,
            }

        # LLM returned something unexpected — default to data_query
        logger.warning(f"LLM returned unrecognized intent '{intent}' for: {query[:80]}. Defaulting to data_query.")
        return {"intent": "data_query", "related_sources": [], "related_source_guids": []}

    except Exception as e:
        logger.error(f"Intent classification failed: {e}. Defaulting to data_query.")
        return {"intent": "data_query", "related_sources": [], "related_source_guids": []}


# --- System View Reference (constant) ---
# This gives the LLM a "schema" of SQL Server's internal metadata.
SYSTEM_VIEW_REFERENCE = """
### SQL SERVER SYSTEM CATALOG REFERENCE

#### Core Object Discovery
- **sys.tables** — All user tables: name, object_id, schema_id, create_date, modify_date
- **sys.views** — All views: name, object_id, schema_id, create_date
- **sys.columns** — Columns for any object: name, object_id, column_id, system_type_id, max_length, precision, scale, is_nullable, is_identity
- **sys.schemas** — Schema names: name, schema_id, principal_id
- **sys.indexes** — Indexes: name, object_id, type_desc, is_unique, is_primary_key
- **sys.objects** — All database objects: name, object_id, type, type_desc
- **sys.procedures** — Stored procedures: name, object_id, create_date, modify_date
- **sys.types** — Data types: name, system_type_id, user_type_id, max_length

#### INFORMATION_SCHEMA (ANSI Standard)
- **INFORMATION_SCHEMA.TABLES** — TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
- **INFORMATION_SCHEMA.COLUMNS** — TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, ORDINAL_POSITION
- **INFORMATION_SCHEMA.ROUTINES** — ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_SCHEMA

#### Server-Level Metadata
- **sys.databases** — All databases: name, database_id, create_date, state_desc, recovery_model_desc
- **@@VERSION** — Returns full SQL Server version string
- **SERVERPROPERTY('ProductVersion')** — Numeric version
- **SERVERPROPERTY('Edition')** — Edition (Enterprise, Standard, etc.)

#### Space & Size
- **sp_spaceused** — Table/database space usage (exec sp_spaceused 'TableName')
- **sys.dm_db_partition_stats** — Row counts and page counts per table: SUM(row_count), SUM(used_page_count)

#### Relationships & Keys
- **sys.foreign_keys** — FK name, parent_object_id, referenced_object_id
- **sys.foreign_key_columns** — FK column mappings: parent_column_id, referenced_column_id
- **sys.key_constraints** — PK and unique constraints
""".strip()


def build_system_catalog_prompt(query: str, database_info: Optional[str] = None) -> str:
    """
    Build a specialized LLM prompt for SQL Server system metadata queries.

    Instead of injecting business schemas, this provides the LLM with
    documentation of SQL Server's catalog views and DMVs so it can write
    correct system-level T-SQL.

    Args:
        query: The user's natural language query.
        database_info: Optional database context string (e.g., "Database: SalesDB").

    Returns:
        A complete prompt string to pass to generate_sql_with_context().
    """
    db_section = ""
    if database_info:
        db_section = f"""### DATABASE CONTEXT
{database_info}

"""

    return f"""{db_section}{SYSTEM_VIEW_REFERENCE}

### RULES
1. Only use standard SQL Server (T-SQL) system views and catalog objects listed above.
2. Do NOT query business data tables or user data — this is a metadata-only request.
3. Always qualify system views with their schema (e.g., sys.tables, INFORMATION_SCHEMA.COLUMNS).
4. Return a single, clean T-SQL query. No markdown fences, no explanation — just SQL.
5. Use JOINs between catalog views when needed (e.g., sys.columns JOIN sys.types for data type names).
6. For table/column discovery, prefer INFORMATION_SCHEMA views for portability unless sys.* views provide needed detail.
7. When the user asks about a specific table, use the table name in a WHERE clause (e.g., WHERE TABLE_NAME = 'Orders').
8. For row counts, prefer sys.dm_db_partition_stats with index_id IN (0, 1) over COUNT(*) for performance.

### TARGET REQUEST
{query}
"""
