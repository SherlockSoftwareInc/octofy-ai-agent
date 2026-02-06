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
    - generation_service.py (SQL)
    - code_generation_service.py (R, SAS, Python)
    
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
