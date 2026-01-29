from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

class SummarizeResultsRequest(BaseModel):
    user_request: str
    result_data: Any  # Can be list of dicts, or any serializable result
    chart_type: Optional[str] = None

class SummarizeResultsResponse(BaseModel):
    summary: str

@router.post("/summarize-results", response_model=SummarizeResultsResponse)
def summarize_results(payload: SummarizeResultsRequest):
    try:
        from app.services.llm_service import get_llm_service
        llm_service = get_llm_service()
        
        # Safely serialize result_data
        try:
            if isinstance(payload.result_data, str):
                data_str = payload.result_data
            else:
                data_str = json.dumps(payload.result_data, indent=2, default=str)
        except Exception:
            data_str = str(payload.result_data)
        
        # Truncate if too long
        if len(data_str) > 4000:
            data_str = data_str[:4000] + "\n... (truncated)"
        
        # Build prompt for summary
        prompt = f"""You are a data analyst assistant. The user asked: "{payload.user_request}"

Here are the results (tabular data):
{data_str}
"""
        if payload.chart_type and payload.chart_type != "none":
            prompt += f"\nChart type displayed: {payload.chart_type}"
        prompt += """

Please provide a concise summary of the key findings in bullet point format:
- Use 3-5 bullet points
- Each bullet should highlight one key insight from the data
- Be specific with numbers and percentages where relevant
- Keep each bullet to 1-2 sentences"""
        
        summary = llm_service.chat(prompt, temperature=0.3)
        return SummarizeResultsResponse(summary=summary)
        
    except Exception as e:
        logger.error(f"Summarize results failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to summarize results: {str(e)}")
