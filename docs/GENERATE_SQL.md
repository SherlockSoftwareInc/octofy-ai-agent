# SQL Generation & Execution Process

## Overview

This document provides a comprehensive guide to the **SQL Generation and Execution Pipeline** in Octofy AI Agent. The system converts natural language queries into validated, executed T-SQL queries using a sophisticated 4-stage process with RAG-based discovery, iterative validation, automatic retry, and AI-powered data analysis.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Stage 1: Query Analysis & Intent](#stage-1-query-analysis--intent)
3. [Stage 2: Discovery & Context Synthesis](#stage-2-discovery--context-synthesis)
4. [Stage 3: Iterative SQL Generation & Validation](#stage-3-iterative-sql-generation--validation)
5. [Stage 4: SQL Execution & Analysis](#stage-4-sql-execution--analysis)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [Key Services Reference](#key-services-reference)
8. [API Endpoints](#api-endpoints)
9. [Configuration Options](#configuration-options)
10. [Common Error Scenarios](#common-error-scenarios)
11. [Performance Considerations](#performance-considerations)
12. [Security & Best Practices](#security--best-practices)

---

## Architecture Overview

The SQL pipeline consists of two main workflows:

### **Generation Workflow** (`/api/v1/generate-sql`)
Natural language → Validated T-SQL query (not executed)

### **Execution Workflow** (`/api/v1/execute-sql`)
Validated T-SQL → Executed results → Profiling → Insights → Chart recommendations

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Natural Language Query                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: Query Analysis & Intent                                │
│ - Plan mode → planning_conversation() (no SQL)                  │
│ - Search mode → search_data_objects() (no SQL)                  │
│ - forceGeneral → off-topic LLM response                         │
│ - 3-way intent: data_query / system_metadata / off_topic        │
│ - Multi-source resolution (primary + data sources via Skills)   │
│ - Entity extraction & complexity scoring (simple/moderate/complex)│
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: Knowledge-Base-First Discovery (Sequential)            │
│                                                                  │
│  Table override? ──YES──► hydrate_override_context() ──────┐   │
│       │ NO                                                  │   │
│       ▼                                                     │   │
│  KB Search (score_threshold=0.5, top_k=3)                  │   │
│       │                                                     │   │
│  KB results? ──YES──► LLM evaluate_example_relevance()     │   │
│       │                     │                              │   │
│       │           confidence≥0.7                           │   │
│       │           & sufficient?                            │   │
│       │            │YES          │NO                       │   │
│       │            ▼             ▼                         │   │
│       │      kb_direct      kb_gap_fill                    │   │
│       │  (skip steps 8-10)  (skip steps 8-9,              │   │
│       │                      run step 10 only)             │   │
│       │ NO                                                  │   │
│       ▼                                                     │   │
│  dual_prong: Value Index + Few-Shot + Schema Index         │   │
│  → rerank_and_select_tables()                              │   │
│  → expand_context_with_neighbors() (path finding)         │   │
│  → Steps 8-10 (completeness + value lookup + sufficiency) │   │
│                                                             │   │
│  Step 10: validate_schema_with_join_paths() or            │   │
│           check_schema_sufficiency()                       │   │
│           (ENABLE_JOIN_PATH_VALIDATION flag)               │   │
└──────────┬──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 3: Iterative SQL Generation & Validation (max 5 attempts)│
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │  1. Build Context Prompt                         │          │
│  │     - Database info                              │          │
│  │     - Query analysis                             │          │
│  │     - Knowledge base examples                    │          │
│  │     - Value mappings                             │          │
│  │     - Schema descriptions                        │          │
│  │     - Attempt history                            │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  2. LLM Generates SQL (temperature=0)           │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  3. Validate with Database (SET NOEXEC ON)      │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│         ┌──────────┴──────────┐                                 │
│         │ Valid?              │                                 │
│         └──┬──────────────┬───┘                                 │
│            │ YES          │ NO                                  │
│            │              │                                     │
│            │              ▼                                     │
│            │    ┌─────────────────────────┐                    │
│            │    │ Intelligent Recovery:   │                    │
│            │    │ - Missing object search │                    │
│            │    │ - Ambiguity fixing      │                    │
│            │    │ - Type mismatch CAST()  │                    │
│            │    └────────┬────────────────┘                    │
│            │             │                                     │
│            │             └──────┐ Retry (attempts 2-5)         │
│            │                    │                              │
│            ▼                    ▼                              │
│     Return Valid SQL     Max Attempts? → Return Error         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 4: SQL Execution & Analysis (NEW!)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │  POST /api/v1/execute-sql                        │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Execute SQL with Retry Loop (max 5 attempts)   │          │
│  │                                                  │          │
│  │  For each attempt:                               │          │
│  │    1. Execute SQL with timeout & row limit       │          │
│  │    2. If error: regenerate_sql_with_error_feedback()│      │
│  │    3. Retry execution with fixed SQL             │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Data Profiling (ProfilingService)               │          │
│  │  - Row/column counts, data types                 │          │
│  │  - Distribution analysis                         │          │
│  │  - Correlation analysis                          │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Insight Generation (InsightService)             │          │
│  │  - Outlier detection                             │          │
│  │  - Trend identification                          │          │
│  │  - Missing data patterns                         │          │
│  │  - AI-powered recommendations                    │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Chart Recommendation (VisualizationService)     │          │
│  │  - Optimal chart type selection                  │          │
│  │  - Axis configuration                            │          │
│  └─────────────────┬────────────────────────────────┘          │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Return ExecuteSQLResponse                       │          │
│  │  - Structured results                            │          │
│  │  - Data profile                                  │          │
│  │  - Insights                                      │          │
│  │  - Chart recommendation                          │          │
│  │  - Auto-fix metadata (if retry occurred)        │          │
│  └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Query Analysis & Intent

**Purpose**: Understand what the user wants before searching for relevant data.

### Process Flow

```python
# File: app/services/generation_service.py
# Function: generate_sql_for_request() - Lines 1756+
```

### Steps

#### 1.1 Conversation Context Injection

At the very start, conversation history is merged into the query so all branches have full context:

```python
combined_query = request.query
if query_history:
    combined_query = f"{query_history}. {request.query}"
```

#### 1.2 Load Data Source Settings

Database metadata is now loaded from the **Skills service** (not from a static `settings.json`):

```python
from app.services.skills_service import get_skills_service
skills_service = get_skills_service()
data_sources = skills_service.load_data_sources_index() or []
primary_source = skills_service.load_primary_data_source()

friendly_name = primary_source.name        # e.g. "Northwind"
db_description = primary_source.description
db_keywords = primary_source.keywords
```

If no Skills data sources are configured:
```python
friendly_name = "Database"
db_description = "Primary database"
db_keywords = []
```

#### 1.3 Handle Special Modes (Pre-Classification)

These modes short-circuit before any intent classification:

**Plan Mode** (`queryMode="plan"`):
- Calls `planning_conversation(combined_query, request.planning_context, user_selected_tables=...)`
- Returns a conversational planning response — no SQL generated

**Search Mode** (`queryMode="search"`):
- Calls `search_data_objects(combined_query)`
- Returns database objects for schema exploration — no SQL generated

**Force General** (`forceGeneral=True`):
- User explicitly chose "General Answer"
- Calls `_handle_general_query()` — bypasses all classification

#### 1.4 Editor Mode Detection

```python
existing_code = request.existing_code or request.previousSQL
editor_mode = "debug"    if request.error_message else \
              "optimize" if existing_code else \
              "fresh"
```

- `debug` — an error message is attached; LLM is asked to diagnose and fix
- `optimize` — existing code is attached; LLM is asked to extend or improve
- `fresh` — standard generation from scratch

#### 1.5 Intent Classification (3-Way)

```python
classification = classify_query_intent(
    combined_query, llm_service,
    db_name=friendly_name,
    db_description=db_description,
    db_keywords=db_keywords,
    data_sources=data_sources,
)
query_intent = classification.get("intent")         # data_query / system_metadata / off_topic
related_sources = classification.get("related_sources", [])
related_source_guids = classification.get("related_source_guids", [])
```

| Intent | Description | Action |
|--------|-------------|--------|
| `data_query` | Query against business data tables | Proceeds to Stage 2 Discovery |
| `system_metadata` | Query about DB structure (tables, columns, counts) | Uses `build_system_catalog_prompt()` with SQL Server catalog views |
| `off_topic` | Unrelated to any registered data source | Returns conversational LLM response |

**Multi-Source Disambiguation**: If `related_source_guids` has more than one match, the agent returns a prompt asking the user to pick one source GUID before proceeding. No SQL is generated until a single source is selected.

**System Metadata Branch** (2 retry attempts):
```python
for attempt in range(2):
    sql = llm_service.generate_sql_with_context(combined_query, system_prompt)
    is_valid, error_msg, _ = validate_sql_with_db(sql, source_id=selected_source_id)
    if is_valid:
        return GenerateSQLResponse(sql=sql, discovery_branch="system_catalog", ...)
```

#### 1.6 Extract Entities & Score Complexity (data_query only)

```python
entities, date_ranges = extract_entities(discovery_query)
query_complexity = score_query_complexity(discovery_query)
```

Classification rules:
- **Simple**: Single table, basic filtering (`SELECT * FROM Products WHERE Price > 100`)
- **Moderate**: 2-3 tables, simple joins (`SELECT c.Name, COUNT(o.OrderID) FROM Customers c JOIN Orders o...`)
- **Complex**: 4+ tables, CTEs, subqueries, multi-step aggregations

**Complexity affects**:
- Prompt scripting authorization (see Stage 3)
- Number of knowledge base examples included
- Whether `DECLARE` / `#TempTable` patterns are suggested

---

## Stage 2: Discovery & Context Synthesis

**Purpose**: Find the most relevant tables and example queries for the user's query. The strategy is **Knowledge-Base-First** (sequential and conditional), not a flat parallel search.

### Context Inputs (All Branches)

```python
allowed_tables = _get_allowed_table_set(vector_store, selected_source_id)  # source-scoped filter
db_object_tables, db_object_unresolved = _resolve_database_objects_to_tables(
    request.database_objects, vector_store, selected_source_id, allowed_tables=allowed_tables
)
```

### Branch A: Table Override (user-pinned tables)

If `request.table_override` is non-empty, all discovery is **skipped entirely**:
```python
context = hydrate_override_context(table_override, source_id=selected_source_id)
# value_mappings = {} (no value lookup), Steps 8/9/10 also skipped
```

### Branch B: Explicit Context

If `request.context` is provided directly (API callers), it is used as-is — discovery is skipped.

### Branch C: Knowledge-Base-First Discovery (default)

#### Step 1 — KB Priority Search

```python
kb_results = vector_store.search_fewshots_with_threshold(
    discovery_query, top_k=3, knowledge_type="sql_query", score_threshold=0.5
)
```

The L2 distance threshold of `0.5` filters out low-quality matches before LLM evaluation.

---

#### Branch 1.1 — KB Hit: LLM Evaluates Relevance

```python
kb_assessment = llm_service.evaluate_example_relevance(discovery_query, kb_results)
is_sufficient = kb_assessment.get("is_sufficient", False)
confidence = kb_assessment.get("confidence", 0.0)
```

##### Branch 1.1.1 `kb_direct` — High Confidence (confidence ≥ 0.7 and sufficient)

**What happens**:
1. Extract tables from the best KB example's SQL: `llm_service.extract_tables_from_sql([best_sql])`
2. Hydrate context using only those tables via `_hydrate_discovery_context_scoped()`
3. `value_mappings = {}` (value lookup is skipped)
4. **Steps 8, 9, 10 are all skipped** — generation proceeds immediately

KB-informed adjustments (if any) are injected into the prompt:
```python
adjustments = kb_assessment.get("adjustments_needed", [])
# → Added to prompt as "### KB-INFORMED ADJUSTMENTS"
```

##### Branch 1.1.2 `kb_gap_fill` — Low Confidence (confidence < 0.7 or not sufficient)

**What happens**:
1. Start from tables extracted from KB examples
2. Use `kb_assessment["missing_entities"]`, `["missing_tables"]`, `["suggested_search_terms"]` as gap keywords
3. For each gap keyword (up to 5): search `schema_index` + `value_index`
4. Expand value hits with FK relationships: `expand_value_tables_with_relationships()`
5. Combine and source-filter all tables, then hydrate context
6. `value_mappings = {}` (value lookup is skipped)
7. **Steps 8, 9 are skipped; Step 10 runs**

---

#### Branch 1.2 `dual_prong` — No KB Hit

Fallback when no KB results pass the `score_threshold=0.5` threshold.

**Step 1 — NER & Value Discovery**:
```python
filter_values = llm_service.extract_filter_values(discovery_query)
# For each filter value: search value_index
# Expand results with FK relationship tracing
value_tables = expand_value_tables_with_relationships(value_tables)
```

**Step 2 — Few-Shot Discovery** (broader, no threshold):
```python
similar_queries = vector_store.search_fewshots(discovery_query, top_k=3, knowledge_type="sql_query")
few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
```

**Step 3 — Schema Index Discovery**:
```python
schema_results = _search_schemas_scoped(vector_store, discovery_query, top_k=5, source_id=selected_source_id)
schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
```

**Step 4 — Re-Rank & Select**:
```python
final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
```

| Source | Weight |
|--------|--------|
| Value Index | 10 |
| Few-Shot | 5 |
| Schema Index | 2 |

Example:
```
Value Index:  ['dbo.Customers', 'dbo.Orders']     → +10 each
Few-Shot:     ['dbo.Orders', 'dbo.Products']       → +5 each
Schema Index: ['dbo.Orders', 'dbo.Employees']      → +2 each

Scores: Orders=17, Customers=10, Products=5, Employees=2
Selected (top 8): ['Orders', 'Customers', 'Products', 'Employees']
```

**Step 5 — Hydrate Context** + **Step 6 — Path Finding**:
```python
context = _hydrate_discovery_context_scoped(final_table_list, similar_queries, selected_source_id)
expanded_list = expand_context_with_neighbors(final_table_list, discovery_query, selected_source_id)
# LLM identifies "glue tables" — e.g. ['Customers', 'Products'] → adds ['Orders', 'OrderDetails']
```

**Steps 7–10: Full Validation Pipeline runs** (see table below).

---

### Validation Steps (Branch-Dependent)

| Step | `kb_direct` | `kb_gap_fill` | `dual_prong` |
|------|:-----------:|:-------------:|:------------:|
| **Step 8**: Schema completeness (`validate_schema_completeness`) | Skip | Skip | Run |
| **Step 9**: Value index lookup (`lookup_values_for_query`) | Skip | Skip | Run |
| **Step 10**: Schema sufficiency check | Skip | Run | Run |

#### Step 8 — Schema Completeness Validation

Checks FK dependencies. On failure, auto-discovers missing tables via `perform_discovery()`. If a table still can't be found, the pipeline returns a user-facing error with next steps (e.g., sync the schema).

#### Step 9 — Value Index Lookup

```python
value_mappings = lookup_values_for_query(combined_query, allowed_tables=allowed_tables)
# Injected into prompt as:
# ### VERIFIED DATA MAPPINGS
# - The value(s) 'Canada', 'USA' was found in: [dbo].[Customers].[Country]
```

#### Step 10 — Schema Sufficiency Pre-Flight Check

Controlled by `ENABLE_JOIN_PATH_VALIDATION` config flag (default: `True`):

```python
if use_join_path:
    sufficiency_result = llm_service.validate_schema_with_join_paths(
        user_query=discovery_query, schemas=context.relevant_tables, code_type="sql"
    )  # Checks data existence AND that a valid join path exists between tables
else:
    sufficiency_result = llm_service.check_schema_sufficiency(
        user_query=discovery_query, schemas=context.relevant_tables, code_type="sql"
    )  # Checks data existence only
```

If `status == "insufficient_data"` or `"insufficient_joins"`:
1. `expand_context_for_missing_data()` is called with `search_suggestions` (up to 5)
2. Step 10 re-runs once with the expanded context
3. If still insufficient, the pipeline returns a structured error listing missing data points and any join path issues

If Step 10 succeeds, a `validated_mapping_section` is extracted from `validation_details` and injected directly into the generation prompt as `### VALIDATED MAPPING (use these exact tables/columns)`.

---

## Stage 3: Iterative SQL Generation & Validation

**Purpose**: Generate and validate SQL, with automatic error recovery (max 5 attempts).

### 3.1 Retry Loop (Max 5 Attempts)

```python
# File: app/services/generation_service.py (Lines 2730+)

for attempt in range(5):
    # 1. Build context prompt (rebuilt each attempt with updated schema + attempt history)
    current_prompt = build_prompt(...)

    # 2. LLM generates SQL
    sql = llm_service.generate_sql_with_context(combined_query, current_prompt)

    # 3. Check for special validation errors (TABLE_VALIDATION_ERROR / COLUMN_VALIDATION_ERROR)
    is_special_error, error_text, special_missing = parse_validation_error(sql)

    # 4. Validate with database (SET NOEXEC ON)
    if not is_special_error:
        is_valid, error_msg, missing_cols = validate_sql_with_db(sql, source_id=selected_source_id)

    if is_valid:
        yield GenerateSQLResponse(sql=sql, discovery_branch=..., ...)
        return

    # 5. Intelligent recovery + append to current_context_history
    ...
```

### 3.2 Context Prompt Construction

The prompt is rebuilt **each attempt** and includes the following sections:

```
{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {entities}
Date Ranges: {date_ranges}

### KNOWLEDGE BASE EXAMPLES
{reference_text}          ← KB examples matched to same complexity level (top 3)
{value_context}           ← ### VERIFIED DATA MAPPINGS (from value index, top 5 columns)

{db_objects_context}      ← Only if request.database_objects provided
{editor_context}          ← Only if editor_mode="debug" or "optimize"
{context_guard}           ← Only if table_override active
{validated_mapping_section} ← Only if Step 10 found validated column mappings

### AVAILABLE SCHEMAS (table names and column lists — use only these)
{schema_text}

### REASONING PROCESS
1. Decomposition  2. Variable Mapping  3. Drafting  4. Joins & Bridges  5. Final Selection

### VIEW HANDLING
(prefer base tables over view variants)

{scripting_instruction}   ← Varies by complexity (see below)

### ATTEMPT HISTORY
First attempt.  (or previous failures on retries)

## CRITICAL SQL RULES (1–8)
...

Target Request: {combined_query}
```

#### Knowledge Base Examples (complexity-matched)

KB examples are filtered to prefer those whose complexity matches the current query:
```python
for sq in context.similar_queries:
    sq_complexity = score_query_complexity(sq.get("question", ""))
    if sq_complexity == query_complexity or not complexity_relevant_queries:
        complexity_relevant_queries.append(sq)
```

If `discovery_branch == "kb_direct"`, KB-informed adjustments are appended:
```
### KB-INFORMED ADJUSTMENTS
- Change date filter from 2023 to 2024
- Add GROUP BY ProductCategory
Use the reference SQL as your starting point and apply these adjustments.
```

#### Scripting Authorization (complexity-dependent)

| Complexity | Scripting Instruction Added |
|---|---|
| `complex` | Full T-SQL scripting enabled: `SET NOCOUNT ON`, `DECLARE @vars`, `#TempTables`, `DROP TABLE IF EXISTS` |
| `moderate` | CTEs or `DECLARE` acceptable if they improve clarity |
| `simple` | None (single-query expected) |

#### Editor Mode Context

```python
if editor_mode == "debug":
    editor_context = "### EDITOR MODE\nAn error is attached; identify the root cause and provide a corrected version.\n"
    editor_context += f"### ERROR\n{request.error_message}\n"
    editor_context += f"### EXISTING CODE\n{existing_code}\n"
elif editor_mode == "optimize":
    editor_context = "### EDITOR MODE\nNo error attached; optimize or extend the logic based on the user request.\n"
    editor_context += f"### EXISTING CODE\n{existing_code}\n"
```

If `request.is_user_code` is set, a note is added: *"Code was manually written by the user. Preserve their style and intent."*

### 3.3 SQL Generation (LLM)

```python
sql = llm_service.generate_sql_with_context(combined_query, current_prompt)
```

**LLM Configuration**:
- Model: Configurable via `agent_settings` (default `gpt-4o` or `LLM_MODEL` env var)
- Temperature: `0.0` — deterministic, no creativity
- Output: Raw T-SQL wrapped in a `/* explanation */` comment block, then the SQL script

### 3.4 Dual Validation

```python
# Phase 1: Parse special LLM-generated validation errors
is_special_error, error_text, special_missing = parse_validation_error(sql)
# Catches: TABLE_VALIDATION_ERROR: Cannot find table [X]
#          COLUMN_VALIDATION_ERROR: Cannot find column [X]

# Phase 2: Database parse-check (only if not a special error)
is_valid, error_msg, missing_cols = validate_sql_with_db(sql, source_id=selected_source_id)
# Uses SET NOEXEC ON — parses without executing, no data modified
```

### 3.5 Intelligent Recovery Strategies

#### Recovery 1: Special Validation Error (LLM self-reported)

**Error**: `TABLE_VALIDATION_ERROR: Cannot find table [ProductCategories]`

**Strategy**:
```python
for missing_obj in missing_cols:
    disc_res = perform_discovery(DiscoveryRequest(query=missing_obj, top_k=5, source_id=...))
    # Add newly discovered tables to context
    # Also do a broader search: f"{request.query} {missing_obj}"

if no new tables found:
    return error asking user for more information (stops retrying)
```

#### Recovery 2: Database Validation Error with Missing Objects

**Error**: `Invalid object name 'dbo.ProductCategories'`

Same discovery-then-retry strategy as above. Broader search is performed to find related tables.

#### Recovery 3: Ambiguous Column Fix

**Error**: `Ambiguous column name 'Name'`

```python
recovery_instruction = f"Self-Correction: {error_msg}\n" \
    "Re-examine the join logic and ensure all columns are properly qualified with table aliases."
```

#### Recovery 4: Type Mismatch Correction

**Error**: `Conversion failed when converting varchar to int`

```python
recovery_instruction = f"Type Mismatch: {error_msg}\n" \
    "Ensure data types match in comparisons. Use CAST() when necessary."
```

#### Attempt History Injection

Each failed attempt is recorded and appended to the next prompt:
```
### PREVIOUS ATTEMPTS (Learn from these errors)
Attempt 1:
User Request: ...
Failed Script:
<generated SQL>

Error Message:
<SQL Server error>

Recovery Strategy:
<recovery_instruction>
```

The full failed script is included (not just the error) so the LLM can see variable/temp table context from prior attempts.

### 3.6 Final Output

On success:
```python
GenerateSQLResponse(
    sql=sql,
    explanation="The following code might be able to retrieve the data you requested.",
    query_type="database",
    context_text=current_prompt,
    context_history=current_context_history,
    discovery_branch=discovery_branch,  # "kb_direct" / "kb_gap_fill" / "dual_prong" / "table_override" / "system_catalog"
    source_id=selected_source_id
)
```

After 5 failed attempts:
```python
GenerateSQLResponse(
    sql="",
    explanation=f"Failed after 5 attempts. Final error: {error_msg}. Please try rephrasing your query.",
    ...
)
```

**Error**: `Ambiguous column name 'Name'`

**Strategy**:
```python
add_to_prompt("""
Error: Ambiguous column 'Name'
Fix: Add table aliases:
  - Customers.Name
  - Products.Name
  - Employees.Name
Use aliases consistently: SELECT c.Name, p.Name FROM Customers c JOIN Products p...
""")
```

#### Recovery 3: Type Mismatch Correction

**Error**: `Conversion failed when converting varchar to int`

**Strategy**:
```python
add_to_prompt("""
Error: Type mismatch
Fix: Use CAST() or CONVERT():
  - CAST(column AS INT)
  - CONVERT(INT, column)
Example: WHERE CAST(ProductID AS INT) > 100
""")
```

---

## Stage 4: SQL Execution & Analysis

**NEW FEATURE**: Execute validated SQL with automatic retry, profiling, and insights.

### 4.1 Execution Endpoint

```http
POST /api/v1/execute-sql
Content-Type: application/json

{
  "sql": "SELECT * FROM Products WHERE Price > 100",
  "context": {
    "user_query": "Show expensive products",
    "schema_context": "Products table schema..."
  },
  "timeout_seconds": 30,
  "max_rows": 10000,
  "chart_type_override": "column"
}
```

### 4.2 Execution with Auto-Retry

```python
# File: app/api/endpoints/generation.py
# Function: execute_sql_endpoint() - Lines 292-403

MAX_RETRY_ATTEMPTS = 5

for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
    result = execute_sql_query(
        current_sql,
        timeout_seconds=request.timeout_seconds,
        max_rows=request.max_rows,
        enable_profiling=True,
        user_query=user_query
    )
    
    if result["success"]:
        break  # Success!
    
    if attempt < MAX_RETRY_ATTEMPTS:
        # Regenerate SQL with error feedback
        current_sql = regenerate_sql_with_error_feedback(
            original_request=user_query,
            failed_sql=current_sql,
            error_message=result["error"],
            schema_context=schema_context,
            attempt_number=attempt + 1
        )
```

### 4.3 SQL Execution Service

```python
# File: app/services/validation_service.py
# Function: execute_sql_query() - Lines 158-292

def execute_sql_query(sql, timeout_seconds, max_rows, enable_profiling, user_query):
    engine = get_db_engine()
    raw_conn = engine.raw_connection()
    cursor = raw_conn.cursor()
    
    # Set timeout
    cursor.timeout = timeout_seconds
    
    # Execute SQL
    cursor.execute(sql)
    
    # Fetch all result sets (handles multiple SELECT statements)
    result_sets = _fetch_all_result_sets(cursor)
    
    # Limit rows
    for result_set in result_sets:
        if len(result_set["data"]) > max_rows:
            result_set["data"] = result_set["data"][:max_rows]
    
    # Serialize to JSON-compatible format
    # (handles datetime, Decimal, bytes)
    
    return {
        "success": True,
        "output": result_sets[0],
        "results": result_sets,
        "execution_time": elapsed_time,
        "rows_affected": len(result_sets[0]["data"])
    }
```

**Key Features**:
- **Configurable timeout** (default 30s)
- **Row limits** (default 10,000 to prevent memory exhaustion)
- **Multi-result set support** (handles multiple SELECT statements)
- **Type serialization** (datetime → ISO 8601, Decimal → float, bytes → base64)

### 4.4 Data Profiling

```python
# File: app/services/profiling_service.py

profiling_service = ProfilingService()
data_profile = profiling_service.profile_dataframe(df)
```

**Profiling Levels**:

#### Level 1: Basic (<0.5s)
- Row count, column count
- Data types
- Null percentages

#### Level 2: Distribution (~1-2s, <10k rows)
- Min, max, mean, median, std dev
- Quartiles (25%, 75%)
- Outlier detection (beyond 3×IQR)
- Top value frequencies

#### Level 3: Relationship (~1-2s, <5k rows + <10 cols)
- Correlation matrix
- Strongly correlated pairs (|r| > 0.7)

**Example Output**:
```json
{
  "row_count": 77,
  "column_count": 3,
  "profiling_level": "relationship",
  "columns": [
    {
      "column_name": "ProductID",
      "data_type": "int64",
      "numeric_stats": {
        "min": 1,
        "max": 77,
        "mean": 39.0,
        "median": 39.0,
        "std": 22.3,
        "outliers": []
      }
    },
    {
      "column_name": "Price",
      "data_type": "float64",
      "numeric_stats": {
        "min": 2.5,
        "max": 263.5,
        "mean": 28.87,
        "median": 18.0,
        "outliers": [263.5, 210.8, 123.79]
      }
    }
  ],
  "correlations": [
    {
      "col1": "ProductID",
      "col2": "Price",
      "correlation": 0.14
    }
  ]
}
```

### 4.5 Insight Generation

```python
# File: app/services/insight_service.py

insight_service = InsightService()
insights = insight_service.generate_insights(
    profile=data_profile,
    user_query=user_query,
    df_sample=df.head(10)
)
```

**Hybrid Approach**:
1. **Rule-based detection** (no LLM calls):
   - Outliers (values > 3×IQR)
   - Strong correlations (|r| > 0.7)
   - Missing data (>10% nulls)
   - Sparse distributions (>50% in one category)

2. **LLM prioritization** (single call):
   - Ranks detected insights
   - Selects top 5 most relevant
   - Adds severity and confidence scores

**Example Output**:
```json
{
  "insights": [
    {
      "insight_type": "outlier",
      "title": "Price Outliers Detected",
      "description": "3 products have prices significantly higher than typical range (>$100): Côte de Blaye ($263.50), Thüringer Rostbratwurst ($123.79), Mishi Kobe Niku ($97.00)",
      "severity": "warning",
      "related_columns": ["Price"],
      "confidence": 0.95
    },
    {
      "insight_type": "distribution",
      "title": "Price Distribution Skewed",
      "description": "Most products (75%) are priced under $50, with a long tail of premium items",
      "severity": "info",
      "related_columns": ["Price"],
      "confidence": 0.88
    },
    {
      "insight_type": "recommendation",
      "title": "Consider Price Segmentation",
      "description": "Products naturally cluster into 3 price tiers: Budget (<$20), Standard ($20-$50), Premium (>$50). Consider analyzing sales performance by tier.",
      "severity": "info",
      "related_columns": ["Price"],
      "confidence": 0.75
    }
  ]
}
```

### 4.6 Chart Recommendation

```python
# File: app/services/visualization_service.py

viz_service = VisualizationService()
recommendation = viz_service.get_chart_recommendation(
    df=df,
    user_query=user_query,
    chart_type_override=request.chart_type_override
)
```

**Process**:
1. **Data Classification**:
   - 2D data (1 category + 1 number) → bar, line, pie
   - 3D data (1 category + multiple numbers) → stacked/clustered
   - Too large (>200 rows or >15 cols) → table only
   - Multiple text columns → table only

2. **LLM Recommendation** (if chartable):
   ```python
   prompt = f"""
   User Query: {user_query}
   Data Sample (first 5 rows): {df.head(5).to_markdown()}
   
   Recommend the best chart type: bar, line, pie, scatter, etc.
   Specify x_axis and y_axis columns.
   """
   ```

3. **Override Support**:
   If user specifies `chart_type_override="pie"`, validate and use it.

**Example Output**:
```json
{
  "chart_type": "column",
  "x_axis": "ProductName",
  "y_axis": ["Price"],
  "title": "Product Prices",
  "explanation": "A column chart is ideal for comparing prices across products",
  "colors": ["#4CAF50"]
}
```

### 4.7 Response Format

```json
{
  "success": true,
  "output": {
    "columns": ["ProductID", "ProductName", "Price"],
    "data": [
      {"ProductID": 38, "ProductName": "Côte de Blaye", "Price": 263.5},
      {"ProductID": 29, "ProductName": "Thüringer Rostbratwurst", "Price": 123.79},
      ...
    ]
  },
  "results": [
    {
      "name": "result_set_1",
      "type": "sql_result",
      "data": {...},
      "rows": 10,
      "columns": ["ProductID", "ProductName", "Price"]
    }
  ],
  "recommendation": {
    "chart_type": "column",
    "x_axis": "ProductName",
    "y_axis": ["Price"],
    "title": "Product Prices",
    "explanation": "Column chart shows price comparison clearly"
  },
  "execution_time": 0.42,
  "rows_affected": 10,
  "data_profile": {
    "row_count": 10,
    "column_count": 3,
    "profiling_level": "basic",
    "columns": [...]
  },
  "insights": [
    {
      "insight_type": "outlier",
      "title": "Price Outliers Detected",
      "description": "3 products with extremely high prices",
      "severity": "warning"
    }
  ],
  
  // Auto-fix metadata (only if retry occurred)
  "sql": "SELECT * FROM Products WHERE Price > 100 ORDER BY Price DESC",
  "auto_fixed": true,
  "fix_attempt": 2,
  "original_error": "Invalid object name 'products'. Did you mean 'Products'?"
}
```

---

## Data Flow Diagrams

### Generation Flow (Parse-Only)

```
User Query
    │
    ▼
Query Analysis
    │
    ▼
Multi-Source Discovery
    │
    ├─→ Value Index (weight 10)
    ├─→ Few-Shot Index (weight 5)
    └─→ Schema Index (weight 2)
    │
    ▼
Re-rank & Select Top 8 Tables
    │
    ▼
Path Finding (Add glue tables)
    │
    ▼
Schema Completeness Validation
    │
    ▼
Build Context Prompt
    │
    ▼
LLM Generates SQL
    │
    ▼
Database Validation (SET NOEXEC ON)
    │
    ├─→ Valid? → Return SQL ✅
    │
    └─→ Invalid? → Intelligent Recovery
            │
            └─→ Retry (max 5 attempts)
```

### Execution Flow (Actual Run)

```
Validated SQL
    │
    ▼
Execute SQL with Timeout & Row Limit
    │
    ├─→ Success? → Continue
    │
    └─→ Error? → Regenerate SQL with Error Feedback
            │
            └─→ Retry (max 5 attempts)
    │
    ▼
Fetch & Serialize Results
    │
    ▼
Data Profiling
    ├─→ Basic stats
    ├─→ Distribution analysis
    └─→ Correlation matrix
    │
    ▼
Insight Generation
    ├─→ Rule-based detection
    └─→ LLM prioritization
    │
    ▼
Chart Recommendation
    ├─→ Data classification
    ├─→ LLM recommendation
    └─→ Override handling
    │
    ▼
Return ExecuteSQLResponse
    ├─→ Results
    ├─→ Profile
    ├─→ Insights
    ├─→ Chart config
    └─→ Auto-fix metadata
```

---

## Key Services Reference

### Generation Service
**File**: `app/services/generation_service.py` (~3,000+ lines)

**Key Functions**:
- `generate_sql_for_request()` - Main SQL generation pipeline (Lines 1756+)
- `rerank_and_select_tables()` - Multi-source re-ranking (value/few-shot/schema weighted scoring)
- `expand_context_with_neighbors()` - Path finding (LLM suggests glue tables)
- `hydrate_override_context()` - Context hydration for user-pinned tables
- `_hydrate_discovery_context_scoped()` - Context hydration scoped to a source
- `_search_schemas_scoped()` - Source-aware schema index search
- `expand_value_tables_with_relationships()` - FK-traced expansion of value index hits
- `expand_context_for_missing_data()` - Post-Step-10 context expansion
- `_handle_general_query()` - Off-topic LLM response
- `planning_conversation()` - Plan mode handler
- `search_data_objects()` - Search mode handler
- `build_system_catalog_prompt()` - System metadata SQL prompt builder

### Validation Service
**File**: `app/services/validation_service.py`

**Key Functions**:
- `validate_sql_with_db()` - Parse-only validation with `SET NOEXEC ON`
- `execute_sql_query()` - Actual SQL execution with timeout & row limits
- `_serialize_sql_results()` - Convert SQL types to JSON (datetime, Decimal, bytes)
- `_fetch_all_result_sets()` - Handle multiple SELECT result sets

### LLM Service
**File**: `app/services/llm_service.py`

**Key Methods**:
- `generate_sql_with_context()` - T-SQL generation (temperature=0)
- `evaluate_example_relevance()` - KB example relevance assessment (returns `is_sufficient`, `confidence`, `adjustments_needed`, `missing_entities`)
- `validate_schema_with_join_paths()` - Schema sufficiency + join path validation
- `check_schema_sufficiency()` - Schema sufficiency only (no join path check)
- `extract_filter_values()` - NER-based filter value extraction
- `extract_tables_from_sql()` - Extract table references from SQL strings
- `classify_query_intent()` - 3-way intent classification (data_query / system_metadata / off_topic)

### Discovery Service
**File**: `app/services/discovery_service.py`

**Key Functions**:
- `perform_discovery()` - Schema + few-shot search (used in error recovery)
- `perform_value_index_search()` - Value index search with FK relationship tracing

### Skills Service
**File**: `app/services/skills_service.py`

**Key Methods**:
- `load_data_sources_index()` - Load all registered data sources
- `load_primary_data_source()` - Load the primary/default data source
- Data source objects carry `.name`, `.description`, `.keywords`, `.source_id`

### Profiling Service
**File**: `app/services/profiling_service.py`

**Key Class**: `ProfilingService`
- `profile_dataframe()` - Generate DataProfile
- Profiling levels: `basic`, `distribution`, `relationship`

### Insight Service

## Configuration Options
**Key Class**: `InsightService`
- `generate_insights()` - Hybrid rule-based + LLM
- Insight types: `outlier`, `trend`, `correlation`, `missing_data`, `distribution`, `recommendation`

### Visualization Service
**File**: `app/services/visualization_service.py`

**Key Class**: `VisualizationService`
- `get_chart_recommendation()` - Optimal chart selection
- Supports 12 chart types: bar, line, pie, scatter, column variants, area, radar, treemap, funnel

---

## API Endpoints
### 1. Generate SQL (Parse-Only)

```http
### Insight Service
X-API-Key: your-api-key

{
  "query": "Show monthly revenue for 2024",
  "queryMode": "generate",
  "forceGeneral": false,
  "table_override": null,
  "previousSQL": null,
  "queryHistory": null
}
```

**Response** (Server-Sent Events stream):
```json
// Status update
data: {"step_id": 1, "message": "Analyzing query...", "type": "status"}

// Status update
data: {"step_id": 2, "message": "Searching for relevant tables...", "type": "status"}

// Final result
data: {
  "type": "result",
  "payload": {
    "sql": "SELECT MONTH(OrderDate) AS Month, SUM(Quantity * UnitPrice) AS Revenue FROM Orders o JOIN OrderDetails od ON o.OrderID = od.OrderID WHERE YEAR(OrderDate) = 2024 GROUP BY MONTH(OrderDate) ORDER BY Month",
    "explanation": "This query calculates monthly revenue for 2024...",
    "query_type": "database",
    "context_text": "Full prompt sent to LLM...",
    "context_history": null
  }
}
```

### 2. Execute SQL (Actual Execution)

```http
POST /api/v1/execute-sql
Content-Type: application/json
X-API-Key: your-api-key

{
  "sql": "SELECT * FROM Products WHERE Price > 100",
  "context": {
    "user_query": "Show expensive products",
    "schema_context": "Products table with ProductID, ProductName, Price columns"
  },
  "timeout_seconds": 30,
  "max_rows": 10000,
  "chart_type_override": "column"
}
```

**Response**:
```json
{
  "success": true,
  "output": {
    "columns": ["ProductID", "ProductName", "Price"],
    "data": [
      {"ProductID": 38, "ProductName": "Côte de Blaye", "Price": 263.5},
      ...
    ]
  },
  "results": [...],
  "recommendation": {
    "chart_type": "column",
    "x_axis": "ProductName",
    "y_axis": ["Price"]
  },
  "execution_time": 0.42,
  "rows_affected": 10,
  "data_profile": {...},
  "insights": [...],
  "sql": null,
  "auto_fixed": false,
  "fix_attempt": 1,
  "original_error": null
}
```

---

## Configuration Options

### Database Settings
```json
// config/settings.json
{
  "target_db": {
    "friendly_name": "Northwind Database",
    "description": "Sales database for imported and exported specialty foods",
    "keywords": ["sales", "customers", "orders", "products"],
    "db_type": "mssql",
    "server": "localhost",
    "database_name": "Northwind",
    "driver": "ODBC Driver 17 for SQL Server",
    "connection_string_encrypted": "..."
  }
}
```

### LLM Configuration
```json
{
  "llm_config": {
    "llm_model": "gpt-4o",
    "temperature": 0.0,
    "llm_endpoint": null,
    "llm_api_key": "sk-..."
  }
}
```

### Execution Defaults
```python
# In app/api/endpoints/generation.py
MAX_RETRY_ATTEMPTS = 5  # Configurable

# In ExecuteSQLRequest model
timeout_seconds: int = 30  # Default query timeout
max_rows: int = 10000  # Default row limit
```

### Profiling Thresholds
```python
# In app/services/profiling_service.py
MAX_ROWS_FOR_DISTRIBUTION = 10000
MAX_ROWS_FOR_RELATIONSHIP = 5000
MAX_COLS_FOR_RELATIONSHIP = 10

# In app/services/validation_service.py
MAX_ROWS_FOR_PROFILING = 100000  # Security limit
```

---

## Common Error Scenarios

### 1. Invalid Object Name

**Error**: `Invalid object name 'dbo.products'`

**Cause**: Case sensitivity or missing table

**Generation Stage Recovery**:
- Search vector DB for similar table names
- Suggest correct name: "Did you mean 'Products'?"

**Execution Stage Recovery**:
- Regenerate SQL with correct table name
- Add note: "Table names in SQL Server are case-sensitive"

### 2. Ambiguous Column Name

**Error**: `Ambiguous column name 'Name'`

**Cause**: Multiple tables have a 'Name' column, aliases not used

**Recovery**:
```sql
-- Before (error):
SELECT Name FROM Customers JOIN Products ON ...

-- After (fixed):
SELECT c.Name AS CustomerName, p.Name AS ProductName
FROM Customers c
JOIN Products p ON ...
```

### 3. Type Mismatch

**Error**: `Conversion failed when converting varchar to int`

**Cause**: Comparing incompatible types

**Recovery**:
```sql
-- Before (error):
WHERE ProductID = '100'  -- ProductID is INT, '100' is VARCHAR

-- After (fixed):
WHERE ProductID = CAST('100' AS INT)
-- OR
WHERE ProductID = 100
```

### 4. Query Timeout

**Error**: `Query timeout expired`

**Cause**: Query too slow (>30s default)

**Recovery**:
- Increase `timeout_seconds` in request
- Suggest optimization: indexes, WHERE clauses, LIMIT
- Regenerate with simplified query

### 5. Empty Result Set

**Status**: SUCCESS (not an error)

**Handling**:
```json
{
  "success": true,
  "output": {"columns": ["ProductID", "Price"], "data": []},
  "rows_affected": 0
}
```

**Note**: Empty results do NOT trigger retry (per design decision).

---

## Performance Considerations

### Latency by Stage

| Stage | Typical Latency | Notes |
|-------|----------------|-------|
| Query Analysis | ~0.5-1s | LLM call |
| Discovery | ~0.5-1s | Vector search (3 sources) |
| Path Finding | ~0.5s | LLM call |
| Schema Validation | ~0.2s | LLM call |
| SQL Generation | ~1-2s | LLM call |
| Parse Validation | ~0.1s | Database parse |
| **Total (Generation)** | **~3-5s** | First attempt |

| Stage | Typical Latency | Notes |
|-------|----------------|-------|
| SQL Execution | ~0.5-5s | Depends on query complexity |
| Data Profiling | ~0.5-2s | Depends on data size |
| Insight Generation | ~1-2s | LLM call |
| Chart Recommendation | ~0.5-1s | LLM call |
| **Total (Execution)** | **~2-10s** | First attempt |

### Retry Impact

- **Generation Retry**: +2-3s per attempt (max 5 attempts = +8-12s worst case)
- **Execution Retry**: +3-5s per attempt (max 5 attempts = +12-20s worst case)

### LLM Token Usage

**Generation**:
- Query Analysis: ~500 tokens
- Path Finding: ~800 tokens
- SQL Generation: ~2,000-4,000 tokens
- Validation Recovery: +1,000 tokens per retry

**Execution**:
- SQL Regeneration: ~1,500-2,500 tokens per retry
- Insight Prioritization: ~1,000 tokens
- Chart Recommendation: ~800 tokens

**Cost Estimate** (gpt-4o):
- Generation: $0.01-0.02 per query
- Execution: $0.005-0.01 per execution
- **Total**: ~$0.015-0.03 per complete workflow

### Database Load

**Generation**: Minimal (parse-only with `SET NOEXEC ON`)

**Execution**:
- Query execution: 1-5s CPU time
- Retry attempts: Up to 5 executions per request
- **Mitigation**: Timeout enforcement, row limits, connection pooling

---

## Security & Best Practices

### SQL Injection Prevention

**Already Protected**:
- User queries are analyzed by LLM, not directly concatenated
- LLM generates parameterized SQL where possible
- Validation stage catches malicious patterns

**Best Practices**:
- Review generated SQL before execution (frontend should display it)
- Use read-only database user for query execution
- Enforce row limits to prevent data exfiltration

### Timeout & Resource Limits

**Implemented**:
```python
# Query timeout (default 30s)
cursor.timeout = timeout_seconds

# Row limit (default 10,000)
if len(results) > max_rows:
    results = results[:max_rows]

# Profiling limit (100,000 rows max)
if len(data) > MAX_ROWS_FOR_PROFILING:
    skip_profiling()
```

**Recommendations**:
- Set appropriate timeouts for your database size
- Use `max_rows` to prevent memory exhaustion
- Monitor execution times and adjust limits

### Connection Pooling

**Configuration**:
```python
# In app/core/database.py
engine = create_engine(
    connection_string,
    pool_size=10,  # Max connections
    max_overflow=20,  # Extra connections when busy
    pool_timeout=30,  # Wait time for connection
    pool_pre_ping=True  # Verify connection before use
)
```

### API Key Authentication

**All endpoints require**:
```http
X-API-Key: your-api-key
```

**Configure**:
```bash
# .env
API_KEY=change-this-to-a-secure-key
```

### Error Sanitization

**Before sending to LLM**:
- Strip connection strings
- Remove internal paths
- Sanitize stack traces

**Example**:
```python
# Never send this to LLM:
error = "Connection failed: Server=localhost;Database=Northwind;User=sa;Password=MyP@ssw0rd"

# Send this instead:
error = "Connection failed: Database connection error (credentials removed)"
```

---

## Conclusion

The SQL Generation & Execution Pipeline provides a sophisticated, production-ready system for converting natural language to executed SQL queries with:

✅ **Multi-source RAG** for accurate table discovery  
✅ **Iterative validation** with intelligent error recovery  
✅ **Automatic retry** for both generation and execution  
✅ **Data profiling** and **AI insights** for analysis  
✅ **Chart recommendations** for visualization  
✅ **Full transparency** through response metadata  

**Next Steps**:
- Test the execution endpoint with your queries
- Adjust timeout and row limits for your use case
- Monitor retry rates to optimize prompts
- Integrate with frontend for complete workflow

For detailed implementation guides, see:
- [SQL_EXECUTION_AUTO_RETRY_FEATURE.md](SQL_EXECUTION_AUTO_RETRY_FEATURE.md) - Deep dive into execution retry
- [BACKEND_API.md](BACKEND_API.md) - Complete API reference
- [PYTHON_CODE_AUTO_RETRY_FEATURE.md](PYTHON_CODE_AUTO_RETRY_FEATURE.md) - Python execution comparison
