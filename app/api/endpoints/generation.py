from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus
from app.services.generation_service import generate_sql_for_request
from app.services.code_generation_service import generate_r_for_request, generate_sas_for_request, generate_python_for_request
from app.core.auth import verify_api_key
from app.models.user_models import User
from app.services.activity_service import log_sql_generation
from app.core.user_database import get_user_db
from sqlalchemy.orm import Session
import traceback
import logging
import json
import time

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-sql")
async def generate_sql_endpoint(
    request: GenerateSQLRequest, 
    http_request: Request,
    current_user: User = Depends(verify_api_key),
    db: Session = Depends(get_user_db)
):
    start_time = time.time()
    final_result = None
    error_occurred = False
    error_message = None
    
    def event_generator():
        nonlocal final_result, error_occurred, error_message
        try:
            for item in generate_sql_for_request(request, request.previousSQL, request.queryHistory):
                if isinstance(item, AgentStatus):
                    yield f"data: {json.dumps(item.model_dump())}\n\n"
                elif isinstance(item, dict) and item.get("type") == "result":
                    # Payload is a GenerateSQLResponse object
                    payload = item["payload"]
                    final_result = payload
                    data = {
                        "type": "result",
                        "payload": payload.model_dump(by_alias=True)
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(item, dict) and item.get("type") == "done":
                    # Forward done signal to frontend
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            logger.error(f"Error in generate_sql_endpoint: {str(e)}")
            logger.error(traceback.format_exc())
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Log activity after generation completes
            execution_time = time.time() - start_time
            log_sql_generation(
                db=db,
                user_id=current_user.id,
                query=request.query,
                sql=final_result.sql if final_result else None,
                tokens_used=final_result.usage.total_tokens if final_result and hasattr(final_result, 'usage') else None,
                execution_time=execution_time,
                success=not error_occurred,
                error_message=error_message,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent")
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/generate-r")
async def generate_r_endpoint(request: GenerateSQLRequest, api_key: str = Depends(verify_api_key)):
    def event_generator():
        try:
            for item in generate_r_for_request(request):
                if isinstance(item, AgentStatus):
                    yield f"data: {json.dumps(item.model_dump())}\n\n"
                elif isinstance(item, dict) and item.get("type") == "result":
                    payload = item["payload"]
                    data = {
                        "type": "result",
                        "payload": payload.model_dump(by_alias=True)
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(item, dict) and item.get("type") == "done":
                    # Forward done signal to frontend
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Error in generate_r_endpoint: {str(e)}")
            logger.error(traceback.format_exc())
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/generate-sas")
async def generate_sas_endpoint(request: GenerateSQLRequest, api_key: str = Depends(verify_api_key)):
    def event_generator():
        try:
            for item in generate_sas_for_request(request):
                if isinstance(item, AgentStatus):
                    yield f"data: {json.dumps(item.model_dump())}\n\n"
                elif isinstance(item, dict) and item.get("type") == "result":
                    payload = item["payload"]
                    data = {
                        "type": "result",
                        "payload": payload.model_dump(by_alias=True)
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(item, dict) and item.get("type") == "done":
                    # Forward done signal to frontend
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Error in generate_sas_endpoint: {str(e)}")
            logger.error(traceback.format_exc())
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/generate-python")
async def generate_python_endpoint(request: GenerateSQLRequest, api_key: str = Depends(verify_api_key)):
    def event_generator():
        try:
            for item in generate_python_for_request(request):
                if isinstance(item, AgentStatus):
                    yield f"data: {json.dumps(item.model_dump())}\n\n"
                elif isinstance(item, dict) and item.get("type") == "result":
                    payload = item["payload"]
                    data = {
                        "type": "result",
                        "payload": payload.model_dump(by_alias=True)
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(item, dict) and item.get("type") == "done":
                    # Forward done signal to frontend
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Error in generate_python_endpoint: {str(e)}")
            logger.error(traceback.format_exc())
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

from app.models.schemas import ExecutePythonRequest, ExecutePythonResponse
from app.services.execution_service import execute_python_code
from app.services.code_generation_service import regenerate_python_with_error_feedback
from app.services.activity_service import log_code_execution

from app.services.visualization_service import VisualizationService

@router.post("/execute-python", response_model=ExecutePythonResponse)
async def execute_python_endpoint(
    request: ExecutePythonRequest, 
    http_request: Request,
    current_user: User = Depends(verify_api_key),
    db: Session = Depends(get_user_db)
):
    """
    Executes Python code and returns the output and any results.
    Automatically retries up to 5 times if execution fails, using LLM to fix errors.
    Appends a chart recommendation if a DataFrame is produced.
    """
    MAX_RETRY_ATTEMPTS = 5
    start_time = time.time()
    
    try:
        from app.services.settings_service import load_settings, decrypt_string
        
        # Validation: check for disallowed keywords
        if "sqlalchemy.create_engine(" in request.code and "DB_CONNECTION_STRING" not in request.code:
             logger.warning("User code contains create_engine but does not appear to use DB_CONNECTION_STRING")

        # 1. Build Windows Authentication Connection String
        # Get connection info from _data-source.md
        from app.services.skills_service import get_skills_service
        import re
        import urllib.parse
        
        skills_service = get_skills_service()
        data_source = skills_service.load_primary_data_source()
        
        # Create execution context if not exists
        exec_context = request.context or {}
        
        # Build connection string using Windows Authentication
        decrypted_conn_str = None
        if data_source:
            try:
                # Extract server and database from data source metadata
                server_match = re.search(r'\*\*Server:\*\*\s*([^\n]+)', data_source.description or '')
                database_match = re.search(r'\*\*Database:\*\*\s*([^\n]+)', data_source.description or '')
                
                # Also check in the raw file content
                if not server_match or not database_match:
                    if hasattr(data_source, 'file_path') and data_source.file_path:
                        from pathlib import Path
                        file_content = Path(data_source.file_path).read_text(encoding='utf-8')
                        if not server_match:
                            server_match = re.search(r'\*\*Server:\*\*\s*([^\n]+)', file_content)
                        if not database_match:
                            database_match = re.search(r'\*\*Database:\*\*\s*([^\n]+)', file_content)
                
                if server_match and database_match:
                    server = server_match.group(1).strip()
                    database = database_match.group(1).strip()
                    
                    # Build ODBC connection string with Windows Authentication
                    driver = "ODBC Driver 17 for SQL Server"
                    odbc_conn_str = f"Driver={{{driver}}};Server={server};Database={database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes"
                    
                    # Convert to SQLAlchemy URL format for Python code
                    params = urllib.parse.quote_plus(odbc_conn_str)
                    decrypted_conn_str = f"mssql+pyodbc:///?odbc_connect={params}"
                    
                    # Inject as a variable in the local scope
                    exec_context['DB_CONNECTION_STRING'] = decrypted_conn_str
                    logger.info(f"Injected Windows Authentication connection string for Python execution")
                else:
                    logger.warning("Could not extract Server/Database from _data-source.md")
                        
            except Exception as e:
                logger.error(f"Failed to build Windows Authentication connection string: {e}")
        
        # Extract user_query and schema_context from context (needed for retry)
        user_query = exec_context.get("user_query", "") if exec_context else ""
        schema_context = exec_context.get("schema_context", "") if exec_context else ""
        
        # 2. Execute Code with Retry Loop
        current_code = request.code
        original_error = None
        attempt = 1
        result = None
        
        while attempt <= MAX_RETRY_ATTEMPTS:
            logger.info(f"Executing Python code (attempt {attempt}/{MAX_RETRY_ATTEMPTS})")
            
            result = execute_python_code(
                current_code, 
                exec_context,
                enable_profiling=request.enable_profiling or False,
                user_query=user_query
            )
            
            # Check if execution was successful
            if result["success"]:
                logger.info(f"Code execution succeeded on attempt {attempt}")
                break
            
            # Execution failed - capture original error on first attempt
            if attempt == 1:
                original_error = result["error"]
            
            # If we've reached max attempts, stop retrying
            if attempt >= MAX_RETRY_ATTEMPTS:
                logger.warning(f"Code execution failed after {MAX_RETRY_ATTEMPTS} attempts")
                break
            
            # Retry: regenerate code using error feedback
            logger.info(f"Retrying code generation (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS})")
            try:
                current_code = regenerate_python_with_error_feedback(
                    original_request=user_query,
                    failed_code=current_code,
                    error_message=result["error"],
                    schema_context=schema_context,
                    attempt_number=attempt + 1
                )
                
                # Re-inject DB_CONNECTION_STRING for next execution
                if decrypted_conn_str:
                    exec_context['DB_CONNECTION_STRING'] = decrypted_conn_str
                    
            except Exception as regen_error:
                logger.error(f"Error during code regeneration: {regen_error}")
                # If regeneration fails, stop retrying
                break
            
            attempt += 1
        
        # 3. Process Results and Generate Visualization
        recommendation = None
        
        if result["success"] and result.get("results"):
            # New Step: Visualization Consultant

            # 1. Identify valid dataframes
            dataframes = [r for r in result["results"] if r["type"] == "dataframe"]
            
            if dataframes:
                target_df_data = None
                
                # Check if 'final_result_df' exists
                final_df = next((d for d in dataframes if d["name"] == "final_result_df"), None)
                if final_df:
                    target_df_data = final_df["data"]
                else:
                    # Fallback to first dataframe
                    target_df_data = dataframes[0]["data"]

                try:
                    import pandas as pd

                    if isinstance(target_df_data, dict) and "data" in target_df_data:
                        rows = target_df_data.get("data", [])
                        columns = target_df_data.get("columns")
                        df = pd.DataFrame(rows)
                        if columns:
                            df = df[[col for col in columns if col in df.columns]]
                    else:
                        df = pd.DataFrame(target_df_data)

                    viz_service = VisualizationService()
                    recommendation = viz_service.get_chart_recommendation(
                        df, current_code, request.chart_type_override, request.preserved_x_axis, request.preserved_y_axis
                    )
                except Exception as viz_err:
                    logger.error(f"Visualization recommendation failed: {viz_err}")

        # 4. Build Response with Auto-Fix Information
        return ExecutePythonResponse(
            success=result["success"],
            output=result["output"],
            error=result["error"],
            results=result.get("results"),
            recommendation=recommendation,
            execution_time=result.get("execution_time", 0.0),
            data_profile=result.get("data_profile"),
            insights=result.get("insights", []),
            code=current_code if result["success"] and attempt > 1 else None,  # Only include if auto-fixed
            auto_fixed=result["success"] and attempt > 1,  # True if succeeded after retry
            fix_attempt=attempt,
            original_error=original_error if result["success"] and attempt > 1 else None
        )
    except Exception as e:
        logger.error(f"Error in execute_python_endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Log failed execution
        execution_time = time.time() - start_time
        log_code_execution(
            db=db,
            user_id=current_user.id,
            code_type="python",
            code=request.code,
            success=False,
            error_message=str(e),
            execution_time=execution_time,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        # Return error response
        return ExecutePythonResponse(
            success=False,
            output=None,
            error=str(e),
            results=None,
            recommendation=None,
            execution_time=0.0
        )
    finally:
        # Log successful execution
        if result and result.get("success"):
            execution_time = time.time() - start_time
            log_code_execution(
                db=db,
                user_id=current_user.id,
                code_type="python",
                code=current_code if attempt > 1 else request.code,
                success=True,
                execution_time=execution_time,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent")
            )


from app.models.schemas import ExecuteSQLRequest, ExecuteSQLResponse
from app.services.validation_service import execute_sql_query
from app.services.generation_service import regenerate_sql_with_error_feedback
from app.services.activity_service import log_sql_execution

@router.post("/execute-sql", response_model=ExecuteSQLResponse)
async def execute_sql_endpoint(
    request: ExecuteSQLRequest, 
    http_request: Request,
    current_user: User = Depends(verify_api_key),
    db: Session = Depends(get_user_db)
):
    """
    Executes SQL query and returns results with automatic retry on failure.
    Automatically retries up to 5 times if execution fails, using LLM to fix errors.
    Includes data profiling, insights, and chart recommendations.
    """
    MAX_RETRY_ATTEMPTS = 5
    start_time = time.time()
    
    try:
        # Extract context for retry
        user_query = request.context.get("user_query", "") if request.context else ""
        schema_context = request.context.get("schema_context", "") if request.context else ""
        
        # Retry loop
        current_sql = request.sql
        original_error = None
        attempt = 1
        result = None
        
        while attempt <= MAX_RETRY_ATTEMPTS:
            logger.info(f"Executing SQL query (attempt {attempt}/{MAX_RETRY_ATTEMPTS})")
            
            result = execute_sql_query(
                current_sql,
                timeout_seconds=request.timeout_seconds or 60,
                max_rows=request.max_rows or 10000,
                enable_profiling=request.enable_profiling or False,
                user_query=user_query
            )
            
            if result["success"]:
                logger.info(f"SQL execution succeeded on attempt {attempt}")
                break
            
            # Capture original error on first attempt
            if attempt == 1:
                original_error = result["error"]
            
            # Max attempts reached
            if attempt >= MAX_RETRY_ATTEMPTS:
                logger.warning(f"SQL execution failed after {MAX_RETRY_ATTEMPTS} attempts")
                break
            
            # Retry: regenerate SQL
            logger.info(f"Retrying SQL generation (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS})")
            try:
                current_sql = regenerate_sql_with_error_feedback(
                    original_request=user_query,
                    failed_sql=current_sql,
                    error_message=result["error"],
                    schema_context=schema_context,
                    attempt_number=attempt + 1
                )
            except Exception as regen_error:
                logger.error(f"Error during SQL regeneration: {regen_error}")
                break
            
            attempt += 1
        
        # Generate visualization recommendations for ALL result sets
        recommendations = []
        if result["success"] and result.get("results"):
            # Use VisualizationService for chart recommendation
            dataframes = [r for r in result["results"] if r["type"] == "sql_result"]
            
            if dataframes:
                viz_service = VisualizationService()
                
                # Generate recommendation for EACH result set
                for idx, df_result in enumerate(dataframes):
                    target_df_data = df_result["data"]
                    
                    try:
                        import pandas as pd
                        
                        if isinstance(target_df_data, dict) and "data" in target_df_data:
                            rows = target_df_data.get("data", [])
                            columns = target_df_data.get("columns")
                            df = pd.DataFrame(rows)
                            if columns:
                                df = df[[col for col in columns if col in df.columns]]
                        else:
                            df = pd.DataFrame(target_df_data)
                        
                        recommendation = viz_service.get_chart_recommendation(
                            df, user_query or current_sql, request.chart_type_override, request.preserved_x_axis, request.preserved_y_axis
                        )
                        recommendations.append(recommendation)
                    except Exception as viz_err:
                        logger.error(f"Visualization recommendation failed for result set {idx}: {viz_err}")
                        recommendations.append(None)
        
        # Use first recommendation for backward compatibility with single-result queries
        # But attach all recommendations to result sets
        recommendation = recommendations[0] if recommendations else None
        
        # Attach recommendations to each result set
        if result.get("results") and recommendations:
            for idx, result_item in enumerate(result["results"]):
                if idx < len(recommendations) and recommendations[idx]:
                    result_item["recommendation"] = recommendations[idx].model_dump()
        
        # Build response
        return ExecuteSQLResponse(
            success=result["success"],
            output=result["output"],
            error=result["error"],
            results=result.get("results"),
            recommendation=recommendation,
            execution_time=result.get("execution_time", 0.0),
            rows_affected=result.get("rows_affected"),
            data_profile=result.get("data_profile"),
            insights=result.get("insights", []),
            sql=current_sql if result["success"] and attempt > 1 else None,
            auto_fixed=result["success"] and attempt > 1,
            fix_attempt=attempt,
            original_error=original_error if result["success"] and attempt > 1 else None
        )
    except Exception as e:
        logger.error(f"Error in execute_sql_endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Log failed execution
        execution_time = time.time() - start_time
        log_sql_execution(
            db=db,
            user_id=current_user.id,
            sql=request.sql,
            success=False,
            error_message=str(e),
            execution_time=execution_time,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        # Return error response
        return ExecuteSQLResponse(
            success=False,
            output=None,
            error=str(e),
            results=None,
            recommendation=None,
            execution_time=0.0
        )
    finally:
        # Log successful execution
        if result and result.get("success"):
            execution_time = time.time() - start_time
            log_sql_execution(
                db=db,
                user_id=current_user.id,
                sql=current_sql,
                success=True,
                rows_affected=result.get("rows_affected"),
                execution_time=execution_time,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent")
            )


@router.post("/planning-summary")
async def generate_planning_summary_endpoint(
    request: dict,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate a structured summary from planning context.
    
    Request body: {"planning_context": {...}}
    Response: {"summary": "markdown formatted summary"}
    """
    try:
        from app.services.generation_service import generate_planning_summary
        
        planning_context = request.get("planning_context")
        if not planning_context:
            raise HTTPException(status_code=400, detail="planning_context required")
        
        summary = generate_planning_summary(planning_context)
        
        return {"summary": summary}
    
    except Exception as e:
        logger.error(f"Error generating planning summary: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code-advisor")
async def code_advisor_endpoint(request: GenerateSQLRequest, current_user: User = Depends(verify_api_key)):
    """
    Code Advisor - Get advice on SQL/R/SAS/Python code.
    
    Extracts code from query, detects language and intent,
    provides conversational advice for supported languages.
    
    Rate limited to 10 requests per minute per API key.
    """
    from app.core.rate_limiter import code_advisor_rate_limiter
    from app.services.code_advisor_service import generate_code_advisor_for_request
    
    # Check rate limit
    is_allowed, message = code_advisor_rate_limiter.is_allowed(current_user.api_key)
    
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=message
        )
    
    # Log rate limit info
    logger.info(f"Code Advisor request from {current_user.api_key[:8]}... - {message}")
    
    def event_generator():
        try:
            for item in generate_code_advisor_for_request(request):
                if isinstance(item, AgentStatus):
                    yield f"data: {json.dumps(item.model_dump())}\n\n"
                elif isinstance(item, dict) and item.get("type") == "result":
                    payload = item["payload"]
                    data = {
                        "type": "result",
                        "payload": payload.model_dump(by_alias=True)
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(item, dict) and item.get("type") == "done":
                    # Forward done signal to frontend
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Error in code_advisor_endpoint: {str(e)}")
            logger.error(traceback.format_exc())
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-RateLimit-Info": message,
        }
    )

