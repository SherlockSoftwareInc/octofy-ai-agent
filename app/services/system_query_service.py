"""
System Query Service - Handles SQL Server system metadata queries.

Provides LLM-based intent classification (data_query / system_metadata / off_topic)
and a specialized prompt builder for system catalog queries.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# The three valid intent categories
VALID_INTENTS = {"data_query", "system_metadata", "off_topic"}

# Classification prompt — kept minimal to reduce latency and token cost.
CLASSIFICATION_SYSTEM_PROMPT = """You are a query intent classifier for a SQL Server database assistant.

Classify the user's message into exactly ONE of these categories:

- **data_query** — The user wants to retrieve, analyze, or aggregate BUSINESS DATA stored in the database (e.g., sales figures, customer counts, revenue trends, employee records).
- **system_metadata** — The user wants information about the DATABASE STRUCTURE or SERVER itself (e.g., list tables, show columns, table row counts, SQL Server version, indexes, schemas, which tables have a certain column).
- **off_topic** — The user's message is NOT related to querying or exploring the database at all (e.g., greetings, general knowledge questions, jokes, SQL syntax explanations).

Reply with EXACTLY one word: data_query, system_metadata, or off_topic
Do NOT include any other text."""


def classify_query_intent(query: str, llm_service) -> str:
    """
    Classify user query intent using the LLM.

    Args:
        query: The user's natural language query.
        llm_service: An LLM service instance with a chat_completion() method.

    Returns:
        One of: "data_query", "system_metadata", "off_topic".
        Defaults to "data_query" on any error (safest fallback — lets the
        existing pipeline handle it).
    """
    if not query or not query.strip():
        return "off_topic"

    try:
        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        response = llm_service.chat_completion(messages, temperature=0)
        intent = (response or "").strip().lower()

        if intent in VALID_INTENTS:
            logger.info(f"Query classified as '{intent}': {query[:80]}")
            return intent

        # LLM returned something unexpected — default to data_query
        logger.warning(f"LLM returned unrecognized intent '{intent}' for: {query[:80]}. Defaulting to data_query.")
        return "data_query"

    except Exception as e:
        logger.error(f"Intent classification failed: {e}. Defaulting to data_query.")
        return "data_query"


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
