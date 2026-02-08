# LLM-Based 3-Way Intent Classifier — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the regex-based `detect_system_query_intent()` with an LLM-based 3-way classifier (`data_query` / `system_metadata` / `off_topic`) that runs at the very beginning of `generate_sql_for_request`, before any entity extraction or discovery.

**Architecture:** A new `classify_query_intent()` function in `system_query_service.py` uses `llm_service.chat_completion()` with a focused system prompt to classify user queries into exactly one of three categories. The regex-based detector is removed entirely. The main generation pipeline restructures its early flow: classification happens immediately after LLM service init (before entity extraction), then branches to the appropriate handler. `build_system_catalog_prompt()` and `SYSTEM_VIEW_REFERENCE` remain unchanged.

**Tech Stack:** Python 3.8+, existing `llm_service.chat_completion()`, FastAPI (existing), pytest + unittest.mock for tests.

---

## Task 1: Replace `detect_system_query_intent` with `classify_query_intent`

**Files:**
- Modify: `app/services/system_query_service.py`
- Modify: `tests/test_system_query_service.py`

### Step 1: Write the failing tests for `classify_query_intent`

Replace the contents of `tests/test_system_query_service.py` with:

```python
"""
Tests for query intent classification and system catalog prompt building.
"""

import pytest
from unittest.mock import MagicMock
from app.services.system_query_service import classify_query_intent
from app.services.system_query_service import build_system_catalog_prompt


class TestClassifyQueryIntent:
    """Test suite for LLM-based classify_query_intent function"""

    def _make_llm(self, response_text: str) -> MagicMock:
        """Create a mock LLM service that returns the given text."""
        llm = MagicMock()
        llm.chat_completion.return_value = response_text
        return llm

    # --- system_metadata cases ---

    def test_list_tables(self):
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("list all tables in the database", llm) == "system_metadata"

    def test_show_columns(self):
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("show columns for the Orders table", llm) == "system_metadata"

    def test_sql_version(self):
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("what SQL Server version are we running?", llm) == "system_metadata"

    def test_how_many_tables_have_column(self):
        """The query that originally broke the regex approach"""
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("How many tables have EmployeeID column", llm) == "system_metadata"

    # --- data_query cases ---

    def test_business_sales(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent("show me total sales by region", llm) == "data_query"

    def test_business_customers(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent("how many customers ordered last month?", llm) == "data_query"

    # --- off_topic cases ---

    def test_off_topic_greeting(self):
        llm = self._make_llm("off_topic")
        assert classify_query_intent("What a nice day!", llm) == "off_topic"

    def test_off_topic_general_knowledge(self):
        llm = self._make_llm("off_topic")
        assert classify_query_intent("What is the capital of France?", llm) == "off_topic"

    # --- Robustness: LLM returns unexpected text ---

    def test_strips_whitespace(self):
        llm = self._make_llm("  system_metadata  \n")
        assert classify_query_intent("list tables", llm) == "system_metadata"

    def test_defaults_to_data_query_on_garbage(self):
        """If LLM returns something unrecognized, default to data_query (safest)"""
        llm = self._make_llm("I think this is about tables")
        assert classify_query_intent("list tables", llm) == "data_query"

    def test_empty_query_returns_off_topic(self):
        """Empty or blank queries should be classified as off_topic without calling LLM"""
        llm = self._make_llm("data_query")
        assert classify_query_intent("", llm) == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_none_query_returns_off_topic(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent(None, llm) == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_llm_exception_defaults_to_data_query(self):
        """If LLM call fails, default to data_query to avoid blocking the user"""
        llm = MagicMock()
        llm.chat_completion.side_effect = Exception("API error")
        assert classify_query_intent("list all tables", llm) == "data_query"

    # --- Verify prompt structure ---

    def test_sends_system_and_user_message(self):
        llm = self._make_llm("data_query")
        classify_query_intent("show me sales", llm)
        llm.chat_completion.assert_called_once()
        messages = llm.chat_completion.call_args[0][0] if llm.chat_completion.call_args[0] else llm.chat_completion.call_args[1].get("messages", llm.chat_completion.call_args[0][0])
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "show me sales" in messages[1]["content"]

    def test_system_prompt_mentions_three_categories(self):
        llm = self._make_llm("data_query")
        classify_query_intent("test query", llm)
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        assert "data_query" in system_content
        assert "system_metadata" in system_content
        assert "off_topic" in system_content


class TestBuildSystemCatalogPrompt:
    """Test suite for build_system_catalog_prompt function (unchanged)"""

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
        result = build_system_catalog_prompt("list tables")
        assert "business" in result.lower() or "user data" in result.lower()

    def test_with_database_info(self):
        result = build_system_catalog_prompt("list tables", database_info="Database: SalesDB")
        assert "SalesDB" in result
```

### Step 2: Run test to verify it fails

Run: `pytest tests/test_system_query_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'classify_query_intent'`

### Step 3: Replace the implementation in `system_query_service.py`

Replace the entire contents of `app/services/system_query_service.py` with:

```python
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
        intent = response.strip().lower()

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
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_system_query_service.py -v`
Expected: All tests PASS

### Step 5: Commit

```bash
git add app/services/system_query_service.py tests/test_system_query_service.py
git commit -m "feat: replace regex intent detector with LLM-based 3-way classifier"
```

---

## Task 2: Restructure `generate_sql_for_request` to Use 3-Way Classification

**Files:**
- Modify: `app/services/generation_service.py` (line 17 for import, lines 1510-1578 for restructure)
- Modify: `tests/test_system_query_generation.py`

### Step 1: Write the failing integration tests

Replace the contents of `tests/test_system_query_generation.py` with:

```python
"""
Tests for 3-way intent classification integration in generate_sql_for_request.

Uses mocks to avoid requiring real database/LLM connections.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus


def _make_skills_mock():
    """Create a standard mock for skills_service."""
    mock_skills_instance = MagicMock()
    mock_skills_instance.load_primary_data_source.return_value = MagicMock(
        name="TestDB", description="Test database", keywords=[]
    )
    return mock_skills_instance


class TestIntentClassificationRouting:
    """Test that 3-way classification routes queries correctly"""

    @patch("app.services.generation_service.classify_query_intent", return_value="system_metadata")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_metadata_skips_discovery(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """system_metadata queries bypass discovery and use catalog prompt"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT name FROM sys.tables"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (True, "", [])

        request = GenerateSQLRequest(query="list all tables in the database")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert isinstance(payload, GenerateSQLResponse)
        assert payload.discovery_branch == "system_catalog"
        assert payload.sql == "SELECT name FROM sys.tables"

    @patch("app.services.generation_service.classify_query_intent", return_value="system_metadata")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_metadata_with_retry(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """System metadata queries should retry once on validation failure"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.side_effect = [
            "SELECT name FROM sys.nonexistent",
            "SELECT name FROM sys.tables",
        ]
        mock_llm_factory.return_value = mock_llm

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
        assert mock_llm.generate_sql_with_context.call_count == 2

    @patch("app.services.generation_service.classify_query_intent", return_value="system_metadata")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_metadata_max_retry_exhausted(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """After 2 failed attempts, should return error explanation"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT bad FROM sys.bad"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (False, "Invalid object name 'sys.bad'", ["sys.bad"])

        request = GenerateSQLRequest(query="list all tables")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert payload.sql == ""
        assert "failed" in payload.explanation.lower() or "error" in payload.explanation.lower()

    @patch("app.services.generation_service.classify_query_intent", return_value="off_topic")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_off_topic_returns_general_response(self, mock_skills, mock_vs, mock_llm_factory, mock_classify):
        """off_topic queries should return a general (non-SQL) response"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = "That sounds lovely! How can I help you with the database?"
        mock_llm_factory.return_value = mock_llm

        request = GenerateSQLRequest(query="What a nice day!")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert isinstance(payload, GenerateSQLResponse)
        assert payload.query_type == "general"
        assert payload.sql == ""

    @patch("app.services.generation_service.classify_query_intent", return_value="data_query")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_data_query_continues_to_discovery(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """data_query should proceed past classification into discovery (Stage 2+)"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        request = GenerateSQLRequest(query="show me total sales by region")

        # We just need to verify it gets past classification.
        # It will fail later in discovery (no real vector store), but that's fine —
        # we only care that it did NOT take the system_metadata or off_topic branch.
        results = []
        try:
            for item in generate_sql_for_request(request):
                results.append(item)
        except Exception:
            pass  # Expected — discovery pipeline needs real services

        # Verify classification was called and we got past it
        mock_classify.assert_called_once()

        # Should have yielded status messages about analysis (not system metadata or off-topic)
        statuses = [r for r in results if isinstance(r, AgentStatus)]
        status_messages = [s.message for s in statuses]
        # Should NOT contain system metadata messages
        assert not any("System metadata" in m for m in status_messages)
        assert not any("off-topic" in m.lower() for m in status_messages)

    def test_forceGeneral_still_skips_classification(self):
        """When forceGeneral is set, should skip LLM classification entirely"""
        from app.services.generation_service import generate_sql_for_request

        with patch("app.services.generation_service.get_llm_service") as mock_llm_factory, \
             patch("app.services.generation_service.get_vector_store"), \
             patch("app.services.skills_service.get_skills_service") as mock_skills, \
             patch("app.services.generation_service.classify_query_intent") as mock_classify:

            mock_skills.return_value = _make_skills_mock()

            mock_llm = MagicMock()
            mock_llm.chat_completion.return_value = "General answer here"
            mock_llm_factory.return_value = mock_llm

            request = GenerateSQLRequest(query="What is a LEFT JOIN?", forceGeneral=True)
            results = list(generate_sql_for_request(request))

            # classify_query_intent should NOT have been called
            mock_classify.assert_not_called()

            result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
            assert len(result_items) == 1
            payload = result_items[0]["payload"]
            assert payload.query_type == "general"
```

### Step 2: Run test to verify it fails

Run: `pytest tests/test_system_query_generation.py -v`
Expected: FAIL — `classify_query_intent` is not imported in `generation_service.py` yet, and the pipeline still uses the old `detect_system_query_intent`.

### Step 3: Update the import in `generation_service.py`

Change line 17 from:

```python
from app.services.system_query_service import detect_system_query_intent, build_system_catalog_prompt
```

to:

```python
from app.services.system_query_service import classify_query_intent, build_system_catalog_prompt
```

### Step 4: Restructure the early pipeline in `generate_sql_for_request`

Replace the block from line 1510 through line 1578 (the current Stage 1 analysis + system query branch) with the new 3-way classification flow.

**Current code to replace** (lines 1510-1578):

```python
    # Stage 1: Query Analysis & Intent
    yield AgentStatus(step_id=2, message="Analyzing query and intent...")
    
    # If forceGeneral flag is set (user explicitly chose "General Answer"), skip classification
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # Classification removed: Always assume 'database' query unless forceGeneral is set

    # Extract entities and score complexity for database queries
    entities, date_ranges = extract_entities(request.query)
    query_complexity = score_query_complexity(request.query)
    
    yield AgentStatus(step_id=3, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")

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

**New code:**

```python
    # Stage 1: Intent Classification & Query Analysis
    yield AgentStatus(step_id=2, message="Classifying query intent...")
    
    # If forceGeneral flag is set (user explicitly chose "General Answer"), skip classification
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # 3-way LLM intent classification: data_query / system_metadata / off_topic
    query_intent = classify_query_intent(request.query, llm_service)
    
    yield AgentStatus(step_id=3, message=f"Intent classified as: {query_intent}")

    # --- Off-Topic Branch ---
    if query_intent == "off_topic":
        yield AgentStatus(step_id=4, message="Off-topic query detected. Generating general response...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # --- System Metadata Branch ---
    if query_intent == "system_metadata":
        yield AgentStatus(step_id=4, message="System metadata query detected. Accessing SQL Server catalogs...")

        database_info = f"Database: {friendly_name}\nDescription: {db_description}"
        system_prompt = build_system_catalog_prompt(request.query, database_info=database_info)

        max_system_attempts = 2
        last_error = ""
        for attempt in range(max_system_attempts):
            yield AgentStatus(step_id=10 + attempt, message=f"Generating system catalog SQL (Attempt {attempt + 1}/{max_system_attempts})...")

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

    # --- Data Query Branch (continues to Stage 2: Discovery) ---
    # Extract entities and score complexity for database queries
    entities, date_ranges = extract_entities(request.query)
    query_complexity = score_query_complexity(request.query)
    
    yield AgentStatus(step_id=4, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")
```

Note: The old `step_id=3` for entity analysis becomes `step_id=4` since classification takes `step_id=3`. The subsequent Stage 2 comment on the next line (`# Stage 2: Discovery & Context Synthesis`) stays as-is, and its `step_id=4` for "Discovering relevant tables..." needs to become `step_id=5`.

### Step 5: Update the step_id for Stage 2 discovery

Change the line immediately after our new block (currently `generation_service.py:1580`):

```python
    # Stage 2: Discovery & Context Synthesis (Multi-Source Retrieval)
    yield AgentStatus(step_id=4, message="Discovering relevant tables and schemas...")
```

to:

```python
    # Stage 2: Discovery & Context Synthesis (Multi-Source Retrieval)
    yield AgentStatus(step_id=5, message="Discovering relevant tables and schemas...")
```

### Step 6: Run integration tests

Run: `pytest tests/test_system_query_generation.py -v`
Expected: All tests PASS

### Step 7: Run full test suite

Run: `pytest tests/test_system_query_service.py tests/test_system_query_generation.py -v`
Expected: All tests PASS

### Step 8: Commit

```bash
git add app/services/generation_service.py tests/test_system_query_generation.py
git commit -m "feat: integrate 3-way LLM intent classifier into SQL generation pipeline"
```

---

## Task 3: Update `code_generation_service.py` Import (if needed)

**Files:**
- Check: `app/services/code_generation_service.py`

### Step 1: Check if `code_generation_service.py` imports `detect_system_query_intent`

Run: `grep -n "detect_system_query_intent\|system_query_service" app/services/code_generation_service.py`

If it does NOT import it (likely — the code gen service uses `_handle_general_query` from generation_service, not the system query service directly), this task is done.

If it DOES import it, update the import to `classify_query_intent` and adapt accordingly.

### Step 2: Commit if changes were needed

```bash
git add app/services/code_generation_service.py
git commit -m "fix: update code generation service import for new classifier"
```

---

## Task 4: Clean Up and Final Verification

**Files:**
- All modified files

### Step 1: Verify no remaining references to `detect_system_query_intent`

Run: `grep -rn "detect_system_query_intent" app/ tests/`

Expected: Zero matches. If any remain, update them.

### Step 2: Run the complete test suite

Run: `pytest tests/ -v --timeout=30`

Expected: All tests PASS with no regressions.

### Step 3: Commit cleanup if needed

```bash
git add -A
git commit -m "chore: remove remaining references to deprecated regex intent detector"
```

---

## Summary of All Changes

| File | Action | Description |
|------|--------|-------------|
| `app/services/system_query_service.py` | **Rewrite** | Remove regex patterns + `detect_system_query_intent()`. Add `classify_query_intent()` with LLM-based 3-way classification. Keep `build_system_catalog_prompt()` and `SYSTEM_VIEW_REFERENCE` unchanged. |
| `app/services/generation_service.py` | **Modify** (line 17 import, lines 1510-1580 restructure) | Replace import; restructure early pipeline: classification → off_topic branch → system_metadata branch → data_query continues to discovery. |
| `tests/test_system_query_service.py` | **Rewrite** | New tests for `classify_query_intent` (mock LLM responses, edge cases, error handling, prompt structure). Keep `TestBuildSystemCatalogPrompt` unchanged. |
| `tests/test_system_query_generation.py` | **Rewrite** | New tests for 3-way routing: system_metadata, off_topic, data_query, forceGeneral, retry behavior. |

### Architecture Decision Records

1. **LLM over regex**: Regex cannot handle semantic ambiguity ("how many tables have EmployeeID column" vs "how many customers ordered"). A single LLM call with temperature=0 resolves this reliably.
2. **Safe default = data_query**: On LLM failure or unrecognized output, we default to `data_query` — the full pipeline handles everything, just slower. Never silently drop a query.
3. **Empty/None = off_topic**: Empty strings and None skip the LLM call entirely and return `off_topic` immediately.
4. **Classification before entity extraction**: Moved classification to before `extract_entities()` and `score_query_complexity()` — these are wasted work for system_metadata and off_topic queries.
5. **forceGeneral still respected**: The UI button bypass remains — it skips classification entirely, same as before.
6. **Single LLM call cost**: The classification prompt is ~150 tokens input + 1-2 tokens output. With GPT-4o at $2.50/M input tokens, this costs ~$0.0004 per query. Acceptable tradeoff for accuracy.
