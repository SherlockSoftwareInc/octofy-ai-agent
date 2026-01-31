from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus
from app.services.generation_service import generate_sql_for_request
from app.services.code_generation_service import generate_r_for_request, generate_sas_for_request, generate_python_for_request
from app.core.auth import verify_api_key
import traceback
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-sql")
async def generate_sql_endpoint(request: GenerateSQLRequest, api_key: str = Depends(verify_api_key)):
    def event_generator():
        try:
            for item in generate_sql_for_request(request, request.previousSQL, request.queryHistory):
                if isinstance(item, AgentStatus):
                    yield f"data: {json.dumps(item.model_dump())}\n\n"
                elif isinstance(item, dict) and item.get("type") == "result":
                    # Payload is a GenerateSQLResponse object
                    payload = item["payload"]
                    data = {
                        "type": "result",
                        "payload": payload.model_dump(by_alias=True)
                    }
                    yield f"data: {json.dumps(data)}\n\n"
        except Exception as e:
            logger.error(f"Error in generate_sql_endpoint: {str(e)}")
            logger.error(traceback.format_exc())
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

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

from app.services.visualization_service import VisualizationService

@router.post("/execute-python", response_model=ExecutePythonResponse)
async def execute_python_endpoint(request: ExecutePythonRequest, api_key: str = Depends(verify_api_key)):
    """
    Executes Python code and returns the output and any results.
    Automatically retries up to 5 times if execution fails, using LLM to fix errors.
    Appends a chart recommendation if a DataFrame is produced.
    """
    MAX_RETRY_ATTEMPTS = 5
    
    try:
        from app.services.settings_service import load_settings, decrypt_string
        
        # Validation: check for disallowed keywords
        if "sqlalchemy.create_engine(" in request.code and "DB_CONNECTION_STRING" not in request.code:
             logger.warning("User code contains create_engine but does not appear to use DB_CONNECTION_STRING")

        # 1. Retrieve & Decrypt Connection String
        settings = load_settings()
        encrypted_conn_str = settings.target_db.python_connection_string_encrypted
        
        # Create execution context if not exists
        exec_context = request.context or {}
        
        # Inject DB_CONNECTION_STRING if available
        decrypted_conn_str = None
        if encrypted_conn_str:
            try:
                decrypted_conn_str = decrypt_string(encrypted_conn_str)
                if decrypted_conn_str:
                    # Python connection string is already in SQLAlchemy URL format
                    # (e.g., mssql+pyodbc://user:pass@server,port/database?driver=...&param=value)
                    # No conversion needed!
                    
                    # Inject as a variable in the local scope instead of string replacement 
                    # This is safer and cleaner than string concatenation
                    exec_context['DB_CONNECTION_STRING'] = decrypted_conn_str
                        
            except Exception as e:
                logger.error(f"Failed to decrypt python connection string: {e}")
        
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
                        df, current_code, request.chart_type_override
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
        # Return error response
        return ExecutePythonResponse(
            success=False,
            output=None,
            error=str(e),
            results=None,
            recommendation=None,
            execution_time=0.0
        )


from app.models.schemas import ExecuteSQLRequest, ExecuteSQLResponse
from app.services.validation_service import execute_sql_query
from app.services.generation_service import regenerate_sql_with_error_feedback

@router.post("/execute-sql", response_model=ExecuteSQLResponse)
async def execute_sql_endpoint(request: ExecuteSQLRequest, api_key: str = Depends(verify_api_key)):
    """
    Executes SQL query and returns results with automatic retry on failure.
    Automatically retries up to 5 times if execution fails, using LLM to fix errors.
    Includes data profiling, insights, and chart recommendations.
    """
    MAX_RETRY_ATTEMPTS = 5
    
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
                            df, user_query or current_sql, request.chart_type_override
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
        # Return error response
        return ExecuteSQLResponse(
            success=False,
            output=None,
            error=str(e),
            results=None,
            recommendation=None,
            execution_time=0.0
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

