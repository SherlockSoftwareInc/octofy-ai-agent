from typing import Any, Dict, List, Optional
import sys
import io
import pandas as pd
import json
import traceback
import logging

logger = logging.getLogger(__name__)

# Thresholds for data visualization
MAX_ROWS = 200
MAX_COLS = 15

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
            ["bar", "line", "column", "pie", "treemap", "funnel"],
            ""
        )
    
    # Rule: 3D Data (1 Category, Multiple Numbers)
    if len(text_columns) == 1 and len(numeric_columns) > 1:
        return (
            "3d_data",
            ["clustered column", "stacked column", "100% stacked bar", "line"],
            ""
        )
    
    # Default: No chart for other combinations
    return (
        "no_chart",
        [],
        "This dataset is best viewed as a table."
    )

def execute_python_code(code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes Python code and captures stdout and any resulting DataFrame.
    
    Args:
        code: The Python code to execute.
        context: Optional dictionary of variables to inject into the execution scope.
        
    Returns:
        Dict containing success status, output, error message, and results (serialized DataFrames).
    """
    
    # Create a buffer to capture stdout
    stdout_buffer = io.StringIO()
    original_stdout = sys.stdout
    
    # Prepare execution scope with proper globals
    # We need __builtins__ in globals for imports to work
    global_scope = {'__builtins__': __builtins__}
    local_scope = context.copy() if context else {}

    # Ensure pandas is available as pd in both global and local scope
    if 'pd' not in global_scope:
        global_scope['pd'] = pd
    if 'pd' not in local_scope:
        local_scope['pd'] = pd
    
    # Log the DB_CONNECTION_STRING if present for debugging
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
                        num_cols = df_head.select_dtypes(include=['number']).columns.tolist()
                        cat_cols = df_head.select_dtypes(include=['object', 'category', 'string']).columns.tolist()
                        
                        if len(cat_cols) >= 1 and len(num_cols) >= 1:
                            chart_metadata["type"] = "bar"
                            chart_metadata["x_axis"] = cat_cols[0]
                            chart_metadata["y_axes"] = num_cols
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
                            num_cols = df_head.select_dtypes(include=['number']).columns.tolist()
                            cat_cols = df_head.select_dtypes(include=['object', 'category', 'string']).columns.tolist()
                            if len(cat_cols) >= 1 and len(num_cols) >= 1:
                                chart_metadata["type"] = "bar"
                                chart_metadata["x_axis"] = cat_cols[0]
                                chart_metadata["y_axes"] = num_cols
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
    
    return {
        "success": execution_success,
        "output": structured_output if structured_output is not None else output,
        "error": error_message,
        "results": results
    }
