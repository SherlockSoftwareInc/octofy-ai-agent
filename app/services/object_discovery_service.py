"""
Object discovery service for auto-detecting stored procedures and functions from SQL Server.
"""
from typing import List, Dict, Any, Optional
import re
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models.schemas import DataObject, ObjectType


def discover_stored_procedures(engine: Engine, schema: str = "dbo") -> List[DataObject]:
    """
    Discover stored procedures from SQL Server using system views.
    
    Args:
        engine: SQLAlchemy engine connection
        schema: Schema name to search (default: "dbo")
        
    Returns:
        List of DataObject instances for stored procedures
    """
    query = text("""
        SELECT 
            SCHEMA_NAME(p.schema_id) AS schema_name,
            p.name AS procedure_name,
            m.definition AS procedure_definition,
            p.create_date,
            p.modify_date
        FROM sys.procedures p
        INNER JOIN sys.sql_modules m ON p.object_id = m.object_id
        WHERE SCHEMA_NAME(p.schema_id) = :schema
        ORDER BY p.name
    """)
    
    stored_procedures = []
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema})
        
        for row in result:
            # Parse parameters from definition
            parameters = parse_sp_parameters(row.procedure_definition)
            
            # Extract description from definition comments
            description = extract_description_from_definition(row.procedure_definition)
            
            sp = DataObject(
                schema_name=row.schema_name,
                object_name=row.procedure_name,
                object_type=ObjectType.STORED_PROCEDURE,
                description=description or f"Stored procedure: {row.procedure_name}",
                definition=row.procedure_definition,
                parameters=parameters,
                columns=[]
            )
            stored_procedures.append(sp)
    
    return stored_procedures


def discover_functions(engine: Engine, schema: str = "dbo") -> List[DataObject]:
    """
    Discover user-defined functions from SQL Server.
    
    Supports:
    - Scalar functions (FN)
    - Inline table-valued functions (IF)
    - Multi-statement table-valued functions (TF)
    
    Args:
        engine: SQLAlchemy engine connection
        schema: Schema name to search (default: "dbo")
        
    Returns:
        List of DataObject instances for functions
    """
    query = text("""
        SELECT 
            SCHEMA_NAME(o.schema_id) AS schema_name,
            o.name AS function_name,
            o.type_desc AS function_type,
            m.definition AS function_definition,
            t.name AS return_type_name,
            o.create_date,
            o.modify_date
        FROM sys.objects o
        INNER JOIN sys.sql_modules m ON o.object_id = m.object_id
        LEFT JOIN sys.parameters p ON o.object_id = p.object_id AND p.parameter_id = 0  -- Return parameter
        LEFT JOIN sys.types t ON p.user_type_id = t.user_type_id
        WHERE o.type IN ('FN', 'IF', 'TF')  -- Scalar, Inline, Table-valued
        AND SCHEMA_NAME(o.schema_id) = :schema
        ORDER BY o.name
    """)
    
    functions = []
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema})
        
        for row in result:
            # Parse parameters from definition
            parameters = parse_function_parameters(row.function_definition)
            
            # Extract description
            description = extract_description_from_definition(row.function_definition)
            
            # Determine return type
            return_type = row.return_type_name or parse_return_type_from_definition(row.function_definition)
            
            func = DataObject(
                schema_name=row.schema_name,
                object_name=row.function_name,
                object_type=ObjectType.FUNCTION,
                description=description or f"{row.function_type}: {row.function_name}",
                definition=row.function_definition,
                parameters=parameters,
                return_type=return_type,
                columns=[]
            )
            functions.append(func)
    
    return functions


def discover_all_schemas(engine: Engine) -> List[str]:
    """Get list of all user schemas in the database (excluding system schemas)."""
    query = text("""
        SELECT name 
        FROM sys.schemas
        WHERE name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner', 'db_accessadmin', 
                           'db_securityadmin', 'db_ddladmin', 'db_backupoperator', 'db_datareader', 
                           'db_datawriter', 'db_denydatareader', 'db_denydatawriter')
        ORDER BY name
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        return [row.name for row in result]


def parse_sp_parameters(definition: str) -> List[Dict[str, Any]]:
    """
    Parse stored procedure parameters from CREATE PROCEDURE definition.
    
    Example: @CustomerID INT, @OrderDate DATETIME = NULL
    
    Returns:
        List of parameter dictionaries with name, type, and default value
    """
    if not definition:
        return []
    
    parameters = []
    
    # Extract the parameter section (between CREATE PROCEDURE and AS)
    pattern = r'CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+\S+\s*(.*?)\s+AS'
    match = re.search(pattern, definition, re.IGNORECASE | re.DOTALL)
    
    if not match:
        return []
    
    params_text = match.group(1).strip()
    
    # Parse individual parameters
    # Pattern: @ParamName DataType [= DefaultValue]
    param_pattern = r'(@\w+)\s+([A-Z_]+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)\s*(?:=\s*([^,]+))?'
    
    for match in re.finditer(param_pattern, params_text, re.IGNORECASE):
        param_name = match.group(1)
        param_type = match.group(2).strip()
        default_value = match.group(3).strip() if match.group(3) else None
        
        parameters.append({
            "name": param_name,
            "type": param_type,
            "default": default_value,
            "description": ""
        })
    
    return parameters


def parse_function_parameters(definition: str) -> List[Dict[str, Any]]:
    """
    Parse function parameters from CREATE FUNCTION definition.
    
    Similar to SP parameters but for functions.
    """
    if not definition:
        return []
    
    parameters = []
    
    # Extract the parameter section
    pattern = r'CREATE\s+(?:OR\s+ALTER\s+)?FUNCTION\s+\S+\s*\((.*?)\)'
    match = re.search(pattern, definition, re.IGNORECASE | re.DOTALL)
    
    if not match:
        return []
    
    params_text = match.group(1).strip()
    
    # Parse individual parameters
    param_pattern = r'(@\w+)\s+([A-Z_]+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)'
    
    for match in re.finditer(param_pattern, params_text, re.IGNORECASE):
        param_name = match.group(1)
        param_type = match.group(2).strip()
        
        parameters.append({
            "name": param_name,
            "type": param_type,
            "default": None,
            "description": ""
        })
    
    return parameters


def parse_return_type_from_definition(definition: str) -> Optional[str]:
    """
    Extract return type from function definition.
    
    Examples:
    - RETURNS INT
    - RETURNS TABLE
    - RETURNS @ResultTable TABLE (...)
    """
    if not definition:
        return None
    
    # Pattern for RETURNS clause
    pattern = r'RETURNS\s+(@\w+\s+)?(\w+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)'
    match = re.search(pattern, definition, re.IGNORECASE)
    
    if match:
        return match.group(2).strip()
    
    return None


def extract_description_from_definition(definition: str) -> Optional[str]:
    """
    Extract description from SQL comments in the definition.
    
    Looks for:
    - Single-line comments: -- Description: ...
    - Multi-line comments: /* Description ... */
    """
    if not definition:
        return None
    
    # Try to find description comment patterns
    patterns = [
        r'--\s*Description:\s*(.+)',
        r'--\s*Purpose:\s*(.+)',
        r'/\*\s*Description:\s*(.+?)\*/',
        r'/\*\s*Purpose:\s*(.+?)\*/',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, definition, re.IGNORECASE | re.DOTALL)
        if match:
            desc = match.group(1).strip()
            # Clean up multi-line
            desc = re.sub(r'\s+', ' ', desc)
            return desc[:500]  # Limit length
    
    return None


def build_sp_markdown_description(sp: DataObject) -> str:
    """
    Generate rich Markdown description for stored procedure.
    
    Format:
    ## Stored Procedure: [schema].[sp_name]
    > Description text
    
    ### Parameters:
    - @CustomerID (INT) - Customer identifier
    - @OrderDate (DATETIME) = NULL - Optional order date filter
    
    ### Usage:
    ```sql
    EXEC [schema].[sp_name] @CustomerID = 123, @OrderDate = '2024-01-01'
    ```
    """
    lines = []
    lines.append(f"## **Stored Procedure:** `[{sp.schema_name}].[{sp.object_name}]`")
    
    if sp.description:
        lines.append(f"> {sp.description}")
    
    lines.append("---")
    
    if sp.parameters:
        lines.append("### **Parameters:**")
        for param in sp.parameters:
            default_text = f" = {param['default']}" if param.get('default') else ""
            desc_text = f" - {param['description']}" if param.get('description') else ""
            lines.append(f"- `{param['name']}` ({param['type']}){default_text}{desc_text}")
        lines.append("")
    
    # Usage example
    lines.append("### **Usage:**")
    lines.append("```sql")
    
    if sp.parameters:
        param_list = ", ".join([f"{p['name']} = <value>" for p in sp.parameters])
        lines.append(f"EXEC [{sp.schema_name}].[{sp.object_name}] {param_list}")
    else:
        lines.append(f"EXEC [{sp.schema_name}].[{sp.object_name}]")
    
    lines.append("```")
    lines.append("---")
    
    return "\n".join(lines)


def build_function_markdown_description(func: DataObject) -> str:
    """
    Generate rich Markdown description for function.
    
    Format:
    ## Function: [schema].[function_name]
    **Returns:** INT
    
    > Description text
    
    ### Parameters:
    - @Param1 (INT) - Description
    
    ### Usage:
    ```sql
    SELECT [schema].[function_name](@Param1 = 123)
    ```
    """
    lines = []
    lines.append(f"## **Function:** `[{func.schema_name}].[{func.object_name}]`")
    
    if func.return_type:
        lines.append(f"**Returns:** `{func.return_type}`")
    
    if func.description:
        lines.append(f"> {func.description}")
    
    lines.append("---")
    
    if func.parameters:
        lines.append("### **Parameters:**")
        for param in func.parameters:
            desc_text = f" - {param['description']}" if param.get('description') else ""
            lines.append(f"- `{param['name']}` ({param['type']}){desc_text}")
        lines.append("")
    
    # Usage example
    lines.append("### **Usage:**")
    lines.append("```sql")
    
    if func.parameters:
        param_list = ", ".join([f"{p['name']} = <value>" for p in func.parameters])
        lines.append(f"SELECT [{func.schema_name}].[{func.object_name}]({param_list})")
    else:
        lines.append(f"SELECT [{func.schema_name}].[{func.object_name}]()")
    
    lines.append("```")
    lines.append("---")
    
    return "\n".join(lines)
