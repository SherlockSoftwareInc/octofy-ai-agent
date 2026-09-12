from app.core.database import get_database_engine
from sqlalchemy import text
import re
import time
import logging
import traceback
import pandas as pd
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, date
import base64

logger = logging.getLogger(__name__)

# Import workflow services
try:
    from app.services.profiling_service import ProfilingService
    from app.services.insight_service import InsightService
    WORKFLOW_SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Workflow services not available: {e}")
    WORKFLOW_SERVICES_AVAILABLE = False

def validate_sql_with_db(sql: str, source_id: Optional[str] = None) -> tuple[bool, str, list[str]]:
    """
    Validate SQL using the database parser (SET NOEXEC ON).
    Returns (is_valid, error_message, missing_objects)
    """
    if not sql or sql.strip() == "":
        return False, "Empty SQL query generated", []
        
    engine = get_database_engine(source_id)
    error_msg = ""
    missing_objects = []
    is_valid = False

    try:
        with engine.connect() as connection:
            # We use a transaction to be safe, though NOEXEC shouldn't modify anything
            with connection.begin():
                # Enable parse-only mode
                connection.execute(text("SET NOEXEC ON"))
                try:
                    # Handle multi-statement scripts: split on GO if present,
                    # otherwise execute as a single batch (SQL Server handles
                    # DECLARE, #TempTables, and multiple SELECTs in one batch)
                    # Note: SET NOCOUNT ON is harmless under NOEXEC and helps
                    # validate scripts that include it.
                    connection.execute(text(sql))
                    is_valid = True
                except Exception as e:
                    raw_error = str(e)
                    # Extract the database error message (usually the last part of SQLAlchemy error)
                    # SQLAlchemy format: (pyodbc.ProgrammingError) ('42S02', "[42S02] [Microsoft][ODBC Driver 17 for SQL Server][SQL Server]Invalid object name 'dbo.NonExistentTable'. (208) (SQLExecDirectW)")
                    
                    # Simplify error message for LLM
                    error_lines = raw_error.split('\n')
                    simplified_error = raw_error
                    
                    # Try to extract the SQL Server error message
                    Match = re.search(r'\[SQL Server\](.*?)(\(\d+\))', raw_error)
                    if Match:
                        simplified_error = Match.group(1).strip()
                    
                    error_msg = simplified_error
                    
                    # Parse for specific items for discovery
                    # "Invalid object name 'xxx'." -> Missing table
                    # "Invalid column name 'xxx'." -> Missing column
                    
                    obj_match = re.search(r"Invalid object name '([^']+)'.", error_msg)
                    if obj_match:
                        missing_objects.append(obj_match.group(1))
                        
                    col_match = re.search(r"Invalid column name '([^']+)'.", error_msg)
                    if col_match:
                        missing_objects.append(col_match.group(1))
                        
                finally:
                    # Always turn NOEXEC OFF before returning connection to pool
                    # Although 'with connection' should handle cleanup, explicit is better
                    connection.execute(text("SET NOEXEC OFF"))
                    
    except Exception as e:
        # Connection error or other setup error
        return False, f"Database connection failed during validation: {str(e)}", []
         
    return is_valid, error_msg, missing_objects


def _serialize_sql_value(value: Any) -> Any:
    """
    Convert SQL-specific types to JSON-compatible format.
    
    Handles:
    - datetime/date -> ISO 8601 strings
    - Decimal -> float
    - bytes -> base64 string
    - None -> None
    """
    if value is None:
        return None
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, bytes):
        # Encode bytes as base64 for JSON compatibility
        return base64.b64encode(value).decode('utf-8')
    elif isinstance(value, (int, float, str, bool)):
        return value
    else:
        # Fallback: convert to string
        return str(value)


def _serialize_sql_results(cursor) -> Dict[str, Any]:
    """
    Converts pyodbc cursor results to JSON-compatible format.
    
    Returns:
        Dict with 'columns' (list of column names) and 'data' (list of row dicts)
    """
    if not cursor.description:
        # No result set (e.g., INSERT, UPDATE, DELETE without RETURNING)
        return {"columns": [], "data": []}
    
    columns = [column[0] for column in cursor.description]
    rows = []
    
    for row in cursor.fetchall():
        row_dict = {}
        for idx, column_name in enumerate(columns):
            row_dict[column_name] = _serialize_sql_value(row[idx])
        rows.append(row_dict)
    
    return {"columns": columns, "data": rows}


def _fetch_all_result_sets(cursor) -> List[Dict[str, Any]]:
    """
    Fetches all result sets from a query (handles multiple SELECT statements).
    
    Returns:
        List of result set dictionaries, each with 'columns' and 'data'
    """
    result_sets = []
    
    while True:
        result_set = _serialize_sql_results(cursor)
        if result_set["columns"]:  # Only add non-empty result sets
            result_sets.append(result_set)
        
        # Check if there are more result sets
        if not cursor.nextset():
            break
    
    return result_sets


def execute_sql_query(
    sql: str,
    timeout_seconds: int = 60,
    max_rows: int = 10000,
    enable_profiling: bool = True,
    user_query: str = "",
    source_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes SQL query and returns structured results with profiling and insights.
    
    Args:
        sql: T-SQL query to execute
        timeout_seconds: Query timeout in seconds (default 60)
        max_rows: Maximum rows to return (default 10000)
        enable_profiling: Enable data profiling and insights (default True)
        user_query: Original natural language query for insights context
        
    Returns:
        Dict with:
        - success: bool - Whether execution succeeded
        - output: Structured data (first result set)
        - error: Error message (if failed)
        - results: List of all result sets
        - execution_time: Duration in seconds
        - rows_affected: Number of rows in first result set
        - data_profile: Statistical profile (if enabled)
        - insights: AI-generated insights (if enabled)
    """
    start_time = time.time()
    
    if not sql or sql.strip() == "":
        return {
            "success": False,
            "output": None,
            "error": "Empty SQL query provided",
            "results": None,
            "execution_time": 0.0,
            "rows_affected": 0,
            "data_profile": None,
            "insights": []
        }
    
    engine = get_database_engine(source_id)
    execution_success = False
    error_message = None
    results = []
    structured_output = None
    rows_affected = 0
    
    try:
        # Get raw connection for pyodbc-level control
        raw_conn = engine.raw_connection()
        
        try:
            # Set query timeout at connection level (pyodbc requires this on connection, not cursor)
            raw_conn.timeout = timeout_seconds
            
            cursor = raw_conn.cursor()
            
            # Execute the SQL query
            cursor.execute(sql)
            
            # Fetch all result sets (handles multiple SELECT statements)
            result_sets = _fetch_all_result_sets(cursor)
            
            if result_sets:
                # Use first result set as primary output
                structured_output = result_sets[0]
                rows_affected = len(structured_output.get("data", []))
                
                # Limit rows if needed
                if rows_affected > max_rows:
                    logger.warning(f"Result set has {rows_affected} rows, limiting to {max_rows}")
                    structured_output["data"] = structured_output["data"][:max_rows]
                    rows_affected = max_rows
                
                # Build results list with metadata
                for idx, result_set in enumerate(result_sets):
                    result_data = result_set["data"][:max_rows] if len(result_set["data"]) > max_rows else result_set["data"]
                    
                    results.append({
                        "name": f"result_set_{idx + 1}",
                        "type": "sql_result",
                        "data": {"columns": result_set["columns"], "data": result_data},
                        "rows": len(result_data),
                        "columns": result_set["columns"]
                    })
            
            # Commit if there were any modifications
            raw_conn.commit()
            execution_success = True
            
        except Exception as e:
            error_message = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"SQL execution error: {error_message}")
            raw_conn.rollback()
        finally:
            cursor.close()
            raw_conn.close()
            
    except Exception as e:
        error_message = f"Database connection failed: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_message)
    
    execution_time = time.time() - start_time
    
    # Initialize profiling outputs
    data_profile = None
    insights = []
    
    # Perform data profiling and insight generation if enabled and successful
    from app.core.config import settings as app_settings
    profiling_allowed = bool(enable_profiling) and bool(app_settings.ENABLE_AI_DATA_ANALYSIS)
    if profiling_allowed and execution_success and structured_output and WORKFLOW_SERVICES_AVAILABLE:
        try:
            df_data = structured_output.get("data", [])
            
            # SECURITY: Check data size before loading into memory
            MAX_ROWS_FOR_PROFILING = 100000
            if len(df_data) > MAX_ROWS_FOR_PROFILING:
                logger.warning(f"Dataset too large for profiling: {len(df_data)} rows (max: {MAX_ROWS_FOR_PROFILING})")
            elif len(df_data) > 0:
                # Convert to DataFrame for profiling
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
                
        except Exception as e:
            # Don't expose sensitive data in logs
            logger.error(f"Error during profiling/insight generation: {type(e).__name__}")
            logger.debug(f"Profiling error details: {str(e)}", exc_info=True)
            # Continue without profiling if it fails
    
    # Convert data_profile and insights to dicts for JSON serialization
    profile_dict = data_profile.model_dump() if data_profile else None
    insights_dicts = [insight.model_dump() for insight in insights] if insights else []
    
    return {
        "success": execution_success,
        "output": structured_output,
        "error": error_message,
        "results": results,
        "execution_time": execution_time,
        "rows_affected": rows_affected,
        "data_profile": profile_dict,
        "insights": insights_dicts
    }
