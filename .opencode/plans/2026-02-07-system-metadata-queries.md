# SQL Server System Metadata Support - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable the agent to detect system metadata queries (e.g., "list all tables", "show columns for X", "what SQL Server version") and generate T-SQL against system catalog views, bypassing the business schema discovery pipeline entirely.

**Architecture:** A new `system_query_service.py` module provides intent detection (regex) and a specialized prompt builder (system view reference). The main `generate_sql_for_request` function in `generation_service.py` gains an early conditional branch after Stage 1 that delegates to this service, generates SQL via the existing LLM service, validates via `SET NOEXEC ON`, and returns with a single retry on failure. Discovery, value lookup, and schema sufficiency checks are all skipped.

**Tech Stack:** Python 3.8+, regex, FastAPI (existing), OpenAI LLM via existing `llm_service`, SQL Server `SET NOEXEC ON` validation (existing).

---

## Task 1: Create System Query Service Module with Intent Detector

**Files:**
- Create: `app/services/system_query_service.py`
- Test: `tests/test_system_query_service.py`

### Step 1: Write the failing tests for `detect_system_query_intent`

Create `tests/test_system_query_service.py`:

```python
"""
Tests for system query intent detection and prompt building.
"""

import pytest
from app.services.system_query_service import detect_system_query_intent


class TestDetectSystemQueryIntent:
    """Test suite for detect_system_query_intent function"""

    # --- Positive cases: should detect as system query ---

    def test_list_tables(self):
        assert detect_system_query_intent("list all tables in the database") is True

    def test_show_tables(self):
        assert detect_system_query_intent("show me the tables") is True

    def test_what_tables(self):
        assert detect_system_query_intent("what tables are available?") is True

    def test_list_columns(self):
        assert detect_system_query_intent("list the columns in the Orders table") is True

    def test_column_info(self):
        assert detect_system_query_intent("give me column info for Products") is True

    def test_table_structure(self):
        assert detect_system_query_intent("show me the table structure of Customers") is True

    def test_sql_version(self):
        assert detect_system_query_intent("what SQL Server version are we running?") is True

    def test_database_size(self):
        assert detect_system_query_intent("what is the database size?") is True

    def test_list_databases(self):
        assert detect_system_query_intent("list all databases on this server") is True

    def test_show_schemas(self):
        assert detect_system_query_intent("show all schemas in the database") is True

    def test_list_views(self):
        assert detect_system_query_intent("list all views") is True

    def test_show_indexes(self):
        assert detect_system_query_intent("show indexes on the Orders table") is True

    def test_table_row_counts(self):
        assert detect_system_query_intent("show row counts for all tables") is True

    def test_list_stored_procedures(self):
        assert detect_system_query_intent("list stored procedures") is True

    def test_describe_table(self):
        assert detect_system_query_intent("describe the Employees table") is True

    def test_case_insensitive(self):
        assert detect_system_query_intent("LIST ALL TABLES") is True

    # --- Negative cases: should NOT detect as system query ---

    def test_business_query_sales(self):
        assert detect_system_query_intent("show me total sales by region") is False

    def test_business_query_customers(self):
        assert detect_system_query_intent("how many customers ordered last month?") is False

    def test_business_query_join(self):
        assert detect_system_query_intent("compare revenue across product categories") is False

    def test_business_query_with_table_word(self):
        """'table' in a business context should not trigger system intent"""
        assert detect_system_query_intent("show me the sales figures from the quarterly report table") is False

    def test_general_question(self):
        assert detect_system_query_intent("what is a LEFT JOIN?") is False

    def test_empty_query(self):
        assert detect_system_query_intent("") is False
```

### Step 2: Run test to verify it fails

Run: `pytest tests/test_system_query_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.system_query_service'`

### Step 3: Write the `detect_system_query_intent` implementation

Create `app/services/system_query_service.py`:

```python
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
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_system_query_service.py -v`
Expected: All tests PASS

### Step 5: Commit

```bash
git add app/services/system_query_service.py tests/test_system_query_service.py
git commit -m "feat: add system query intent detector for SQL Server metadata queries"
```

---

## Task 2: Add the System Catalog Prompt Builder

**Files:**
- Modify: `app/services/system_query_service.py`
- Modify: `tests/test_system_query_service.py`

### Step 1: Write the failing tests for `build_system_catalog_prompt`

Append to `tests/test_system_query_service.py`:

```python
from app.services.system_query_service import build_system_catalog_prompt


class TestBuildSystemCatalogPrompt:
    """Test suite for build_system_catalog_prompt function"""

    def test_returns_string(self):
        result = build_system_catalog_prompt("list all tables")
        assert isinstance(result, str)

    def test_includes_user_query(self):
        query = "show columns for the Orders table"
        result = build_system_catalog_prompt(query)
        assert query in result

    def test_includes_sys_tables_reference(self):
        result = build_system_catalog_prompt("list tables")
        assert "sys.tables" in result

    def test_includes_sys_columns_reference(self):
        result = build_system_catalog_prompt("list columns")
        assert "sys.columns" in result

    def test_includes_information_schema_reference(self):
        result = build_system_catalog_prompt("list tables")
        assert "INFORMATION_SCHEMA" in result

    def test_includes_version_reference(self):
        result = build_system_catalog_prompt("what version")
        assert "@@VERSION" in result or "SERVERPROPERTY" in result

    def test_includes_tsql_rules(self):
        result = build_system_catalog_prompt("list tables")
        assert "T-SQL" in result

    def test_includes_no_business_data_rule(self):
        """Prompt should instruct LLM to avoid business schemas"""
        result = build_system_catalog_prompt("list tables")
        assert "business" in result.lower() or "user data" in result.lower()

    def test_with_database_info(self):
        result = build_system_catalog_prompt("list tables", database_info="Database: SalesDB")
        assert "SalesDB" in result
```

### Step 2: Run test to verify it fails

Run: `pytest tests/test_system_query_service.py::TestBuildSystemCatalogPrompt -v`
Expected: FAIL with `ImportError: cannot import name 'build_system_catalog_prompt'`

### Step 3: Implement `build_system_catalog_prompt`

Add to `app/services/system_query_service.py` (after `detect_system_query_intent`):

```python
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
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_system_query_service.py -v`
Expected: All tests PASS

### Step 5: Commit

```bash
git add app/services/system_query_service.py tests/test_system_query_service.py
git commit -m "feat: add system catalog prompt builder with T-SQL view reference"
```

---

## Task 3: Integrate System Query Branch into `generate_sql_for_request`

**Files:**
- Modify: `app/services/generation_service.py` (lines ~1-16 for imports, lines ~1526-1528 for branch insertion)
- Test: `tests/test_system_query_generation.py`

### Step 1: Write the failing integration tests

Create `tests/test_system_query_generation.py`:

```python
"""
Tests for system query branch integration in generate_sql_for_request.

Uses mocks to avoid requiring real database/LLM connections.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus


class TestSystemQueryBranch:
    """Test that system queries take the fast path through generate_sql_for_request"""

    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.generation_service.get_skills_service")
    def test_system_query_skips_discovery(self, mock_skills, mock_vs, mock_llm_factory, mock_validate):
        """System queries should NOT call perform_discovery or lookup_values_for_query"""
        from app.services.generation_service import generate_sql_for_request

        # Setup mocks
        mock_skills_instance = MagicMock()
        mock_skills_instance.load_primary_data_source.return_value = MagicMock(
            name="TestDB", description="Test", keywords=[]
        )
        mock_skills.return_value = mock_skills_instance

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT name FROM sys.tables"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (True, "", [])

        request = GenerateSQLRequest(query="list all tables in the database")

        # Consume the generator
        results = list(generate_sql_for_request(request))

        # Should have status messages and a result
        statuses = [r for r in results if isinstance(r, AgentStatus)]
        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]

        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert isinstance(payload, GenerateSQLResponse)
        assert payload.discovery_branch == "system_catalog"
        assert payload.sql == "SELECT name FROM sys.tables"

    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.generation_service.get_skills_service")
    def test_system_query_with_retry(self, mock_skills, mock_vs, mock_llm_factory, mock_validate):
        """System queries should retry once on validation failure"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills_instance = MagicMock()
        mock_skills_instance.load_primary_data_source.return_value = MagicMock(
            name="TestDB", description="Test", keywords=[]
        )
        mock_skills.return_value = mock_skills_instance

        mock_llm = MagicMock()
        # First call returns bad SQL, second returns good SQL
        mock_llm.generate_sql_with_context.side_effect = [
            "SELECT name FROM sys.nonexistent",
            "SELECT name FROM sys.tables",
        ]
        mock_llm_factory.return_value = mock_llm

        # First validation fails, second succeeds
        mock_validate.side_effect = [
            (False, "Invalid object name 'sys.nonexistent'", ["sys.nonexistent"]),
            (True, "", []),
        ]

        request = GenerateSQLRequest(query="list all tables")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert payload.sql == "SELECT name FROM sys.tables"
        # LLM should have been called exactly 2 times
        assert mock_llm.generate_sql_with_context.call_count == 2

    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.generation_service.get_skills_service")
    def test_system_query_max_retry_exhausted(self, mock_skills, mock_vs, mock_llm_factory, mock_validate):
        """After 2 failed attempts, should return error"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills_instance = MagicMock()
        mock_skills_instance.load_primary_data_source.return_value = MagicMock(
            name="TestDB", description="Test", keywords=[]
        )
        mock_skills.return_value = mock_skills_instance

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT bad FROM sys.bad"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (False, "Invalid object name 'sys.bad'", ["sys.bad"])

        request = GenerateSQLRequest(query="list all tables")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert payload.sql == ""  # Failed — no SQL
        assert "failed" in payload.explanation.lower() or "error" in payload.explanation.lower()

    def test_business_query_does_not_trigger_system_branch(self):
        """Ensure business queries are NOT routed to the system branch"""
        from app.services.system_query_service import detect_system_query_intent

        assert detect_system_query_intent("show me total sales by region") is False
        assert detect_system_query_intent("how many customers ordered last month?") is False
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_system_query_generation.py -v`
Expected: FAIL — the system query branch does not exist yet in `generate_sql_for_request`.

### Step 3: Integrate the system query branch into `generate_sql_for_request`

**Modify `app/services/generation_service.py`:**

**A. Add import** (near top of file, after existing imports around line 16):

```python
from app.services.system_query_service import detect_system_query_intent, build_system_catalog_prompt
```

**B. Insert the system query branch** after line 1526 (the `AgentStatus(step_id=3, ...)` yield about query complexity/entities), **before** line 1528 (the `# Stage 2: Discovery` comment).

The exact insertion point is between these existing lines:

```python
    yield AgentStatus(step_id=3, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")
    
    # >>> INSERT NEW SYSTEM QUERY BLOCK HERE <<<

    # Stage 2: Discovery & Context Synthesis (Multi-Source Retrieval)
```

Insert this block:

```python
    # --- System Metadata Query Fast Path ---
    # Bypass discovery entirely for queries about database internals.
    if detect_system_query_intent(request.query):
        yield AgentStatus(step_id=4, message="System metadata intent detected. Accessing SQL Server catalogs...")

        # Build database info string (same as used later in the normal path)
        database_info = f"Database: {friendly_name}\nDescription: {db_description}"

        system_prompt = build_system_catalog_prompt(request.query, database_info=database_info)

        max_system_attempts = 2
        last_error = ""
        for attempt in range(max_system_attempts):
            yield AgentStatus(step_id=10 + attempt, message=f"Generating system catalog SQL (Attempt {attempt + 1}/{max_system_attempts})...")

            # On retry, append error feedback to prompt
            retry_prompt = system_prompt
            if attempt > 0 and last_error:
                retry_prompt += f"\n\n### PREVIOUS ATTEMPT FAILED\nError: {last_error}\nPlease fix the query and try again."

            sql = llm_service.generate_sql_with_context(request.query, retry_prompt)

            is_valid, error_msg, _ = validate_sql_with_db(sql)

            if is_valid:
                result = GenerateSQLResponse(
                    sql=sql,
                    explanation="System metadata query generated from SQL Server catalog views.",
                    query_type="database",
                    context_text=retry_prompt,
                    discovery_branch="system_catalog"
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return

            last_error = error_msg
            logging.warning(f"System catalog SQL attempt {attempt + 1} failed: {error_msg}")

        # Exhausted retries
        result = GenerateSQLResponse(
            sql="",
            explanation=f"Failed to generate a valid system metadata query after {max_system_attempts} attempts. Last error: {last_error}",
            query_type="database",
            context_text=system_prompt,
            discovery_branch="system_catalog"
        )
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

```

### Step 4: Run integration tests

Run: `pytest tests/test_system_query_generation.py -v`
Expected: All tests PASS

### Step 5: Run existing test suite to ensure no regressions

Run: `pytest tests/ -v --timeout=30`
Expected: All existing tests still PASS

### Step 6: Commit

```bash
git add app/services/generation_service.py app/services/system_query_service.py tests/test_system_query_generation.py
git commit -m "feat: integrate system metadata query branch into SQL generation pipeline"
```

---

## Task 4: Add Edge Case Tests and Polish

**Files:**
- Modify: `tests/test_system_query_service.py`

### Step 1: Add edge case tests to the test file

Append additional test class to `tests/test_system_query_service.py`:

```python
class TestDetectSystemQueryIntentEdgeCases:
    """Edge cases and boundary conditions for system intent detection"""

    def test_mixed_case_keywords(self):
        assert detect_system_query_intent("List All Tables") is True

    def test_extra_whitespace(self):
        assert detect_system_query_intent("  list   tables  ") is True

    def test_conversational_phrasing(self):
        assert detect_system_query_intent("can you show me what tables exist?") is True

    def test_specific_table_columns(self):
        assert detect_system_query_intent("what are the columns in dbo.Orders?") is True

    def test_version_question(self):
        assert detect_system_query_intent("what version of SQL Server is this?") is True

    def test_ambiguous_but_system(self):
        """'describe table' is a system operation even without specifying 'system'"""
        assert detect_system_query_intent("describe the Employees table") is True

    def test_business_with_table_mention(self):
        """Business queries mentioning tables should not trigger system path"""
        assert detect_system_query_intent("show me total revenue from the sales table") is False

    def test_business_aggregation(self):
        assert detect_system_query_intent("list the top 10 customers by revenue") is False

    def test_system_query_with_count_tables(self):
        """Asking how many tables exist is a system query"""
        assert detect_system_query_intent("how many tables are in the database?") is True

    def test_none_input(self):
        """Should handle None gracefully"""
        with pytest.raises((TypeError, AttributeError)):
            detect_system_query_intent(None)
```

### Step 2: Run full test suite

Run: `pytest tests/test_system_query_service.py tests/test_system_query_generation.py -v`
Expected: All tests PASS. If any new edge cases fail, adjust the regex patterns in `system_query_service.py` accordingly.

### Step 3: Commit

```bash
git add tests/test_system_query_service.py app/services/system_query_service.py
git commit -m "test: add edge case coverage for system query intent detection"
```

---

## Summary of All Changes

| File | Action | Description |
|------|--------|-------------|
| `app/services/system_query_service.py` | **Create** | New module: `detect_system_query_intent()`, `build_system_catalog_prompt()`, `SYSTEM_VIEW_REFERENCE` constant |
| `app/services/generation_service.py` | **Modify** (~line 16 for import, ~lines 1526-1528 for branch insertion) | Add import + insert system query branch after Stage 1, before Stage 2 |
| `tests/test_system_query_service.py` | **Create** | Unit tests for intent detection (positive/negative/edge) + prompt builder |
| `tests/test_system_query_generation.py` | **Create** | Integration tests for the full branch (success, retry, exhaustion, non-trigger) |

### Architecture Decision Records

1. **Separate module** (`system_query_service.py`): Keeps `generation_service.py` from growing further (already 2445 lines). Clean separation of concerns.
2. **Regex + negative override**: The dual-pattern approach (positive system signals + negative business overrides) minimizes false positives on ambiguous queries like "show me sales from the orders table."
3. **DB validation kept**: System catalog SQL is still validated via `SET NOEXEC ON` to catch typos and confirm the connection works.
4. **Single retry (max 2)**: System queries are simple and well-documented — one retry with error feedback is sufficient.
5. **discovery_branch = "system_catalog"**: Allows frontend and logging to distinguish this code path from `kb_direct`, `kb_gap_fill`, and `dual_prong`.
