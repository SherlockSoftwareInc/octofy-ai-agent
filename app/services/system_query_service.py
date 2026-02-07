"""
System Query Service - Handles SQL Server system metadata queries.

Detects when users ask about database internals (tables, columns, views,
server version, etc.) and generates T-SQL using system catalog views
instead of the business schema discovery pipeline.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate a system metadata query.
# Each pattern is a compiled regex tested against the lowercased query.
# Order does not matter - any match triggers system intent.
SYSTEM_QUERY_PATTERNS = [
    # Table discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\btables?\b'),
    # Column / structure inspection
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bcolumns?\b'),
    re.compile(r'\bcolumn\s*(info|information|details?|metadata)\b'),
    re.compile(r'\btable\s*(structure|definition|schema|layout|design)\b'),
    re.compile(r'\b(describe|definition\s+of)\b.*\btable\b'),
    # View discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bviews?\b'),
    # Schema discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bschemas?\b'),
    # Index inspection
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bindexe?s\b'),
    # Stored procedure discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\b(stored\s+)?procedures?\b'),
    # Database-level metadata
    re.compile(r'\b(list|show|get|find|what|which)\b.*\bdatabases?\b'),
    re.compile(r'\bdatabase\s*(size|info|information|details?|metadata|properties)\b'),
    re.compile(r'\brow\s*counts?\b.*\btables?\b'),
    # Server version
    re.compile(r'\bsql\s*(server)?\s*version\b'),
    re.compile(r'\bserver\s*version\b'),
    re.compile(r'\b(what|which)\s+version\b'),
    # Describe pattern (common DBA shorthand)
    re.compile(r'\bdescribe\b.*\b\w+\b'),
    # "how many tables" pattern
    re.compile(r'\bhow\s+many\s+tables\b'),
]

# Negative patterns - if these match, it is likely a business query even
# if a positive pattern also matched (e.g. "show me sales from the orders table").
BUSINESS_OVERRIDE_PATTERNS = [
    re.compile(r'\b(total|sum|average|avg|count|revenue|sales|profit|cost|amount)\b'),
    re.compile(r'\b(by|per|group\s+by|order\s+by|where|having|between|from\s+\d)\b'),
    re.compile(r'\b(compare|trend|forecast|growth|decline|ratio|percentage)\b'),
    re.compile(r'\b(customers?|employees?|products?|orders?|invoices?|shipments?)\b.*\b(who|how many|total|last|this)\b'),
]


def detect_system_query_intent(query: str) -> bool:
    """
    Detect whether a query is asking about SQL Server system metadata.

    Returns True if the query is about database internals (tables, columns,
    views, version, etc.) rather than business data.

    Args:
        query: The user's natural language query.

    Returns:
        True if system metadata intent is detected, False otherwise.
    """
    if not query or not query.strip():
        return False

    query_lower = query.lower().strip()

    # Check positive patterns
    has_system_signal = any(p.search(query_lower) for p in SYSTEM_QUERY_PATTERNS)
    if not has_system_signal:
        return False

    # Check negative overrides - business context overrules system signals
    has_business_signal = any(p.search(query_lower) for p in BUSINESS_OVERRIDE_PATTERNS)
    if has_business_signal:
        logger.debug(f"System intent suppressed by business signal for: {query[:80]}")
        return False

    logger.info(f"System metadata intent detected for: {query[:80]}")
    return True


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
