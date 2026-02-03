"""
Code Advisor Service - Provides code review, optimization, and debugging advice
for SQL, R, SAS, and Python code.
"""

import json
import re
import logging
from typing import Optional, Generator, Union, Dict
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus
from app.services.llm_service import get_llm_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CodeAdvisorContext(BaseModel):
    """Context information for code advisor analysis."""
    extracted_code: str
    detected_language: str  # "sql" | "r" | "sas" | "python" | "unsupported"
    request_type: str       # "review" | "optimize" | "bug_fix" | "explain" | "refactor" | "general"
    is_supported: bool


def build_advisor_prompt(message: str) -> str:
    """
    Build single-shot optimization prompt for code analysis.
    
    Args:
        message: Original user message containing code
        
    Returns:
        Formatted prompt for LLM
    """
    return f"""Act as an expert polyglot developer. The user will provide code (SQL, Python, R, or SAS) for you to analyze and optimize.

Your task:
1. **Identify** the language/dialect and extract the code from the user's message
2. **Identify** the primary bottlenecks (e.g., I/O overhead, memory leaks, non-vectorized operations, or poor query execution plans)
3. **Refactor** the code for maximum performance, ensuring it remains readable and maintains identical logic/output
4. **Explain** the specific optimizations made using language-specific best practices (e.g., Vectorization in Python/R, Hash Joins in SAS, or SARGability and CTEs in SQL)
5. **List** any environmental or structural recommendations (like indexing or hardware considerations) that would further enhance performance

**CRITICAL FORMATTING RULE:**
When providing optimized code, you MUST wrap it in a proper markdown code block using THREE backticks (```), like this example:

```sql
SELECT * FROM table;
```

Do NOT use any other format. The code block must start with three backticks followed by the language name (sql/python/r/sas).

**User's message:**
{message}

Please provide your analysis and optimized code below:"""


def generate_code_advice(message: str) -> str:
    """
    Generate code advice using LLM in one shot.
    
    Args:
        message: Original user message containing code
        
    Returns:
        LLM-generated advice
    """

    try:
        llm_service = get_llm_service()
        user_prompt = build_advisor_prompt(message)
        
        # Use system message to enforce markdown code block formatting
        system_message = "You are a code optimization expert. When providing optimized code, you MUST wrap it in markdown code blocks using three backticks (```) followed by the language identifier (sql, python, r, or sas). This is MANDATORY."
        
        # Use chat_completion to preserve code block formatting (chat() strips backticks)
        advice = llm_service.chat_completion(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        
        # 🔍 DEBUG: Log raw LLM output
        import sys
        print("\n" + "=" * 80, flush=True)
        print("🔍 RAW LLM OUTPUT (first 800 chars):", flush=True)
        print(advice[:800], flush=True)
        print(f"🔍 Contains ```: {('```' in advice)}", flush=True)
        print(f"🔍 Total length: {len(advice)} chars", flush=True)
        print("=" * 80 + "\n", flush=True)
        sys.stdout.flush()
        
        # Return advice unchanged - frontend will handle code block extraction
        return advice
        
    except Exception as e:
        logger.error(f"Error generating advice: {e}")
        return f"I encountered an error while analyzing your code: {str(e)}. Please try again or rephrase your request."


def generate_code_advisor_for_request(request: GenerateSQLRequest) -> Generator[Union[AgentStatus, Dict], None, None]:
    """
    Main orchestrator for Code Advisor feature.
    One-shot approach: send user message directly to LLM without preprocessing.
    
    Args:
        request: GenerateSQLRequest with user query
        
    Yields:
        AgentStatus updates and final result
    """
    message = request.query
    
    # Step 1: Generate optimization advice (single shot - no extraction)
    yield AgentStatus(step_id=1, message="Analyzing your code...", type="status")
    
    advice = generate_code_advice(message)
    
    # Step 2: Return result
    response = GenerateSQLResponse(
        sql="",  # No SQL generation for advisor mode
        explanation=advice,
        query_type="code_advisor",
        context_text=""
    )
    
    yield {"type": "result", "payload": response}
    yield {"type": "done"}
