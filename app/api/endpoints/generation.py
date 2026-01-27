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

from app.services.visualization_service import VisualizationService

@router.post("/execute-python", response_model=ExecutePythonResponse)
async def execute_python_endpoint(request: ExecutePythonRequest, api_key: str = Depends(verify_api_key)):
    """
    Executes Python code and returns the output and any results.
    automatically appends a chart recommendation if a DataFrame is produced.
    """
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
                
        # 2. Execute Code
        result = execute_python_code(request.code, exec_context)
        
        # Initialize recommendation (will be set if visualization is possible)
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
                    recommendation = viz_service.get_chart_recommendation(df, request.code)
                except Exception as viz_err:
                    logger.error(f"Visualization recommendation failed: {viz_err}")


        return ExecutePythonResponse(
            success=result["success"],
            output=result["output"],
            error=result["error"],
            results=result.get("results"),
            recommendation=recommendation,
            execution_time=0.0  # TODO: Measure time
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
