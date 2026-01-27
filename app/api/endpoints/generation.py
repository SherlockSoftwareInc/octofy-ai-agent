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
