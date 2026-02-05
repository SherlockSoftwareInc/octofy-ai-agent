from typing import Any, Dict, List, Optional
import sys
import io
import re
import sqlalchemy
import pandas as pd
import json
import traceback
import logging
import time

logger = logging.getLogger(__name__)

# Import workflow services
try:
    from app.services.profiling_service import ProfilingService
    from app.services.insight_service import InsightService
    WORKFLOW_SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Workflow services not available: {e}")
    WORKFLOW_SERVICES_AVAILABLE = False

# Thresholds for data visualization
MAX_ROWS = 200
MAX_COLS = 15


def _sanitize_code(code: str) -> str:
    """
    Sanitize code before execution by removing common LLM artifacts:
    - Markdown code blocks (```python...``` or '''python...''')
    - Shell command prefixes
    """
    if not code:
        return code
    
    code = code.strip()
    
    # Remove markdown code blocks with backticks
    code = re.sub(r'^```python\s*\n?', '', code, flags=re.IGNORECASE)
    code = re.sub(r'^```\s*\n?', '', code)
    code = re.sub(r'\n?```$', '', code)
    
    # Remove markdown-style blocks with triple single quotes ('''python ... ''')
    code = re.sub(r"^'''python\s*\n?", '', code, flags=re.IGNORECASE)
    code = re.sub(r"^'''\s*\n?", '', code)
    code = re.sub(r"\n?'''$", '', code)
    
    # Remove markdown-style blocks with triple double quotes (\"\"\"python ... \"\"\")
    code = re.sub(r'^"""python\s*\n?', '', code, flags=re.IGNORECASE)
    code = re.sub(r'^"""\s*\n?', '', code)
    code = re.sub(r'\n?"""$', '', code)
    
    # Remove shell command prefixes
    lines = code.split('\n')
    if lines:
        first_line = lines[0].strip()
        # Check if first line is a shell command to run python
        if re.match(r'^python[3]?\s+(-[a-z]+\s+)?["\']?', first_line, re.IGNORECASE):
            lines = lines[1:]
        elif re.match(r'^[$%>]\s*python', first_line, re.IGNORECASE):
            lines = lines[1:]
    
    return '\n'.join(lines).strip()

def get_chart_category(df: pd.DataFrame) -> tuple:
    """
    Classifies a DataFrame to determine appropriate chart types.
    
    Args:
        df: The pandas DataFrame to classify
        
    Returns:
        tuple: (category, allowed_charts, message)
            - category: "2d_data", "3d_data", "no_chart", or "too_much_data"
            - allowed_charts: List of chart type strings
            - message: User-friendly explanation (empty if charts are available)
    """
    rows, cols = df.shape
    
    # Threshold checks
    if rows > MAX_ROWS or cols > MAX_COLS:
        return (
            "too_much_data",
            [],
            "This dataset is too large to visualize effectively. Please filter or aggregate the data."
        )
    
    # Analyze column types
    text_columns = df.select_dtypes(include=['object', 'string']).columns.tolist()
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    
    # Rule: Multiple text columns = No Chart
    if len(text_columns) > 1:
        return (
            "no_chart",
            [],
            "This dataset is best viewed as a table."
        )
    
    # Rule: 2D Data (1 Category, 1 Number)
    if len(text_columns) == 1 and len(numeric_columns) == 1:
        return (
            "2d_data",
            ["column", "line", "pie", "treemap", "funnel"],
            ""
        )
    
    # Rule: 3D Data (1 Category, Multiple Numbers)
    if len(text_columns) == 1 and len(numeric_columns) > 1:
        return (
            "3d_data",
            ["clustered column", "stacked column", "line"],
            ""
        )
    
    # Default: No chart for other combinations
    return (
        "no_chart",
        [],
        "This dataset is best viewed as a table."
    )

def execute_python_code(
    code: str, 
    context: Optional[Dict[str, Any]] = None,
    enable_profiling: bool = True,
    user_query: str = ""
) -> Dict[str, Any]:
    """
    Executes Python code and captures stdout and any resulting DataFrame.
    
    Args:
        code: The Python code to execute.
        context: Optional dictionary of variables to inject into the execution scope.
        enable_profiling: Whether to enable automatic data profiling and insight generation
        user_query: Original user query for context in insight generation
        
    Returns:
        Dict containing success status, output, error message, results (serialized DataFrames),
        data_profile (if enabled), and insights (if enabled).
    """
    
    start_time = time.time()
    
    # Sanitize code to remove LLM artifacts (markdown blocks, shell prefixes)
    code = _sanitize_code(code)
    
    # Create a buffer to capture stdout
    stdout_buffer = io.StringIO()
    original_stdout = sys.stdout
    
    # Prepare execution scope with proper globals
    # We need __builtins__ in globals for imports to work
    global_scope = {
        '__builtins__': __builtins__,
        'pd': pd,
        'json': json,
        'sqlalchemy': sqlalchemy,
    }
    local_scope = context.copy() if context else {}

    # Ensure pandas is available as pd in both global and local scope
    if 'pd' not in global_scope:
        global_scope['pd'] = pd
    if 'pd' not in local_scope:
        local_scope['pd'] = pd
    
    # Log the DB_CONNECTION_STRING if present for debugging
    # NOTE: This connection string uses Windows Authentication (Trusted_Connection=yes)
    # It is dynamically built from _data-source.md in the skills directory
    # Connection format: mssql+pyodbc:///?odbc_connect=Driver={...};Server=...;Database=...;Trusted_Connection=yes
    if 'DB_CONNECTION_STRING' in local_scope:
        # Mask the actual connection string for security in logs
        conn_str = local_scope['DB_CONNECTION_STRING']
        if isinstance(conn_str, str):
            masked = conn_str[:20] + '...' if len(conn_str) > 20 else conn_str
            logger.info(f"DB_CONNECTION_STRING injected into execution context: {masked}")
        
    execution_success = False
    error_message = None
    results = []
    structured_output = None
    
    try:
        sys.stdout = stdout_buffer
        
        # Execute the code with proper globals and locals
        exec(code, global_scope, local_scope)
        
        execution_success = True
        
        # Capture output early for fallback parsing
        output = stdout_buffer.getvalue()

        # Inspect local scope for DataFrames to serialize
        # We look for variables that are pandas DataFrames (or Series) and not starting with _
        for var_name, var_value in local_scope.items():
            if var_name.startswith('_'):
                continue
                
            # Convert Series to DataFrame
            if isinstance(var_value, pd.Series):
                var_value = var_value.to_frame()
                
            if isinstance(var_value, pd.DataFrame):
                # We limit to 1000 rows for performance/safety in this MVP
                df_head = var_value.head(1000).copy()
                
                # IMPORTANT: Reset index if it's meaningful (not a default RangeIndex).
                # This ensures groupby results (which have the grouping key as index) 
                # are properly serialized with their labels as columns.
                if not isinstance(df_head.index, pd.RangeIndex):
                    df_head = df_head.reset_index()
                
                # Handle bytes columns or values to avoid UnicodeDecodeError
                for col in df_head.columns:
                    if df_head[col].dtype == 'object':
                        # specific check to see if we have bytes to decode
                        df_head[col] = df_head[col].apply(lambda x: x.decode('utf-8', 'replace') if isinstance(x, bytes) else x)
                
                try:
                    json_str = df_head.to_json(orient='records', date_format='iso')
                except Exception:
                    # Fallback: convert entirely to string if specialized handling fails
                    json_str = df_head.astype(str).to_json(orient='records', date_format='iso')

                columns = list(df_head.columns)
                rows = json.loads(json_str)
                structured_payload = {
                    "columns": columns,
                    "data": rows
                }

                # Generate Visualization Configuration using classification engine
                category, allowed_charts, message = get_chart_category(df_head)
                viz_config = {
                    "category": category,
                    "allowed_charts": allowed_charts,
                    "message": message
                }

                # Generate chart_metadata for backward compatibility with ResultChart component
                chart_metadata = {
                    "type": "none",
                    "x_axis": None,
                    "y_axes": [],
                    "is_stacked": False
                }
                
                # Only generate chart_metadata if data is chartable
                if category in ["2d_data", "3d_data"]:
                    try:
                        # Use consistent column classification logic (same as visualization_service.py)
                        datetime_cols = []
                        numeric_cols = []
                        categorical_cols = []
                        
                        for col in df_head.columns:
                            # Check datetime first
                            if pd.api.types.is_datetime64_any_dtype(df_head[col]):
                                datetime_cols.append(col)
                            # Check numeric
                            elif pd.api.types.is_numeric_dtype(df_head[col]):
                                numeric_cols.append(col)
                            else:
                                categorical_cols.append(col)
                        
                        # Check if string columns might be dates
                        for col in categorical_cols[:]:
                            try:
                                sample = df_head[col].dropna().head(10)
                                if len(sample) > 0:
                                    pd.to_datetime(sample)
                                    datetime_cols.append(col)
                                    categorical_cols.remove(col)
                            except:
                                pass
                        
                        # Column chart: categorical X, numeric Y
                        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
                            chart_metadata["type"] = "column"
                            chart_metadata["x_axis"] = categorical_cols[0]
                            chart_metadata["y_axes"] = numeric_cols[:3]
                        elif len(datetime_cols) >= 1 and len(numeric_cols) >= 1:
                            chart_metadata["type"] = "line"
                            chart_metadata["x_axis"] = datetime_cols[0]
                            chart_metadata["y_axes"] = numeric_cols[:3]
                    except Exception as chart_err:
                        logger.warning(f"Failed to generate chart metadata: {chart_err}")

                results.append({
                    "name": var_name,
                    "type": "dataframe",
                    "data": structured_payload,
                    "rows": len(var_value),
                    "columns": columns,
                    "viz_config": viz_config,
                    "chart_metadata": chart_metadata
                })

                # Set structured output from the first dataframe encountered
                if structured_output is None:
                    structured_output = structured_payload

        # Fallback: If no DataFrames were found in the scope (e.g. because code was wrapped in main() and printed),
        # try to parse the stdout buffer as a DataFrame.
        if not results and output.strip():
            try:
                # Attempt to read whitespace-separated text
                # We use io.StringIO on the captured output
                df_parsed = pd.read_csv(io.StringIO(output), sep=r'\s+', engine='python')
                
                # Basic validation: must have at least 1 row and 2 columns to be useful, 
                # or 1 column if it's a list.
                if not df_parsed.empty and len(df_parsed.columns) > 0:
                     # Serialize consistent with the main logic
                    df_head = df_parsed.head(1000).copy()
                    
                    try:
                        json_str = df_head.to_json(orient='records', date_format='iso')
                    except Exception:
                        json_str = df_head.astype(str).to_json(orient='records', date_format='iso')

                    columns = list(df_head.columns)
                    rows = json.loads(json_str)
                    structured_payload = {
                        "columns": columns,
                        "data": rows
                    }

                    # Generate Visualization Configuration for fallback
                    category, allowed_charts, message = get_chart_category(df_head)
                    viz_config = {
                        "category": category,
                        "allowed_charts": allowed_charts,
                        "message": message
                    }

                    # Generate chart_metadata for backward compatibility
                    chart_metadata = {
                        "type": "none",
                        "x_axis": None,
                        "y_axes": [],
                        "is_stacked": False
                    }
                    
                    if category in ["2d_data", "3d_data"]:
                        try:
                            # Use consistent column classification logic (same as visualization_service.py)
                            datetime_cols = []
                            numeric_cols = []
                            categorical_cols = []
                            
                            for col in df_head.columns:
                                if pd.api.types.is_datetime64_any_dtype(df_head[col]):
                                    datetime_cols.append(col)
                                elif pd.api.types.is_numeric_dtype(df_head[col]):
                                    numeric_cols.append(col)
                                else:
                                    categorical_cols.append(col)
                            
                            # Check if string columns might be dates
                            for col in categorical_cols[:]:
                                try:
                                    sample = df_head[col].dropna().head(10)
                                    if len(sample) > 0:
                                        pd.to_datetime(sample)
                                        datetime_cols.append(col)
                                        categorical_cols.remove(col)
                                except:
                                    pass
                            
                            # Column chart: categorical X, numeric Y
                            if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
                                chart_metadata["type"] = "column"
                                chart_metadata["x_axis"] = categorical_cols[0]
                                chart_metadata["y_axes"] = numeric_cols[:3]
                            elif len(datetime_cols) >= 1 and len(numeric_cols) >= 1:
                                chart_metadata["type"] = "line"
                                chart_metadata["x_axis"] = datetime_cols[0]
                                chart_metadata["y_axes"] = numeric_cols[:3]
                        except Exception:
                            pass

                    results.append({
                        "name": "parsed_output_df", 
                        "type": "dataframe",
                        "data": structured_payload,
                        "rows": len(df_parsed),
                        "columns": columns,
                        "viz_config": viz_config,
                        "chart_metadata": chart_metadata
                    })
                    structured_output = structured_payload
                    logger.info("Successfully parsed stdout into a DataFrame fallback.")
            except Exception as parse_err:
                logger.warning(f"Failed to parse stdout fallback: {parse_err}")
                
    except Exception as e:
        error_message = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"Python execution error: {error_message}")
    finally:
        # Restore stdout
        sys.stdout = original_stdout
        
    output = stdout_buffer.getvalue()
    stdout_buffer.close()
    
    execution_time = time.time() - start_time
    
    # Initialize profiling outputs
    data_profile = None
    insights = []
    suggested_refinements = []
    
    # Perform data profiling and insight generation if enabled and successful
    if enable_profiling and execution_success and results and WORKFLOW_SERVICES_AVAILABLE:
        try:
            # Get the first DataFrame result for profiling
            first_result = results[0]
            if first_result.get("type") == "dataframe" and first_result.get("data"):
                # Convert back to DataFrame from structured data
                df_data = first_result["data"]["data"]
                
                # SECURITY: Check data size before loading into memory
                MAX_ROWS_FOR_PROFILING = 100000
                if len(df_data) > MAX_ROWS_FOR_PROFILING:
                    logger.warning(f"Dataset too large for profiling: {len(df_data)} rows (max: {MAX_ROWS_FOR_PROFILING})")
                    # Skip profiling for large datasets
                else:
                    df_for_profiling = pd.DataFrame(df_data)
                    
                    # Profile the DataFrame
                    profiling_service = ProfilingService()
                    data_profile = profiling_service.profile_dataframe(df_for_profiling)
                    logger.info(f"Generated data profile: {data_profile.profiling_level} level, "
                              f"{data_profile.row_count} rows, {data_profile.column_count} cols")
                    
                    # Generate insights
                    insight_service = InsightService()
                    insights = insight_service.generate_insights(
                        profile=data_profile,
                        user_query=user_query or "analyze data",
                        df_sample=df_for_profiling.head(10)
                    )
                    logger.info(f"Generated {len(insights)} insights")
                    
                    # Generate refinement suggestions
                    suggested_refinements = insight_service.suggest_refinements(
                    profile=data_profile,
                    insights=insights
                )
                logger.info(f"Generated {len(suggested_refinements)} refinement suggestions")
                
        except Exception as e:
            # Don't expose sensitive data in logs - only log exception type
            logger.error(f"Error during profiling/insight generation: {type(e).__name__}")
            logger.debug(f"Profiling error details: {str(e)}", exc_info=True)
            # Continue without profiling if it fails
    
    # Convert data_profile and insights to dicts for JSON serialization
    profile_dict = data_profile.model_dump() if data_profile else None
    insights_dicts = [insight.model_dump() for insight in insights]
    
    return {
        "success": execution_success,
        "output": structured_output if structured_output is not None else output,
        "error": error_message,
        "results": results,
        "execution_time": execution_time,
        "data_profile": profile_dict,
        "insights": insights_dicts,
        "suggested_refinements": suggested_refinements
    }
