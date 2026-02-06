# Join-Path Validation Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize schema validation across all code generation types (SQL, R, SAS, Python) with a new Join-Path Validation Protocol featuring context caching, two-stage verification (structural + relational), temporal data handling, and feedback loops.

**Architecture:**
1. **Pydantic Models** - New `ValidationDetail` and `JoinPathValidationResult` models
2. **Shared Utilities** - Extract duplicated schema-building code into `schema_context_utils.py`
3. **LLM Methods** - New `validate_schema_with_join_paths()` on both LLM service classes
4. **Generator Wiring** - SQL, R, SAS, Python generators all use new validation
5. **Feature Flag** - `ENABLE_JOIN_PATH_VALIDATION` for safe rollout

**Key Decision:** Old `check_schema_sufficiency()` is KEPT for backward compatibility. New method is added alongside it.

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| Scope | All 4 phases (caching, two-stage, temporal, feedback) |
| Replace or extend | Add new method, keep old for backward compat |
| R/SAS validation | Full validation (they currently have ZERO) |
| Code duplication | Extract to shared utility module |
| Fail behavior | Fail open (return "sufficient" on parse errors) |

---

## Task 1: Extend Pydantic Models

**File:** `app/models/schemas.py`  
**Location:** After existing `SchemaSufficiencyResult` (line 74)  
**Risk:** Low - additive only

### What to do

Add two new models AFTER the existing `SchemaSufficiencyResult` class (do NOT modify the existing models - they must remain for backward compatibility):

```python
# --- Join-Path Validation Models ---

class ValidationDetail(BaseModel):
    """A single validation check performed during join-path validation"""
    requirement: str  # e.g., "customer name column"
    mapping: Optional[str] = None  # e.g., "[dbo].[Customers].[CustomerName]" or "DERIVED: ..."
    found: bool = False
    reason: str = ""  # Why this passed/failed


class JoinPathValidationResult(BaseModel):
    """Result of the enhanced join-path schema validation (replaces SchemaSufficiencyResult for new flow)"""
    status: Literal["sufficient", "insufficient_data", "insufficient_joins"] = "sufficient"
    join_path: Optional[str] = None  # e.g., "Orders -> OrderDetails ON OrderID -> Products ON ProductID"
    validation_details: List[ValidationDetail] = []
    missing_logic: Optional[str] = None  # e.g., "No FK path between Customers and Invoices"
    search_suggestions: List[str] = []  # Suggested search terms for auto-discovery
    analysis: str = ""  # LLM's reasoning about sufficiency
```

### Verification
```bash
python -c "from app.models.schemas import ValidationDetail, JoinPathValidationResult; print('OK')"
```

---

## Task 2: Create Shared Schema Context Utilities

**File:** `app/services/schema_context_utils.py` (NEW FILE)  
**Risk:** Low - new module, no existing code affected

### What to do

Create a new file `app/services/schema_context_utils.py` with these functions:

```python
"""
Shared schema context utilities for all code generators.

Eliminates 4x code duplication across SQL, R, SAS, and Python generators
by providing common functions for schema text building, view detection,
temporal handling, and derivation guidance.
"""

import re
import hashlib
import logging
from typing import List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def build_schema_text(schemas: List[Any], use_table_override: bool = False) -> str:
    """
    Build annotated schema text with [TABLE]/[VIEW] labels and column details.
    
    Replaces the inline schema-building loops that were duplicated in:
    - generation_service.py:1712-1729
    - code_generation_service.py:316-328 (R)
    - code_generation_service.py:607-620 (SAS)
    - code_generation_service.py:962-976 (Python)
    
    Args:
        schemas: List of TableSchema objects with column definitions
        use_table_override: If True and description exists, use raw description
        
    Returns:
        Formatted schema text string with [TABLE]/[VIEW] annotations
    """
    schema_parts = []
    for t in schemas:
        if use_table_override and getattr(t, 'description', None):
            schema_parts.append(t.description)
            continue

        schema_name = getattr(t, 'schema_name', 'dbo') or 'dbo'
        table_name = getattr(t, 'table_name', '')
        description = getattr(t, 'description', 'No description') or 'No description'
        columns = getattr(t, 'columns', [])
        table_type = getattr(t, 'table_type', 'TABLE')
        
        # Annotate with [TABLE] or [VIEW]
        type_label = "[VIEW]" if _is_view(table_type, table_name) else "[TABLE]"
        
        t_text = f"{type_label} Table: {schema_name}.{table_name}\nDescription: {description}\nColumns:"
        if columns:
            for col in columns:
                col_name = getattr(col, 'name', '')
                col_type = getattr(col, 'data_type', '')
                col_desc = getattr(col, 'description', '') or ''
                # Mark potential FK columns
                fk_marker = " [FK]" if _looks_like_fk(col_name) else ""
                t_text += f"\n  - {col_name} ({col_type}){fk_marker}: {col_desc}"
        else:
            t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    
    return "\n\n".join(schema_parts)


def build_sufficiency_schema_text(schemas: List[Any]) -> str:
    """
    Build compact schema text for validation LLM calls (reduces token usage).
    
    Uses a more compact format than build_schema_text() since the LLM only
    needs column names and types for sufficiency checking, not full descriptions.
    
    Args:
        schemas: List of TableSchema objects
        
    Returns:
        Compact schema text string
    """
    parts = []
    for t in schemas:
        schema_name = getattr(t, 'schema_name', 'dbo') or 'dbo'
        table_name = getattr(t, 'table_name', '')
        columns = getattr(t, 'columns', [])
        description = getattr(t, 'description', '')
        table_type = getattr(t, 'table_type', 'TABLE')
        
        type_label = "[VIEW]" if _is_view(table_type, table_name) else "[TABLE]"
        
        if columns:
            cols = ", ".join([f"{c.name} ({c.data_type})" for c in columns])
            parts.append(f"{type_label} [{schema_name}].[{table_name}]: {cols}")
        elif description:
            parts.append(f"{type_label} [{schema_name}].[{table_name}]:\n{description}")
        else:
            parts.append(f"{type_label} [{schema_name}].[{table_name}]: (no column information available)")
    
    return "\n\n".join(parts)


def prioritize_base_tables(schemas: List[Any]) -> List[Any]:
    """
    Filter out views when equivalent base tables exist.
    
    For temporal queries, views like Orders_1997 should be deprioritized
    when the base Orders table exists (which has datetime columns for filtering).
    
    Args:
        schemas: List of TableSchema objects
        
    Returns:
        Filtered list with views removed when base table equivalents exist
    """
    # Separate tables and views
    base_tables = {}
    views = {}
    
    for t in schemas:
        table_name = getattr(t, 'table_name', '')
        table_type = getattr(t, 'table_type', 'TABLE')
        
        if _is_view(table_type, table_name):
            views[table_name] = t
        else:
            base_tables[table_name] = t
    
    # If no views or no base tables, return as-is
    if not views or not base_tables:
        return list(schemas)
    
    # Check each view against base tables
    filtered = list(base_tables.values())
    base_names = set(base_tables.keys())
    
    for view_name, view in views.items():
        base_name = _extract_base_name(view_name)
        if base_name and base_name in base_names:
            logger.debug(f"Filtering view '{view_name}' - base table '{base_name}' exists")
        else:
            filtered.append(view)
    
    return filtered


def generate_schema_id(schemas: List[Any]) -> str:
    """
    Generate a deterministic hash for a set of schemas (for context caching).
    
    Args:
        schemas: List of TableSchema objects
        
    Returns:
        SHA-256 hex digest of the schema fingerprint
    """
    fingerprint_parts = []
    for t in sorted(schemas, key=lambda x: getattr(x, 'table_name', '')):
        table_name = getattr(t, 'table_name', '')
        schema_name = getattr(t, 'schema_name', 'dbo')
        columns = getattr(t, 'columns', [])
        col_names = sorted([getattr(c, 'name', '') for c in columns])
        fingerprint_parts.append(f"{schema_name}.{table_name}:{','.join(col_names)}")
    
    fingerprint = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


def has_datetime_columns(schemas: List[Any]) -> bool:
    """
    Check if any schema has datetime/date/timestamp columns.
    
    Used for temporal data handling - if datetime columns exist,
    the LLM should not flag temporal queries as insufficient.
    
    Args:
        schemas: List of TableSchema objects
        
    Returns:
        True if any schema has datetime-type columns
    """
    datetime_types = {'datetime', 'datetime2', 'date', 'smalldatetime', 'timestamp', 'datetimeoffset', 'time'}
    
    for t in schemas:
        columns = getattr(t, 'columns', [])
        for col in columns:
            data_type = getattr(col, 'data_type', '').lower()
            if data_type in datetime_types:
                return True
    return False


def get_derivation_guidance(code_type: str) -> str:
    """
    Get language-specific derivation guidance for the validation prompt.
    
    Tells the LLM what computed/derived values are possible in each language
    so it doesn't flag derivable values as missing.
    
    Args:
        code_type: One of "sql", "r", "sas", "python"
        
    Returns:
        Derivation guidance string for the LLM prompt
    """
    code_type_lower = code_type.lower()
    
    if code_type_lower == "python":
        return """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
Python/pandas can compute virtually ANY derived value from raw columns:
- **Aggregations**: df.sum(), df.mean(), df.count(), df.groupby().agg() 
- **Calculated fields**: df['amount'] = df['quantity'] * df['price']
- **Rankings**: df.nlargest(), df.sort_values(), df.rank()
- **Date operations**: pd.to_datetime(), dt.year, dt.month, date arithmetic
- **String operations**: str.contains(), str.upper(), str.split()
- **Statistical analysis**: correlation, percentiles, distributions
- **Pivot tables**: df.pivot_table(), df.crosstab()
- **Window functions**: df.rolling(), df.expanding(), df.shift()

IMPORTANT: If the base columns exist, Python can derive almost anything through code."""

    elif code_type_lower == "r":
        return """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
R (with tidyverse/dplyr) can compute virtually ANY derived value from raw columns:
- **Aggregations**: summarise(n(), sum(), mean(), median()), group_by() + summarise()
- **Calculated fields**: mutate(amount = quantity * price), transmute()
- **Rankings**: top_n(), arrange(), dense_rank(), row_number()
- **Date operations**: lubridate::ymd(), year(), month(), floor_date(), date arithmetic
- **String operations**: stringr::str_detect(), str_replace(), str_to_upper()
- **Statistical analysis**: cor(), quantile(), sd(), t.test()
- **Pivot operations**: tidyr::pivot_wider(), pivot_longer()
- **Window functions**: lag(), lead(), cumsum(), cummean()
- **Joins**: inner_join(), left_join(), anti_join() on related tables

IMPORTANT: If the base columns exist, R can derive almost anything through code."""

    elif code_type_lower == "sas":
        return """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
SAS can compute derived values through multiple approaches:
- **PROC SQL**: COUNT(*), SUM(), AVG(), GROUP BY, HAVING, subqueries
- **DATA step**: calculated fields, conditional logic (IF/THEN/ELSE), arrays, DO loops
- **PROC MEANS/SUMMARY**: N, MEAN, STD, MIN, MAX, SUM with CLASS variables
- **PROC FREQ**: frequency tables, crosstabs, chi-square tests
- **Date operations**: DATEPART(), YEAR(), MONTH(), INTCK(), INTNX(), date formats
- **String operations**: SUBSTR(), UPCASE(), COMPRESS(), SCAN(), CATX()
- **Rankings**: PROC RANK, ORDER BY in PROC SQL, FIRST./LAST. in DATA step
- **Joins**: PROC SQL joins, DATA step MERGE with BY variables

IMPORTANT: If the base columns exist, SAS can derive almost anything through code."""

    else:  # sql (default)
        return """### DERIVABLE VALUES - Mark as "found: true" if computable from existing columns:
- **Aggregations**: COUNT(*), SUM(column), AVG(column), MIN/MAX - always available
- **Calculated fields**: quantity * unit_price = amount, date differences, etc.
- **Rankings**: TOP N, ORDER BY, ROW_NUMBER() - always available
- **Date extractions**: YEAR(), MONTH(), DATEPART() from date columns
- **String operations**: CONCAT(), SUBSTRING(), UPPER/LOWER from string columns
- **Conditional logic**: CASE WHEN, IIF() on existing columns
- **Standard joins**: If related tables exist, join operations are available"""


def get_temporal_guidance(schemas: List[Any]) -> str:
    """
    Get temporal data handling guidance if schemas contain datetime columns.
    
    Prevents the LLM from flagging temporal queries as insufficient when
    datetime columns exist that can be filtered with WHERE clauses.
    
    Args:
        schemas: List of TableSchema objects
        
    Returns:
        Temporal guidance string (empty if no datetime columns found)
    """
    if not has_datetime_columns(schemas):
        return ""
    
    return """
### TEMPORAL DATA HANDLING
DateTime columns detected in the available schemas. For date-filtered queries:
- Prefer base tables with datetime columns over pre-filtered views
- YEAR(), MONTH(), DATEPART() can extract any date component
- Date ranges can be filtered with WHERE clauses on datetime columns
- Do NOT flag as "insufficient" if the user asks for a specific year/month and datetime columns exist
"""


# --- Private helpers ---

def _is_view(table_type: Optional[str], table_name: str) -> bool:
    """Determine if a schema object represents a view."""
    if table_type and table_type.upper() == 'VIEW':
        return True
    # Heuristic: common view naming patterns
    name_lower = table_name.lower()
    return name_lower.endswith('_vw') or name_lower.endswith('_view') or name_lower.endswith('view')


def _looks_like_fk(column_name: str) -> bool:
    """Heuristic check if a column name looks like a foreign key."""
    name_lower = column_name.lower()
    return name_lower.endswith('id') and name_lower != 'id' and len(name_lower) > 2


def _extract_base_name(view_name: str) -> Optional[str]:
    """
    Extract base table name from a view name.
    
    Examples:
        Orders_1997 -> Orders
        Customers_vw -> Customers
        ProductsView -> Products
    """
    # Try common patterns
    patterns = [
        r'^(.+?)_\d{4}$',       # TableName_YYYY (year-filtered view)
        r'^(.+?)_vw$',           # TableName_vw
        r'^(.+?)_view$',         # TableName_view
        r'^(.+?)View$',          # TableNameView
    ]
    
    for pattern in patterns:
        match = re.match(pattern, view_name, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None
```

### Verification
```bash
python -c "from app.services.schema_context_utils import build_schema_text, build_sufficiency_schema_text, prioritize_base_tables, generate_schema_id, has_datetime_columns, get_derivation_guidance, get_temporal_guidance; print('All imports OK')"
```

---

## Task 3: Add validate_schema_with_join_paths() to Both LLM Classes

**File:** `app/services/llm_service.py`  
**Locations:**
- Base class: After line 38 (after `extract_filter_values` abstract method)
- OpenAILLMService: After line 357 (after existing `check_schema_sufficiency`)
- LiteLLMService: After line 881 (after existing `check_schema_sufficiency`)
- Factory: Line 1137 (only returns LiteLLMService, no change needed)

**Risk:** Medium - modifying core LLM service, but additive only

### What to do

#### 3a. Add abstract method to LLMServiceBase

After the `extract_filter_values` abstract method (line 38), add:

```python
    @abstractmethod
    def validate_schema_with_join_paths(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        pass
```

#### 3b. Build the shared prompt builder (private function at module level)

Add this BEFORE `get_llm_service()` (before line 1137):

```python
def _build_join_path_validation_prompt(user_query: str, schema_text: str, code_type: str, temporal_guidance: str, derivation_guidance: str) -> str:
    """Build the join-path validation prompt used by both LLM service implementations."""
    return f"""### ROLE
You are a database schema analyst performing a two-stage validation check.

### TASK
Analyze the user's request against the provided schemas using TWO validation stages:
- **Stage A (Structural):** Do the schemas contain the required columns/data points?
- **Stage B (Relational):** Can the required tables be joined together via a valid path?

### CODE TYPE
{code_type.upper()} - Consider what calculations are possible in this language.

### USER REQUEST
{user_query}

### AVAILABLE SCHEMAS
{schema_text}
{temporal_guidance}

### VALIDATION PROTOCOL

**Stage A - Structural Check:**
1. Identify the core data points required to answer the user's request
2. For each data point, check if it exists directly or can be derived
3. If ANY required base data is truly missing -> status: "insufficient_data"

**Stage B - Relational Check (only if Stage A passes):**
1. If the query requires data from multiple tables, verify a join path exists
2. Look for shared columns (especially columns ending in 'ID' marked [FK])
3. Trace the path: Table_A -> shared_key -> Table_B -> shared_key -> Table_C
4. If tables cannot be connected -> status: "insufficient_joins"

{derivation_guidance}

### OUTPUT FORMAT (JSON only, no markdown)
{{
  "status": "sufficient" or "insufficient_data" or "insufficient_joins",
  "join_path": "TableA -> TableB ON ColumnX -> TableC ON ColumnY" or null,
  "validation_details": [
    {{
      "requirement": "descriptive name of what's needed",
      "mapping": "[schema].[table].[column]" or "DERIVED: expression" or null,
      "found": true or false,
      "reason": "explanation"
    }}
  ],
  "missing_logic": "explanation of what join path is missing" or null,
  "search_suggestions": ["term1", "term2"],
  "analysis": "Brief overall assessment"
}}

### CRITICAL RULES
- status: "sufficient" if all data points exist AND tables can be joined
- status: "insufficient_data" if required BASE DATA does not exist in any schema
- status: "insufficient_joins" if data exists but tables CANNOT be connected
- join_path: REQUIRED when query involves 2+ tables, null for single-table queries
- For single-table queries: skip Stage B, just report Stage A result
- Do NOT require pre-calculated columns when {code_type.upper()} can compute them
- The question is: "Do we have the RAW DATA and can we JOIN it?" not "Do we have the exact column name?"
- search_suggestions: only populate if status is NOT "sufficient"
"""
```

#### 3c. Implement on OpenAILLMService

Add this method AFTER the existing `check_schema_sufficiency` method (after line 357) in `OpenAILLMService`:

```python
    def validate_schema_with_join_paths(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        """
        Enhanced validation with join-path verification (Stage A + Stage B).
        
        Replaces check_schema_sufficiency for new validation flow while 
        keeping the old method for backward compatibility.
        """
        import json
        from app.services.schema_context_utils import (
            build_sufficiency_schema_text, get_derivation_guidance, 
            get_temporal_guidance, prioritize_base_tables
        )
        
        # Mock mode for development
        if self.client is None:
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": "Mock validation - schema assumed sufficient"
            }
        
        # Prioritize base tables over views for temporal queries
        filtered_schemas = prioritize_base_tables(schemas)
        
        schema_text = build_sufficiency_schema_text(filtered_schemas)
        derivation_guidance = get_derivation_guidance(code_type)
        temporal_guidance = get_temporal_guidance(filtered_schemas)
        
        prompt = _build_join_path_validation_prompt(
            user_query, schema_text, code_type, temporal_guidance, derivation_guidance
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, response.choices[0].message.content)
            
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse join-path validation response as JSON: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to parse error: {e}"
            }
        except Exception as e:
            logging.error(f"Error in join-path validation: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to error: {e}"
            }
```

#### 3d. Implement on LiteLLMService

Add the same method AFTER the existing `check_schema_sufficiency` method (after line 881) in `LiteLLMService`, using `litellm.completion()` instead of `self.client.chat.completions.create()`:

```python
    def validate_schema_with_join_paths(self, user_query: str, schemas: List[Any], code_type: str = "sql") -> Dict[str, Any]:
        """
        Enhanced validation with join-path verification (Stage A + Stage B).
        
        Replaces check_schema_sufficiency for new validation flow while 
        keeping the old method for backward compatibility.
        """
        import json
        from app.services.schema_context_utils import (
            build_sufficiency_schema_text, get_derivation_guidance, 
            get_temporal_guidance, prioritize_base_tables
        )
        
        # Prioritize base tables over views for temporal queries
        filtered_schemas = prioritize_base_tables(schemas)
        
        schema_text = build_sufficiency_schema_text(filtered_schemas)
        derivation_guidance = get_derivation_guidance(code_type)
        temporal_guidance = get_temporal_guidance(filtered_schemas)
        
        prompt = _build_join_path_validation_prompt(
            user_query, schema_text, code_type, temporal_guidance, derivation_guidance
        )
        
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "You are a database schema validator. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, response.choices[0].message.content)
            
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse join-path validation response as JSON: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to parse error: {e}"
            }
        except Exception as e:
            logging.error(f"Error in join-path validation: {e}")
            return {
                "status": "sufficient",
                "join_path": None,
                "validation_details": [],
                "missing_logic": None,
                "search_suggestions": [],
                "analysis": f"Validation skipped due to error: {e}"
            }
```

### Verification
```bash
python -c "from app.services.llm_service import LiteLLMService; print(hasattr(LiteLLMService, 'validate_schema_with_join_paths')); print('OK')"
```

---

## Task 4: Wire into SQL Generation

**File:** `app/services/generation_service.py`  
**Locations:**
- Lines 1622-1675: Replace `check_schema_sufficiency` call with `validate_schema_with_join_paths`
- Lines 1712-1729: Replace inline schema building with `build_schema_text()`

**Risk:** Medium - modifying active SQL generation pipeline

### What to do

#### 4a. Replace validation call (lines 1622-1675)

Find the block starting with:
```python
    # Stage 2.6: Schema Sufficiency Pre-Flight Check
    if not use_table_override:
```

Replace the `check_schema_sufficiency` calls with `validate_schema_with_join_paths`:

```python
    # Stage 2.6: Schema Sufficiency Pre-Flight Check (Join-Path Validation)
    if not use_table_override:
        from app.core.config import settings as app_settings
        use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
        
        if use_join_path:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
            
            sufficiency_result = llm_service.validate_schema_with_join_paths(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="sql"
            )
        else:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
            
            sufficiency_result = llm_service.check_schema_sufficiency(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="sql"
            )
        
        result_status = sufficiency_result.get("status")
        
        if result_status in ("insufficient_data", "insufficient_joins"):
            missing_points = sufficiency_result.get("missing_data_points", []) or sufficiency_result.get("validation_details", [])
            search_suggestions = sufficiency_result.get("search_suggestions", [])
            missing_logic = sufficiency_result.get("missing_logic")
            
            # For insufficient_joins, include the missing join logic in the log
            if result_status == "insufficient_joins" and missing_logic:
                logging.info(f"Join-path validation failed. Missing logic: {missing_logic}")
            else:
                logging.info(f"Schema sufficiency check failed. Missing: {[p.get('name', p.get('requirement', '')) for p in missing_points]}")
            
            if search_suggestions:
                yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                
                # Auto-expansion: Search for missing data
                tables_added, context = expand_context_for_missing_data(
                    context, 
                    search_suggestions,
                    max_suggestions=5
                )
                
                if tables_added:
                    yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                    
                    # Re-validate after expansion
                    if use_join_path:
                        sufficiency_result = llm_service.validate_schema_with_join_paths(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="sql"
                        )
                    else:
                        sufficiency_result = llm_service.check_schema_sufficiency(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="sql"
                        )
                    result_status = sufficiency_result.get("status")
            
            # If still insufficient after expansion, inform user
            if result_status in ("insufficient_data", "insufficient_joins"):
                # Extract names from either old or new format
                if "missing_data_points" in sufficiency_result:
                    missing_names = [p.get("name", "unknown") for p in sufficiency_result.get("missing_data_points", [])]
                else:
                    missing_names = [d.get("requirement", "unknown") for d in sufficiency_result.get("validation_details", []) if not d.get("found", True)]
                
                analysis = sufficiency_result.get("analysis", "Required data not found in available schemas.")
                missing_logic_msg = sufficiency_result.get("missing_logic", "")
                
                missing_list = "\n".join([f"- {name}" for name in missing_names])
                
                explanation = f"**Schema Validation Failed**\n\nI analyzed your request but cannot find the required data in the available schemas.\n\n**Missing data points:**\n{missing_list}\n\n**Analysis:** {analysis}"
                if missing_logic_msg:
                    explanation += f"\n\n**Join issue:** {missing_logic_msg}"
                
                result = GenerateSQLResponse(
                    sql="",
                    explanation=explanation,
                    query_type="database",
                    context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}"
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
        
        yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with generation...")
```

#### 4b. Replace inline schema building (lines 1712-1729)

Find the block:
```python
    # Build initial schema text
    schema_parts = []
    for t in context.relevant_tables:
        ...
    initial_schema_text = "\n\n".join(schema_parts)
```

Replace with:
```python
    # Build initial schema text using shared utility
    from app.services.schema_context_utils import build_schema_text
    initial_schema_text = build_schema_text(context.relevant_tables, use_table_override=use_table_override)
```

### Verification
```bash
python -c "from app.services.generation_service import generate_sql_stream; print('Import OK')"
```

---

## Task 5: Wire into R Generator

**File:** `app/services/code_generation_service.py`  
**Location:** After line 296 (after `value_mappings = {}`) and before line 298 (knowledge base search)
**Also:** Lines 316-328 (replace inline schema building)

**Risk:** Medium - adding validation to R generator that had NONE before

### What to do

#### 5a. Add validation block after value_mappings

Insert this block between `value_mappings = {}` (line 296) and the knowledge base search (line 298):

```python
    # Stage 2.6: Schema Sufficiency Pre-Flight Check (Join-Path Validation)
    if not use_table_override:
        from app.core.config import settings as app_settings
        use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
        
        if use_join_path:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
            
            sufficiency_result = llm_service.validate_schema_with_join_paths(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="r"
            )
        else:
            yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
            
            sufficiency_result = llm_service.check_schema_sufficiency(
                user_query=request.query,
                schemas=context.relevant_tables,
                code_type="r"
            )
        
        result_status = sufficiency_result.get("status")
        
        if result_status in ("insufficient_data", "insufficient_joins"):
            search_suggestions = sufficiency_result.get("search_suggestions", [])
            missing_logic = sufficiency_result.get("missing_logic")
            
            if result_status == "insufficient_joins" and missing_logic:
                logger.info(f"Join-path validation failed for R. Missing logic: {missing_logic}")
            
            if search_suggestions:
                yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                
                tables_added, context = expand_context_for_missing_data(
                    context, 
                    search_suggestions,
                    max_suggestions=5
                )
                
                if tables_added:
                    yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                    
                    if use_join_path:
                        sufficiency_result = llm_service.validate_schema_with_join_paths(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="r"
                        )
                    else:
                        sufficiency_result = llm_service.check_schema_sufficiency(
                            user_query=request.query,
                            schemas=context.relevant_tables,
                            code_type="r"
                        )
                    result_status = sufficiency_result.get("status")
            
            if result_status in ("insufficient_data", "insufficient_joins"):
                if "missing_data_points" in sufficiency_result:
                    missing_names = [p.get("name", "unknown") for p in sufficiency_result.get("missing_data_points", [])]
                else:
                    missing_names = [d.get("requirement", "unknown") for d in sufficiency_result.get("validation_details", []) if not d.get("found", True)]
                
                analysis = sufficiency_result.get("analysis", "Required data not found in available schemas.")
                missing_logic_msg = sufficiency_result.get("missing_logic", "")
                missing_list = "\n".join([f"- {name}" for name in missing_names])
                
                explanation = f"**Schema Validation Failed**\n\nI analyzed your request but cannot find the required data in the available schemas.\n\n**Missing data points:**\n{missing_list}\n\n**Analysis:** {analysis}"
                if missing_logic_msg:
                    explanation += f"\n\n**Join issue:** {missing_logic_msg}"
                
                result = GenerateSQLResponse(
                    sql="",
                    explanation=explanation,
                    query_type="r_code",
                    context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}"
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
        
        yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with R code generation...")

```

#### 5b. Replace inline schema building (lines 316-328)

Find the R generator's schema building block:
```python
    # Build Schema & Value Text
    schema_parts = []
    for t in context.relevant_tables:
        if use_table_override and t.description:
            schema_parts.append(t.description)
            continue
        t_text = f"Table: {t.schema_name or 'dbo'}.{t.table_name}\nDescription: {t.description or 'No description'}\nColumns:"
        if t.columns:
            for col in t.columns:
                t_text += f"\n  - {col.name} ({col.data_type}): {col.description or ''}"
        else:
             t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    schema_text = "\n\n".join(schema_parts)
```

Replace with:
```python
    # Build Schema & Value Text using shared utility
    from app.services.schema_context_utils import build_schema_text
    schema_text = build_schema_text(context.relevant_tables, use_table_override=use_table_override)
```

### Verification
```bash
python -c "from app.services.code_generation_service import generate_r_code_stream; print('Import OK')"
```

---

## Task 6: Wire into SAS Generator

**File:** `app/services/code_generation_service.py`  
**Location:** After line 588 (after `value_mappings = {}` in SAS function) and lines 607-620 (schema building)

**Risk:** Medium - same pattern as R

### What to do

Same exact pattern as Task 5, but:
- `code_type="sas"` instead of `code_type="r"`
- `query_type="sas_code"` in the GenerateSQLResponse
- Insert after `value_mappings = {}` at line 588 (in the SAS generator function)
- Status message says "SAS code generation" instead of "R code generation"

#### 6a. Insert validation block after line 588

(Same pattern as Task 5a with `code_type="sas"` and `query_type="sas_code"`)

#### 6b. Replace inline schema building (lines 607-620)

Find the SAS generator's schema building block and replace with:
```python
    # Build Schema & Value Text using shared utility
    from app.services.schema_context_utils import build_schema_text
    schema_text = build_schema_text(context.relevant_tables, use_table_override=use_table_override)
```

### Verification
```bash
python -c "from app.services.code_generation_service import generate_sas_code_stream; print('Import OK')"
```

---

## Task 7: Update Python Generator

**File:** `app/services/code_generation_service.py`  
**Location:** Lines 888-941 (validation block) and 962-976 (schema building)

**Risk:** Medium - modifying existing validation, not adding new

### What to do

#### 7a. Replace validation call (lines 888-941)

Replace `check_schema_sufficiency(code_type="python")` with `validate_schema_with_join_paths(code_type="python")`. Same pattern as SQL (Task 4a) but with:
- `code_type="python"` 
- `query_type="python_code"` in the GenerateSQLResponse

#### 7b. Replace inline schema building (lines 962-976)

Replace with:
```python
    # Build Schema Text using shared utility
    from app.services.schema_context_utils import build_schema_text
    schema_text = build_schema_text(context.relevant_tables, use_table_override=use_table_override)
```

### Verification
```bash
python -c "from app.services.code_generation_service import generate_python_code_stream; print('Import OK')"
```

---

## Task 8: Add Feature Flag + View Guidance

**File:** `app/core/config.py`  
**Location:** After line 53 (after `CODE_ADVISOR_TEMPERATURE`)

**Risk:** Low - additive

### What to do

#### 8a. Add feature flag to config.py

Add before `settings = Settings()`:

```python
    # Join-Path Validation
    ENABLE_JOIN_PATH_VALIDATION: bool = True  # Use enhanced join-path validation (vs legacy sufficiency check)
```

#### 8b. Add view handling guidance to SQL generation prompt

In `app/services/generation_service.py`, in the `initial_prompt` f-string (around line 1735), add this to the rules section:

```
### VIEW HANDLING
- If both a base table and its view variant appear in schemas, prefer the base table
- Views ending in _YYYY, _vw, or _view are typically filtered subsets of base tables
- Base tables with datetime columns support flexible date filtering via WHERE clauses
```

This can be added as part of the context_guard section or within the initial_prompt itself.

### Verification
```bash
python -c "from app.core.config import settings; print(f'JOIN_PATH_VALIDATION={settings.ENABLE_JOIN_PATH_VALIDATION}')"
```

---

## Task 9: Update/Extend Tests

**Files:**
- `tests/test_schema_sufficiency.py` (existing - extend)
- `tests/test_schema_context_utils.py` (NEW)

**Risk:** Low - test-only changes

### What to do

#### 9a. Add new test class to test_schema_sufficiency.py

Add at the end of the file, testing the new models:

```python
from app.models.schemas import ValidationDetail, JoinPathValidationResult


class TestJoinPathValidationModels:
    """Test the new join-path validation Pydantic models"""
    
    def test_validation_detail_creation(self):
        detail = ValidationDetail(
            requirement="customer name",
            mapping="[dbo].[Customers].[CustomerName]",
            found=True,
            reason="Direct column match"
        )
        assert detail.requirement == "customer name"
        assert detail.found is True
    
    def test_validation_detail_missing(self):
        detail = ValidationDetail(
            requirement="tax rate",
            mapping=None,
            found=False,
            reason="No tax column in any schema"
        )
        assert detail.found is False
        assert detail.mapping is None
    
    def test_join_path_result_sufficient(self):
        result = JoinPathValidationResult(
            status="sufficient",
            join_path="Orders -> OrderDetails ON OrderID -> Products ON ProductID",
            validation_details=[
                ValidationDetail(requirement="order total", mapping="[dbo].[Orders].[Total]", found=True, reason="test")
            ],
            analysis="All data points found with valid join path"
        )
        assert result.status == "sufficient"
        assert result.join_path is not None
    
    def test_join_path_result_insufficient_joins(self):
        result = JoinPathValidationResult(
            status="insufficient_joins",
            join_path=None,
            missing_logic="No FK path between Customers and Invoices",
            validation_details=[
                ValidationDetail(requirement="customer name", found=True, reason="found"),
                ValidationDetail(requirement="invoice total", found=True, reason="found"),
            ],
            search_suggestions=["CustomerInvoice", "bridge table"],
            analysis="Data exists but cannot be joined"
        )
        assert result.status == "insufficient_joins"
        assert result.missing_logic is not None
        assert len(result.search_suggestions) == 2
    
    def test_join_path_result_insufficient_data(self):
        result = JoinPathValidationResult(
            status="insufficient_data",
            validation_details=[
                ValidationDetail(requirement="tax rate", found=False, reason="missing"),
            ],
            search_suggestions=["tax", "tax_rate"],
            analysis="Missing required data"
        )
        assert result.status == "insufficient_data"
```

#### 9b. Create test_schema_context_utils.py

Create `tests/test_schema_context_utils.py`:

```python
"""
Tests for the shared schema context utilities.
"""
import pytest
from unittest.mock import MagicMock
from app.services.schema_context_utils import (
    build_schema_text,
    build_sufficiency_schema_text,
    prioritize_base_tables,
    generate_schema_id,
    has_datetime_columns,
    get_derivation_guidance,
    get_temporal_guidance,
    _is_view,
    _looks_like_fk,
    _extract_base_name,
)


def _make_schema(table_name, schema_name="dbo", columns=None, description="", table_type="TABLE"):
    """Helper to create mock schema objects."""
    mock = MagicMock()
    mock.table_name = table_name
    mock.schema_name = schema_name
    mock.description = description
    mock.table_type = table_type
    if columns:
        mock.columns = [_make_column(n, t, d) for n, t, d in columns]
    else:
        mock.columns = []
    return mock


def _make_column(name, data_type="nvarchar", description=""):
    mock = MagicMock()
    mock.name = name
    mock.data_type = data_type
    mock.description = description
    return mock


class TestBuildSchemaText:
    def test_basic_table(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", "PK"), ("Total", "decimal", "Order total")])]
        result = build_schema_text(schemas)
        assert "[TABLE]" in result
        assert "Orders" in result
        assert "OrderID" in result
    
    def test_view_annotation(self):
        schemas = [_make_schema("Orders_1997", table_type="VIEW", columns=[("OrderID", "int", "")])]
        result = build_schema_text(schemas)
        assert "[VIEW]" in result
    
    def test_fk_marker(self):
        schemas = [_make_schema("Orders", columns=[("CustomerID", "int", "FK to Customers")])]
        result = build_schema_text(schemas)
        assert "[FK]" in result
    
    def test_table_override_uses_description(self):
        schemas = [_make_schema("Orders", description="Custom description")]
        result = build_schema_text(schemas, use_table_override=True)
        assert result == "Custom description"
    
    def test_no_columns(self):
        schemas = [_make_schema("Orders")]
        result = build_schema_text(schemas)
        assert "(No columns defined)" in result


class TestBuildSufficiencySchemaText:
    def test_compact_format(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", ""), ("Total", "decimal", "")])]
        result = build_sufficiency_schema_text(schemas)
        assert "[TABLE]" in result
        assert "OrderID (int)" in result
    
    def test_falls_back_to_description(self):
        schemas = [_make_schema("Orders", description="Markdown description")]
        result = build_sufficiency_schema_text(schemas)
        assert "Markdown description" in result


class TestPrioritizeBaseTables:
    def test_filters_year_view(self):
        schemas = [
            _make_schema("Orders", columns=[("OrderDate", "datetime", "")]),
            _make_schema("Orders_1997", table_type="VIEW", columns=[("OrderDate", "datetime", "")]),
        ]
        result = prioritize_base_tables(schemas)
        assert len(result) == 1
        assert result[0].table_name == "Orders"
    
    def test_keeps_unrelated_view(self):
        schemas = [
            _make_schema("Orders", columns=[("OrderID", "int", "")]),
            _make_schema("CustomerSummary", table_type="VIEW", columns=[("Name", "nvarchar", "")]),
        ]
        result = prioritize_base_tables(schemas)
        assert len(result) == 2
    
    def test_no_views_returns_all(self):
        schemas = [
            _make_schema("Orders"),
            _make_schema("Customers"),
        ]
        result = prioritize_base_tables(schemas)
        assert len(result) == 2


class TestGenerateSchemaId:
    def test_deterministic(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", "")])]
        id1 = generate_schema_id(schemas)
        id2 = generate_schema_id(schemas)
        assert id1 == id2
    
    def test_different_schemas_different_ids(self):
        s1 = [_make_schema("Orders", columns=[("OrderID", "int", "")])]
        s2 = [_make_schema("Customers", columns=[("CustomerID", "int", "")])]
        assert generate_schema_id(s1) != generate_schema_id(s2)


class TestHasDatetimeColumns:
    def test_has_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderDate", "datetime", "")])]
        assert has_datetime_columns(schemas) is True
    
    def test_has_date(self):
        schemas = [_make_schema("Orders", columns=[("OrderDate", "date", "")])]
        assert has_datetime_columns(schemas) is True
    
    def test_no_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", ""), ("Name", "nvarchar", "")])]
        assert has_datetime_columns(schemas) is False
    
    def test_empty_schemas(self):
        assert has_datetime_columns([]) is False


class TestGetDerivationGuidance:
    def test_sql_guidance(self):
        result = get_derivation_guidance("sql")
        assert "COUNT(*)" in result
        assert "CASE WHEN" in result
    
    def test_python_guidance(self):
        result = get_derivation_guidance("python")
        assert "pandas" in result
        assert "df.groupby" in result
    
    def test_r_guidance(self):
        result = get_derivation_guidance("r")
        assert "dplyr" in result
        assert "summarise" in result
    
    def test_sas_guidance(self):
        result = get_derivation_guidance("sas")
        assert "PROC SQL" in result
        assert "DATA step" in result


class TestGetTemporalGuidance:
    def test_has_guidance_when_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderDate", "datetime", "")])]
        result = get_temporal_guidance(schemas)
        assert "TEMPORAL" in result
    
    def test_empty_when_no_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", "")])]
        result = get_temporal_guidance(schemas)
        assert result == ""


class TestPrivateHelpers:
    def test_is_view_by_type(self):
        assert _is_view("VIEW", "Orders") is True
        assert _is_view("TABLE", "Orders") is False
    
    def test_is_view_by_name(self):
        assert _is_view(None, "Orders_vw") is True
        assert _is_view(None, "OrdersView") is True
        assert _is_view(None, "Orders") is False
    
    def test_looks_like_fk(self):
        assert _looks_like_fk("CustomerID") is True
        assert _looks_like_fk("OrderID") is True
        assert _looks_like_fk("ID") is False  # Just "ID" alone is not an FK
        assert _looks_like_fk("Name") is False
    
    def test_extract_base_name(self):
        assert _extract_base_name("Orders_1997") == "Orders"
        assert _extract_base_name("Customers_vw") == "Customers"
        assert _extract_base_name("ProductsView") == "Products"
        assert _extract_base_name("Orders") is None
```

### Verification
```bash
pytest tests/test_schema_context_utils.py -v
pytest tests/test_schema_sufficiency.py -v -k "TestJoinPathValidation"
```

---

## Task 10: Final Integration Verification

**Risk:** Low - verification only

### What to do

Run the full test suite and verify all imports work:

```bash
# Verify all imports
python -c "
from app.models.schemas import ValidationDetail, JoinPathValidationResult
from app.services.schema_context_utils import build_schema_text, build_sufficiency_schema_text
from app.services.schema_context_utils import prioritize_base_tables, generate_schema_id
from app.services.schema_context_utils import has_datetime_columns, get_derivation_guidance, get_temporal_guidance
from app.services.llm_service import LiteLLMService, OpenAILLMService
from app.core.config import settings
print(f'Feature flag: {settings.ENABLE_JOIN_PATH_VALIDATION}')
print(f'LiteLLM has method: {hasattr(LiteLLMService, \"validate_schema_with_join_paths\")}')
print('All imports OK')
"

# Run all tests
pytest tests/test_schema_sufficiency.py tests/test_schema_context_utils.py -v

# Verify generation service imports
python -c "from app.services.generation_service import generate_sql_stream; print('SQL gen OK')"
python -c "from app.services.code_generation_service import generate_r_code_stream, generate_sas_code_stream, generate_python_code_stream; print('Code gen OK')"
```

If any tests fail, debug and fix before marking complete.

---

## Important Notes

1. **Backward compatibility**: The old `check_schema_sufficiency()` is NEVER removed. It stays on both LLM classes. The generators use the feature flag to decide which method to call.

2. **Fail open**: All error handlers return `status: "sufficient"` to avoid blocking generation.

3. **View handling**: The `_is_view()` function uses both `table_type` attribute AND naming heuristics since Milvus stores `table_type` but some older schemas may not have it.

4. **The factory**: `get_llm_service()` at line 1137 always returns `LiteLLMService`, so that's the implementation that runs in production. OpenAI implementation is for backward compat.

5. **Imports**: Use lazy imports (`from app.services.schema_context_utils import ...`) inside function bodies in generation_service.py and code_generation_service.py to avoid circular imports at module load time.

6. **expand_context_for_missing_data**: This existing helper function is already imported in both generation_service.py and code_generation_service.py. The R and SAS generators already have it available via their imports from the discovery flow.
