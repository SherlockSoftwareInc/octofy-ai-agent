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
│ - Query classification (database/general/uncertain)              │
│ - Entity extraction & date range detection                       │
│ - Complexity scoring (simple/moderate/complex)                   │
│ - Special mode handling (search/general)                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: Discovery & Context Synthesis                          │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│ │ Value Index │  │  Few-Shot   │  │Schema Index │             │
│ │ (weight 10) │  │ (weight 5)  │  │ (weight 2)  │             │
│ └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│        └─────────────────┴─────────────────┘                    │
│                         │                                        │
│                Re-rank & Select Top 8 Tables                    │
│                         │                                        │
│        ┌────────────────┴────────────────┐                      │
│        │ Path Finding (Context Expansion)│                      │
│        └────────────────┬────────────────┘                      │
│                         │                                        │
│              Schema Completeness Validation                     │
└──────────────────────┬──────────────────────────────────────────┘
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
# Function: generate_sql_for_request() - Lines 419-454
```

### Steps

#### 1.1 Load Database Settings
```python
settings = get_settings_for_display()
database_name = settings.target_db.database_name
database_description = settings.target_db.description
database_keywords = settings.target_db.keywords
```

**Example Output**:
```
Database: Northwind
Description: Sales database for imported and exported specialty foods
Keywords: ['sales', 'customers', 'orders', 'products', 'employees', 'shipping']
```

#### 1.2 Handle Special Modes

**Search Mode** (`queryMode="search"`):
- Returns database objects instead of SQL
- Used for schema exploration

**General Chat Mode** (`forceGeneral=True`):
- Skips SQL generation
- Returns conversational response

#### 1.3 Extract Entities & Date Ranges

Uses LLM to parse the query:
```python
# Extract key nouns (e.g., "customers", "orders", "products")
entities = ["customers", "revenue", "2024"]

# Detect date ranges
date_ranges = ["2024-01-01 to 2024-12-31"]
```

#### 1.4 Score Query Complexity

Classification rules:
- **Simple**: Single table, basic filtering (`SELECT * FROM Products WHERE Price > 100`)
- **Moderate**: 2-3 tables, simple joins (`SELECT c.Name, COUNT(o.OrderID) FROM Customers c JOIN Orders o...`)
- **Complex**: 4+ tables, CTEs, subqueries, aggregations

**Complexity affects**:
- Number of knowledge base examples included
- Prompt structure
- Validation strictness

---

## Stage 2: Discovery & Context Synthesis

**Purpose**: Find the most relevant tables and example queries using multi-source RAG.

### 2.1 Multi-Source Discovery Strategy

The system searches **three parallel sources** and combines results with weighted scoring:

```python
# File: app/services/generation_service.py
# Lines 481-521
```

#### Source 1: Value Index Discovery (Weight: 10)

**What**: Maps user terms to exact database values.

**Example**:
```
User Query: "Show sales in North America"
Value Index Search: "North America"
→ Finds: Customers.Region = 'North America'
→ Returns: ['Customers'] with weight 10
```

**Process**:
1. Extract filter values from query using LLM
2. Search `value_index` collection in Milvus
3. Return tables containing matching values

#### Source 2: Few-Shot Discovery (Weight: 5)

**What**: Finds similar SQL queries from knowledge base.

**Example**:
```
User Query: "Monthly revenue by product category"
Few-Shot Search (semantic):
→ Match: "What is the total revenue by category?"
→ SQL: SELECT c.CategoryName, SUM(od.Quantity * od.UnitPrice) FROM Categories c...
→ Extracts tables: ['Categories', 'Products', 'OrderDetails']
→ Returns: ['Categories', 'Products', 'OrderDetails'] with weight 5 each
```

**Process**:
1. Embed user query with OpenAI text-embedding-3-small
2. Search `fewshot_index` collection (top 3 matches)
3. Parse table names from example SQL queries

#### Source 3: Schema Index Discovery (Weight: 2)

**What**: Semantic search on table descriptions.

**Example**:
```
User Query: "Show employee sales performance"
Schema Search (semantic):
→ Match: "Employees" table (description mentions "sales representatives")
→ Match: "Orders" table (description mentions "employee assignments")
→ Returns: ['Employees', 'Orders'] with weight 2 each
```

**Process**:
1. Embed user query
2. Search `schema_index` collection (top 5 matches)
3. Return table names

#### 2.2 Re-Ranking & Selection

**Algorithm**:
```python
def rerank_and_select_tables(few_shot_tables, value_tables, schema_tables):
    scores = {}
    
    # Accumulate scores
    for table in value_tables:
        scores[table] += 10
    for table in few_shot_tables:
        scores[table] += 5
    for table in schema_tables:
        scores[table] += 2
    
    # Sort by score descending
    sorted_tables = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return top 8
    return [table for table, score in sorted_tables[:8]]
```

**Example**:
```
Value Index:   ['Customers', 'Orders']        → +10 each
Few-Shot:      ['Orders', 'Products']         → +5 each
Schema:        ['Orders', 'Employees']        → +2 each

Final Scores:
  Orders: 10 + 5 + 2 = 17 ⭐⭐⭐
  Customers: 10 = 10 ⭐⭐
  Products: 5 = 5 ⭐
  Employees: 2 = 2

Selected (top 8): ['Orders', 'Customers', 'Products', 'Employees']
```

#### 2.3 Path Finding / Context Expansion

**Purpose**: Identify missing "glue tables" needed for joins.

```python
# Example:
Selected Tables: ['Customers', 'Products']
User Query: "Show customer purchases by product"

Path Finding (LLM):
→ "To connect Customers and Products, you need: Orders, OrderDetails"
→ Adds: ['Orders', 'OrderDetails'] to context
```

**Process**:
```python
expand_context_with_neighbors(selected_tables, user_query)
# Uses LLM to suggest intermediate tables
```

#### 2.4 Schema Completeness Validation

**Purpose**: Ensure all foreign key dependencies are satisfied.

**Example**:
```
Selected: ['Orders', 'Customers']
Orders.CustomerID → FK to Customers.CustomerID ✅

Selected: ['OrderDetails', 'Shippers']
OrderDetails.OrderID → FK to Orders.OrderID ❌ MISSING!

Action: Auto-discover and add 'Orders' table
```

**Process**:
```python
llm_service.validate_schema_references(schema_context)
→ Returns: "MISSING_TABLES" or "SCHEMA_COMPLETE"

If missing:
    - Search vector DB for missing tables
    - Add to context
    - Re-validate
```

#### 2.5 Value Index Lookup

**Purpose**: Include exact categorical values in prompt.

**Example**:
```
Query: "Sales in Canada"
Value Lookup:
→ Customers.Country: ["Canada", "USA", "Mexico", ...]
→ Includes in prompt: "For Country, valid values include: 'Canada', 'USA', 'Mexico'"
```

---

## Stage 3: Iterative SQL Generation & Validation

**Purpose**: Generate and validate SQL, with automatic error recovery.

### 3.1 Retry Loop (Max 5 Attempts)

```python
# File: app/services/generation_service.py
# Lines 731-923

for attempt in range(1, 6):
    # 1. Build context prompt
    prompt = build_prompt(...)
    
    # 2. LLM generates SQL
    sql = llm_service.generate_sql_with_context(prompt)
    
    # 3. Validate with database
    is_valid, error_msg, missing_objects = validate_sql_with_db(sql)
    
    if is_valid:
        return sql  # SUCCESS!
    
    # 4. Intelligent recovery
    recovery_strategy = determine_recovery(error_msg, missing_objects)
    add_to_context_history(attempt, error_msg, recovery_strategy)
```

### 3.2 Context Prompt Construction

**Components** (Lines 764-819):

1. **Database Info**:
   ```
   DATABASE: Northwind
   DESCRIPTION: Sales database for imported and exported specialty foods
   KEYWORDS: sales, customers, orders, products
   ```

2. **Query Analysis**:
   ```
   USER REQUEST: Show monthly revenue for 2024
   COMPLEXITY: moderate
   ENTITIES: revenue, 2024
   DATE RANGES: 2024-01-01 to 2024-12-31
   ```

3. **Knowledge Base Examples** (filtered by complexity):
   ```
   EXAMPLE 1:
   Question: What is total revenue by month?
   SQL: SELECT MONTH(OrderDate), SUM(Quantity * UnitPrice) ...
   ```

4. **Verified Data Mappings** (from value index):
   ```
   VERIFIED VALUES:
   - Customers.Country: 'Canada', 'USA', 'Mexico', ...
   - Products.CategoryID: 1, 2, 3, 4, 5, ...
   ```

5. **Database Schema** (with full column descriptions):
   ```markdown
   ### Orders (dbo.Orders)
   Customer orders with shipping details
   
   | Column | Type | Description |
   |--------|------|-------------|
   | OrderID | int | Primary key |
   | CustomerID | nchar(5) | FK to Customers.CustomerID |
   | OrderDate | datetime | Date order was placed |
   ...
   ```

6. **Attempt History** (on retries):
   ```
   PREVIOUS ATTEMPTS:
   
   Attempt 1:
   SQL: SELECT * FROM orders WHERE ...
   Error: Invalid object name 'orders' (should be 'Orders' with capital O)
   Recovery: Check table name case sensitivity
   ```

7. **Critical SQL Rules**:
   ```
   - Use table aliases to avoid ambiguous columns
   - Use CAST() for type conversions
   - Qualify all columns with table aliases
   - Use square brackets for reserved words
   ```

### 3.3 SQL Generation (LLM)

```python
sql = llm_service.generate_sql_with_context(
    user_query=request.query,
    context_prompt=prompt,
    temperature=0  # Deterministic for consistency
)
```

**LLM Configuration**:
- Model: `gpt-4o` (configurable)
- Temperature: `0` (no creativity, strict SQL)
- Max tokens: ~2000

### 3.4 Database Validation

```python
# File: app/services/validation_service.py
# Function: validate_sql_with_db()

def validate_sql_with_db(sql):
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("SET NOEXEC ON"))  # Parse-only mode
        try:
            conn.execute(text(sql))
            return True, "", []  # Valid!
        except Exception as e:
            return False, str(e), parse_missing_objects(e)
        finally:
            conn.execute(text("SET NOEXEC OFF"))
```

**Validation Method**: SQL Server's `SET NOEXEC ON`
- Parses SQL without executing
- Catches syntax errors, invalid objects, type mismatches
- **No data modified** during validation

### 3.5 Intelligent Recovery Strategies

#### Recovery 1: Missing Object Search

**Error**: `Invalid object name 'dbo.ProductCategories'`

**Strategy**:
```python
# Search vector DB for missing table
results = vector_store.search_schemas("ProductCategories")
→ Finds: 'Categories' table

# Add to discovery context
add_table_to_context('Categories')
add_to_prompt("Did you mean 'Categories' instead of 'ProductCategories'?")
```

#### Recovery 2: Ambiguous Column Fix

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
**File**: `app/services/generation_service.py` (1,030 lines)

**Key Functions**:
- `generate_sql_for_request()` - Main SQL generation pipeline (Lines 411-933)
- `regenerate_sql_with_error_feedback()` - Lightweight retry regeneration (Lines 945-1030)
- `rerank_and_select_tables()` - Multi-source re-ranking (Lines 33-60)
- `expand_context_with_neighbors()` - Path finding (Lines 95-127)

### Validation Service
**File**: `app/services/validation_service.py` (292 lines)

**Key Functions**:
- `validate_sql_with_db()` - Parse-only validation with `SET NOEXEC ON` (Lines 5-65)
- `execute_sql_query()` - Actual SQL execution with profiling (Lines 158-292)
- `_serialize_sql_results()` - Convert SQL types to JSON (Lines 90-127)
- `_fetch_all_result_sets()` - Handle multiple result sets (Lines 130-155)

### LLM Service
**File**: `app/services/llm_service.py` (816 lines)

**Implementations**:
- `OpenAILLMService` - Direct OpenAI SDK (Lines 40-411)
- `LiteLLMService` - Multi-provider via LiteLLM (Lines 412-786)

**Key Methods**:
- `generate_sql_with_context()` - SQL generation (Lines 186-219, 544-577)
- `validate_schema_references()` - FK completeness check (Lines 88-184, 468-542)
- `suggest_intermediate_tables()` - Path finding (Lines 343-386, 714-760)
- `extract_filter_values()` - Value extraction (Lines 388-410, 762-786)

### Discovery Service
**File**: `app/services/discovery_service.py` (33 lines)

**Key Function**:
- `perform_discovery()` - Schema + few-shot search (Lines 4-32)

### Profiling Service
**File**: `app/services/profiling_service.py` (290 lines)

**Key Class**: `ProfilingService`
- `profile_dataframe()` - Generate DataProfile (Lines 22-180)
- Profiling levels: `basic`, `distribution`, `relationship`

### Insight Service
**File**: `app/services/insight_service.py` (368 lines)

**Key Class**: `InsightService`
- `generate_insights()` - Hybrid rule-based + LLM (Lines 19-150)
- Insight types: `outlier`, `trend`, `correlation`, `missing_data`, `distribution`, `recommendation`

### Visualization Service
**File**: `app/services/visualization_service.py` (420 lines)

**Key Class**: `VisualizationService`
- `get_chart_recommendation()` - Optimal chart selection (Lines 17-70)
- Supports 12 chart types: bar, line, pie, scatter, column variants, area, radar, treemap, funnel

---

## API Endpoints

### 1. Generate SQL (Parse-Only)

```http
POST /api/v1/generate-sql
Content-Type: application/json
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
