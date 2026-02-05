# SQL Execution Auto-Retry Feature

## Overview

This feature adds automatic error recovery for SQL query execution by feeding execution errors back to the LLM for query regeneration. The system will automatically retry up to 5 times to fix errors while maintaining focus on the original user request.

## Implementation Date

January 29, 2026

## Key Features

1. **Automatic Silent Retries**: Up to 5 execution attempts happen transparently behind the scenes
2. **Error Feedback Loop**: Failed SQL and error messages are sent to LLM for intelligent fixes
3. **Query Replacement**: Successfully fixed SQL replaces the originally generated query
4. **User Notification**: Response includes flags indicating when auto-fix occurred
5. **Data Analysis**: Includes profiling, insights, and chart recommendations for successful executions

## Architecture

### Retry Flow

```
User Request → Execute SQL → Success? → Return Result + Analysis
                     ↓ No (attempt 1-4)
              Feed Error to LLM → Regenerate SQL
                     ↓
              Execute Fixed SQL → Success? → Return with auto_fixed=True
                     ↓ No
              Repeat up to 5 times total
                     ↓
              Final Failure → Return Error
```

### Success Criteria

SQL execution is considered successful when:
- The query runs without throwing any exceptions
- Empty result sets count as "success" (empty is valid data)
- Timeout errors trigger retry with optimized query

### Context Sent to LLM for Retry

Each retry includes:
1. **Original User Request**: The natural language query to maintain goal focus
2. **Failed SQL**: The query that caused the error
3. **Error Message**: Full traceback and error details from database
4. **Schema Context**: Database schema used for original generation
5. **Attempt Number**: Which retry this is (2-5)

## Files Modified

### 1. `app/models/schemas.py`

**Changes**: Added `ExecuteSQLRequest` and `ExecuteSQLResponse` models

```python
class ExecuteSQLRequest(BaseModel):
    sql: str  # SQL query to execute
    context: Optional[Dict[str, Any]] = None  # Optional execution context
    chart_type_override: Optional[ChartTypeLiteral] = None  # User-specified chart type
    timeout_seconds: Optional[int] = 30  # Configurable timeout
    max_rows: Optional[int] = 10000  # Row limit for results

class ExecuteSQLResponse(BaseModel):
    # ... execution results ...
    sql: Optional[str] = None  # NEW: Final working SQL (if auto-fixed)
    auto_fixed: bool = False  # NEW: Flag indicating auto-retry happened
    fix_attempt: int = 1  # NEW: Which attempt succeeded (1-5)
    original_error: Optional[str] = None  # NEW: Original error before auto-fix
```

**Location**: Lines 76-81, 184-199

### 2. `app/services/validation_service.py`

**Changes**: Added SQL execution function with full profiling support

#### Function 1: `execute_sql_query()`

**Purpose**: Executes SQL query and returns structured results with profiling

**Parameters**:
- `sql` (str): T-SQL query to execute
- `timeout_seconds` (int): Query timeout (default 30)
- `max_rows` (int): Row limit (default 10000)
- `enable_profiling` (bool): Enable data profiling (default True)
- `user_query` (str): Original natural language query for context

**Returns**: Dict with execution results, profiling, and insights

**Location**: Lines 158-292

**Key Features**:
- Configurable timeout at connection level
- Row limits to prevent memory exhaustion
- Multi-result set support (multiple SELECT statements)
- Type serialization (datetime→ISO8601, Decimal→float, bytes→base64)
- Automatic data profiling and insight generation

#### Helper Functions:

**`_serialize_sql_value()`** (Lines 68-87):
- Converts SQL types to JSON-compatible format

**`_serialize_sql_results()`** (Lines 90-127):
- Converts pyodbc cursor results to structured JSON

**`_fetch_all_result_sets()`** (Lines 130-155):
- Handles multiple result sets from batch queries

### 3. `app/services/generation_service.py`

**Changes**: Added SQL error regeneration function

#### Function: `regenerate_sql_with_error_feedback()`

**Purpose**: Generates fixed SQL based on execution error feedback

**Parameters**:
- `original_request` (str): User's natural language request
- `failed_sql` (str): The SQL that failed execution
- `error_message` (str): Error traceback from database
- `schema_context` (str): Database schema context
- `attempt_number` (int): Retry attempt number (2-5)

**Returns**: Regenerated SQL query as string

**Location**: Lines 945-1030

**Key Features**:
- Analyzes error to identify root cause
- Maintains original query intent and logic
- Follows T-SQL best practices (aliases, CAST, qualifiers)
- Uses LLM with temperature=0.1 for consistency
- Handles common error patterns (invalid objects, ambiguous columns, type mismatches)

### 4. `app/api/endpoints/generation.py`

**Changes**: Added `/execute-sql` endpoint with retry loop

**Key Components**:
1. `MAX_RETRY_ATTEMPTS = 5` constant (Line 292)
2. Retry loop implementation (Lines 305-341)
3. Visualization recommendation (Lines 344-366)
4. Response with auto-fix metadata (Lines 369-383)

**Location**: Lines 289-403

**Retry Logic**:
```python
attempt = 1
while attempt <= MAX_RETRY_ATTEMPTS:
    result = execute_sql_query(current_sql, ...)
    
    if result["success"]:
        break  # Success!
    
    if attempt >= MAX_RETRY_ATTEMPTS:
        break  # Max attempts reached
    
    # Regenerate SQL with error feedback
    current_sql = regenerate_sql_with_error_feedback(...)
    attempt += 1
```

## Response Format

### When Auto-Fix Succeeds

```json
{
  "success": true,
  "output": {
    "columns": ["ProductID", "ProductName", "Price"],
    "data": [
      {"ProductID": 38, "ProductName": "Côte de Blaye", "Price": 263.5}
    ]
  },
  "results": [...],
  "recommendation": {
    "chart_type": "column",
    "x_axis": "ProductName",
    "y_axis": ["Price"]
  },
  "execution_time": 1.2,
  "rows_affected": 10,
  "data_profile": {...},
  "insights": [...],
  "sql": "SELECT * FROM Products WHERE Price > 100",
  "auto_fixed": true,
  "fix_attempt": 2,
  "original_error": "Invalid object name 'products'. Expected 'Products'."
}
```

### When First Attempt Succeeds

```json
{
  "success": true,
  "output": {...},
  "results": [...],
  "sql": null,
  "auto_fixed": false,
  "fix_attempt": 1,
  "original_error": null
}
```

### When All Attempts Fail

```json
{
  "success": false,
  "error": "Final error after 5 attempts: Invalid column name 'xyz'",
  "sql": null,
  "auto_fixed": false,
  "fix_attempt": 5,
  "original_error": null
}
```

## Frontend Integration

### Displaying Auto-Fixed SQL

```javascript
if (response.auto_fixed && response.sql) {
  // Update displayed SQL with fixed version
  sqlEditor.setValue(response.sql);
  
  // Show notification
  showNotification(
    `SQL automatically fixed on attempt ${response.fix_attempt}/5`,
    'success'
  );
}
```

### UI/UX Recommendations

1. **Badge or Icon**: Display when SQL was auto-fixed
   - Example: "Auto-fixed (2/5)" badge

2. **Notification**: Show success message
   - "Query was automatically corrected to fix execution errors"

3. **Debugging Info**: Expandable section with original error

4. **Color Coding**: Green border for auto-fixed queries

## Common Error Scenarios Handled

### 1. Invalid Object Name

**Error**: `Invalid object name 'dbo.products'`

**Fix**: Correct to `dbo.Products` (proper case)

### 2. Ambiguous Column Name

**Error**: `Ambiguous column name 'Name'`

**Fix**: Add table aliases: `c.Name AS CustomerName, p.Name AS ProductName`

### 3. Type Mismatch

**Error**: `Conversion failed when converting varchar to int`

**Fix**: Add CAST: `WHERE ProductID = CAST('100' AS INT)`

### 4. Syntax Error

**Error**: `Incorrect syntax near 'WHERE'`

**Fix**: Correct T-SQL syntax (JOIN conditions, missing commas, etc.)

### 5. Timeout

**Error**: `Query timeout expired`

**Fix**: Optimize query (add WHERE clause, indexes, LIMIT)

## Configuration

### Retry Attempts

```python
# In app/api/endpoints/generation.py
MAX_RETRY_ATTEMPTS = 5  # Change to desired number (3-7 recommended)
```

### Execution Limits

```python
# In ExecuteSQLRequest model
timeout_seconds: int = 30  # Query timeout
max_rows: int = 10000  # Row limit
```

### LLM Temperature

```python
# In app/services/generation_service.py, line ~980
fixed_sql = llm_service.chat(prompt, temperature=0.1)  # Adjust as needed
```

## Performance Considerations

### Latency Impact

- **First attempt success**: ~0.5-2s (execution + profiling)
- **Each retry adds**: ~3-5s (LLM call + re-execution)
- **Maximum latency**: ~15-25s (5 attempts)

### Cost Impact

- **LLM API calls**: 1 additional call per retry
- **Token usage per retry**: ~1,500-2,500 tokens (smaller than Python)
- **Worst case**: 4 extra LLM calls (attempts 2-5)

### Database Load

- **Up to 5 executions** per request (if all retries fail)
- **Mitigation**: Timeout enforcement, row limits, connection pooling

## Security Considerations

### SQL Injection Prevention

- User input analyzed by LLM, not directly concatenated
- Validation stage catches malicious patterns
- Frontend should display generated SQL before execution

### Resource Limits

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

### Connection Pooling

```python
engine = create_engine(
    connection_string,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True
)
```

## Testing

### Manual Test Cases

#### Test 1: Simple Query (Success on First Attempt)

**Request**:
```json
POST /api/v1/execute-sql
{
  "sql": "SELECT TOP 10 * FROM Products",
  "context": {
    "user_query": "Show me the first 10 products"
  }
}
```

**Expected**:
- `success=True`
- Results with 10 rows
- `auto_fixed=False`
- `fix_attempt=1`

#### Test 2: Query with Error (Auto-Retry)

**Request**:
```json
POST /api/v1/execute-sql
{
  "sql": "SELECT * FROM products",  // Wrong case
  "context": {
    "user_query": "Show all products",
    "schema_context": "Products table..."
  }
}
```

**Expected**:
- `success=True` (after retry)
- `auto_fixed=True`
- `fix_attempt=2`
- `sql` contains corrected query
- `original_error` contains first error

#### Test 3: Empty Result Set

**Request**:
```json
POST /api/v1/execute-sql
{
  "sql": "SELECT * FROM Products WHERE ProductID = 99999"
}
```

**Expected**:
- `success=True`
- `results=[]` (empty)
- `auto_fixed=False` (empty is valid)

#### Test 4: Query Timeout

**Request**:
```json
POST /api/v1/execute-sql
{
  "sql": "SELECT * FROM LargeTable",
  "timeout_seconds": 5
}
```

**Expected**:
- `success=False` or retry with optimized query
- Error contains timeout message

#### Test 5: Data Profiling & Insights

**Request**:
```json
POST /api/v1/execute-sql
{
  "sql": "SELECT Country, COUNT(*) as Count FROM Customers GROUP BY Country"
}
```

**Expected**:
- `success=True`
- `data_profile` with column statistics
- `insights` with detected patterns
- `recommendation` with chart suggestion

## Comparison with Python Execution

| Feature | Python Execution | SQL Execution |
|---------|------------------|---------------|
| **Endpoint** | `/execute-python` | `/execute-sql` |
| **Max Retries** | 5 | 5 |
| **Auto-Fix Metadata** | ✅ | ✅ |
| **Data Profiling** | ✅ | ✅ |
| **Insights** | ✅ | ✅ |
| **Chart Recommendation** | ✅ | ✅ |
| **Timeout** | Inherited | ✅ Configurable |
| **Row Limits** | Code-based | ✅ Configurable |
| **Connection Injection** | ✅ DB_CONNECTION_STRING | ❌ Uses pool |
| **Code Sanitization** | ✅ Remove LLM artifacts | ❌ Pre-validated |
| **Scope Isolation** | ✅ exec() with local scope | ❌ Stateless SQL |

## Related Documentation

- **[GENERATE_SQL.md](GENERATE_SQL.md)**: Complete SQL generation & execution process
- **[PYTHON_CODE_AUTO_RETRY_FEATURE.md](PYTHON_CODE_AUTO_RETRY_FEATURE.md)**: Python execution comparison
- **[BACKEND_API.md](BACKEND_API.md)**: API endpoint reference

## Conclusion

The SQL Execution Auto-Retry feature significantly improves the user experience by automatically recovering from common execution errors. It maintains transparency through response metadata while operating efficiently to reduce friction. Combined with data profiling, insights, and chart recommendations, it provides a complete workflow from natural language query to actionable visualizations.

For implementation details, see:
- `app/services/validation_service.py` - Execution logic
- `app/services/generation_service.py` - Regeneration logic
- `app/api/endpoints/generation.py` - API endpoint
