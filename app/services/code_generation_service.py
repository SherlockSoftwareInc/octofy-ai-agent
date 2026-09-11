"""
R, SAS, and Python code generation functions.

R, SAS, and Python generation share the built-in SQL pipeline (routing, discovery, retry).
"""

import re
from app.models.schemas import GenerateSQLRequest, AgentStatus
from app.services.llm_service import get_llm_service
from app.services.generation_service import (
    search_data_objects,
    _handle_general_query,
)
from typing import Optional, Generator, Union, Dict, Any
import logging


from app.utils.python_normalization import cleanup_python_code as _cleanup_python_code

logger = logging.getLogger(__name__)


def generate_r_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate R code using the same built-in pipeline as SQL and Python generation:
    routing, pin validation, KB/precomputed fast paths, discovery, and bounded retry.
    """
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    combined_query = request.query
    if request.queryHistory:
        combined_query = f"{request.queryHistory}. {request.query}"

    if request.forceGeneral:
        yield AgentStatus(step_id=1, message="Processing general query...")
        llm_service = get_llm_service()
        result = _handle_general_query(combined_query, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    existing_code = request.existing_code or request.previousSQL
    is_edit = bool(existing_code and existing_code.strip() and _is_code_edit_request(request.query))

    from app.core.orchestrator.builtin_sql_generator import generate_r_builtin
    from app.services.source_resolver import resolve_or_primary
    from app.services.stores.bundle import build_source_stores

    builtin_source = resolve_or_primary(request.source_id)
    stores = build_source_stores(builtin_source)
    for event in generate_r_builtin(request, stores):
        if is_edit and isinstance(event, dict) and event.get("type") == "result":
            payload = event.get("payload")
            if isinstance(payload, dict) and payload.get("sql") and payload.get("success") is not False:
                payload["is_code_edit"] = True
                if not payload.get("explanation"):
                    payload["explanation"] = "Code updated based on your request."
        yield event


def generate_sas_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate SAS code using the same built-in pipeline as SQL and Python generation:
    routing, pin validation, KB/precomputed fast paths, discovery, and bounded retry.
    """
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    combined_query = request.query
    if request.queryHistory:
        combined_query = f"{request.queryHistory}. {request.query}"

    if request.forceGeneral:
        yield AgentStatus(step_id=1, message="Processing general query...")
        llm_service = get_llm_service()
        result = _handle_general_query(combined_query, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    existing_code = request.existing_code or request.previousSQL
    is_edit = bool(existing_code and existing_code.strip() and _is_code_edit_request(request.query))

    from app.core.orchestrator.builtin_sql_generator import generate_sas_builtin
    from app.services.source_resolver import resolve_or_primary
    from app.services.stores.bundle import build_source_stores

    builtin_source = resolve_or_primary(request.source_id)
    stores = build_source_stores(builtin_source)
    for event in generate_sas_builtin(request, stores):
        if is_edit and isinstance(event, dict) and event.get("type") == "result":
            payload = event.get("payload")
            if isinstance(payload, dict) and payload.get("sql") and payload.get("success") is not False:
                payload["is_code_edit"] = True
                if not payload.get("explanation"):
                    payload["explanation"] = "Code updated based on your request."
        yield event


def _is_code_edit_request(query: str) -> bool:
    """Return True if the user message is asking to edit/modify previously generated code."""
    if not query or not query.strip():
        return False
    q = query.strip().lower()
    edit_phrases = [
        "change ", "replace ", "update the code", "in the generated code",
        "in the code", "modify the code", "edit the code", "fix the code",
        "change the ", "replace the ", "update the ", "change where", "replace where",
    ]
    return any(p in q for p in edit_phrases)


def _apply_python_code_edit(previous_code: str, user_edit_instruction: str, query_history: Optional[str], llm_service) -> str:
    """
    Ask the LLM to apply the user's edit to the previous code and return FULL executable code.
    Ensures the result is complete code that still answers the original request, not a snippet.
    """
    prompt = f"""### ROLE
You are an expert Python programmer. The user has previously been shown Python code and now wants a specific edit applied.

### CRITICAL RULES
1. Apply ONLY the change the user asked for. Do not add or remove unrelated logic.
2. You MUST return the COMPLETE, executable Python script—not a snippet or a diff.
3. The output must be valid Python that can run as-is (same structure: imports, engine, raw_connection, pd.read_sql, final_result_df, etc.).
4. Do NOT use markdown code blocks. Do NOT include any text before or after the code. Start with # comments or import.
5. Preserve the original goal of the script; the edit should only change what the user specified (e.g. a WHERE clause value).

### PREVIOUS PYTHON CODE
```python
{_strip_db_connection_injection(previous_code)}
```

### CONVERSATION CONTEXT (optional)
{query_history or "(none)"}

### USER'S EDIT REQUEST
{user_edit_instruction}

### YOUR TASK
Apply the user's requested change to the code above and output the ENTIRE modified Python script. The code must remain executable and still answer the original analysis question."""

    code = llm_service.chat(prompt, temperature=0.1)
    return _cleanup_python_code(code)


def generate_python_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    """
    Generate Python code using the same built-in pipeline as SQL generation:
    routing, pin validation, KB/precomputed fast paths, discovery, and bounded retry.
    """
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    combined_query = request.query
    if request.queryHistory:
        combined_query = f"{request.queryHistory}. {request.query}"

    if request.forceGeneral:
        yield AgentStatus(step_id=1, message="Processing general query...")
        llm_service = get_llm_service()
        result = _handle_general_query(combined_query, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    existing_code = request.existing_code or request.previousSQL
    is_edit = bool(existing_code and existing_code.strip() and _is_code_edit_request(request.query))

    from app.core.orchestrator.builtin_sql_generator import generate_python_builtin
    from app.services.source_resolver import resolve_or_primary
    from app.services.stores.bundle import build_source_stores

    builtin_source = resolve_or_primary(request.source_id)
    stores = build_source_stores(builtin_source)
    for event in generate_python_builtin(request, stores):
        if is_edit and isinstance(event, dict) and event.get("type") == "result":
            payload = event.get("payload")
            if isinstance(payload, dict) and payload.get("sql") and payload.get("success") is not False:
                payload["is_code_edit"] = True
                if not payload.get("explanation"):
                    payload["explanation"] = "Code updated based on your request."
        yield event


def regenerate_python_with_error_feedback(
    original_request: str,
    failed_code: str,
    error_message: str,
    schema_context: str,
    attempt_number: int
) -> str:
    """
    Regenerate Python code based on execution error feedback.
    
    Args:
        original_request: The user's original natural language request
        failed_code: The Python code that failed to execute
        error_message: The error message and traceback from execution
        schema_context: The database schema context used for original generation
        attempt_number: Which retry attempt this is (2-5)
    
    Returns:
        Regenerated Python code as a string
    """
    llm_service = get_llm_service()
    
    # Strip DB_CONNECTION_STRING from failed code to avoid sending sensitive data
    code_to_send = _strip_db_connection_injection(failed_code)
    
    prompt = f"""### ROLE
You are an expert Python Programmer debugging code execution failures.

### CONTEXT
A Python script was generated to answer a user's request, but it failed during execution.
Your task is to fix the code based on the error feedback.

**IMPORTANT**: This is retry attempt {attempt_number} of 5. Focus on fixing the specific error while still fulfilling the original user request.

### ORIGINAL USER REQUEST
{original_request}

### FAILED CODE
```python
{code_to_send}
```

### EXECUTION ERROR
```
{error_message}
```

### DATABASE SCHEMA
{schema_context}

### YOUR TASK
1. Analyze the error carefully - identify the root cause
2. Fix the specific issue in the code
3. **CRITICAL**: The fix must still address the original user request
4. **CRITICAL**: Do NOT change the goal - only fix the execution error
5. Return corrected Python code that will execute successfully

### COMMON ISSUES TO CHECK
- **Connection Issues**: Ensure `engine.raw_connection()` is used with try/finally pattern
- **SQL Syntax**: Check table names, column names match the schema exactly (case-sensitive)
- **Data Types**: Ensure proper type conversions for operations
- **Missing Imports**: Verify all required libraries are imported
- **Variable Names**: Check for typos in variable names
- **DataFrame Operations**: Ensure operations are valid for pandas DataFrames

### PYTHON CODE GUIDELINES (SAME AS BEFORE)
- **Connectivity:**
    - The application will inject `DB_CONNECTION_STRING` at runtime (you don't need to define it)
    - **MANDATORY PATTERN**: 
      ```python
      conn = engine.raw_connection()
      try:
          df = pd.read_sql("SELECT * FROM dbo.TableName", conn)
      finally:
          conn.close()
      ```
    - **DO NOT use context managers** (`with` statements for connections)
- **Data Retrieval:**
    - Use ONLY tables and columns from the DATABASE SCHEMA
    - Use exact table/column names (case-sensitive)
- **Final Output:**
    - Assign final result to `final_result_df`
    - Do NOT wrap in `def main():` function

### OUTPUT FORMAT
Return ONLY the corrected Python code:
- Start with # comments explaining the fix
- Include all imports
- Use the MANDATORY connection pattern
- No markdown blocks, no shell commands, no plain text explanations
- Just executable Python code

**Example Format:**
# Fixed: Corrected table name from 'products' to 'dbo.Products'
# Fixed: Added missing import for datetime
import pandas as pd
import sqlalchemy
from datetime import datetime
# ... rest of corrected code ...
"""
    
    # Generate fixed code
    fixed_code = llm_service.chat(prompt, temperature=0.1)
    
    # Clean up the generated code
    fixed_code = _cleanup_python_code(fixed_code)
    
    return fixed_code


def _strip_db_connection_injection(code: str) -> str:
    """
    Remove the injected DB_CONNECTION_STRING value from code before sending to LLM.
    Keeps the variable reference but removes the actual connection string.
    
    Args:
        code: Python code that may contain injected connection string
    
    Returns:
        Code with DB_CONNECTION_STRING reference preserved but value stripped
    """
    if not code:
        return code
    
    # Pattern to match DB_CONNECTION_STRING assignment (keep the pattern, remove the value)
    # This regex looks for lines like: DB_CONNECTION_STRING = "mssql+pyodbc://..."
    # We'll replace the value with a placeholder comment
    
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Check if this line contains DB_CONNECTION_STRING assignment
        if 'DB_CONNECTION_STRING' in line and '=' in line:
            # If it's a comment showing the example format, keep it
            if line.strip().startswith('#'):
                cleaned_lines.append(line)
            # If it's an actual assignment, replace with comment
            elif re.match(r'\s*DB_CONNECTION_STRING\s*=', line):
                cleaned_lines.append('# DB_CONNECTION_STRING will be injected at runtime')
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)
