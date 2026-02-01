"""
Code Advisor Service - Provides code review, optimization, and debugging advice
for SQL, R, SAS, and Python code.
"""

import re
import json
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


def extract_code_from_message(message: str) -> Optional[str]:
    """
    Extract code from user message.
    1. First try to find markdown code blocks (```language ... ```)
    2. If not found, use LLM to detect and extract code
    
    Args:
        message: User's input message
        
    Returns:
        Extracted code or None if no code found
    """
    # Try to find markdown code blocks first
    # Pattern matches: ```language\ncode\n``` or ```\ncode\n```
    code_block_pattern = r'```(?:\w+)?\s*\n(.*?)```'
    matches = re.findall(code_block_pattern, message, re.DOTALL)
    
    if matches:
        # Return the first code block found, stripped of extra whitespace
        code = matches[0].strip()
        logger.info(f"Extracted code from markdown block ({len(code)} chars)")
        return code
    
    # No code block found, use LLM to extract code from plain text
    try:
        llm_service = get_llm_service()
        prompt = f"""Extract any code from this message. If there's SQL, Python, R, or SAS code present, return ONLY the code itself with no explanations or markdown.

If there's absolutely no code in the message, respond with exactly: NO_CODE_FOUND

Message:
{message}

Remember: Return ONLY the code, or NO_CODE_FOUND if there's no code."""
        
        response = llm_service.chat(prompt, temperature=0)
        
        if "NO_CODE_FOUND" in response.upper():
            logger.info("No code found by LLM extraction")
            return None
        
        # Clean up any markdown that might have been added
        code = response.strip()
        code = re.sub(r'^```\w*\s*\n', '', code)  # Remove opening ```
        code = re.sub(r'\n```\s*$', '', code)  # Remove closing ```
        code = code.strip()
        
        if code:
            logger.info(f"Extracted code via LLM ({len(code)} chars)")
            return code
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting code with LLM: {e}")
        return None


def extract_code_from_history(query_history: str) -> Optional[str]:
    """
    Extract the most recent code from conversation history.
    This allows follow-up questions without re-pasting code.
    
    Args:
        query_history: Conversation history string
        
    Returns:
        Most recent code found in history or None
    """
    if not query_history:
        return None
    
    # Split by user/AI turns and search in reverse order (most recent first)
    # History format is typically: "User: ... AI: ... User: ..."
    turns = query_history.split("\n")
    
    # Try to extract code from recent turns
    for i in range(len(turns) - 1, -1, -1):
        turn = turns[i]
        code = extract_code_from_message(turn)
        if code:
            logger.info(f"Found code in conversation history (turn {i})")
            return code
    
    return None


def detect_language_and_intent(code: str, message: str) -> CodeAdvisorContext:
    """
    Use LLM to detect programming language and user intent.
    
    Args:
        code: Extracted code to analyze
        message: Original user message for context
        
    Returns:
        CodeAdvisorContext with detection results
    """
    try:
        llm_service = get_llm_service()
        
        prompt = f"""Analyze this code and the user's message to determine:

1. Programming language (must be EXACTLY ONE of: sql, r, sas, python, unsupported)
2. What the user is asking for (choose ONE: review, optimize, bug_fix, explain, refactor, general)

Code:
```
{code}
```

User message:
{message}

Return ONLY a JSON object in this exact format (no markdown, no explanation):
{{"language": "sql", "intent": "review"}}"""
        
        response = llm_service.chat(prompt, temperature=0)
        
        # Clean any markdown formatting
        response = response.strip()
        response = re.sub(r'^```json\s*\n?', '', response)
        response = re.sub(r'\n?```\s*$', '', response)
        
        # Parse JSON response
        result = json.loads(response)
        language = result.get("language", "unsupported").lower()
        intent = result.get("intent", "general").lower()
        
        # Validate language
        supported_languages = ["sql", "r", "sas", "python"]
        is_supported = language in supported_languages
        
        logger.info(f"Detected language: {language}, intent: {intent}, supported: {is_supported}")
        
        return CodeAdvisorContext(
            extracted_code=code,
            detected_language=language,
            request_type=intent,
            is_supported=is_supported
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        # Fallback to unsupported
        return CodeAdvisorContext(
            extracted_code=code,
            detected_language="unsupported",
            request_type="general",
            is_supported=False
        )
    except Exception as e:
        logger.error(f"Error detecting language and intent: {e}")
        return CodeAdvisorContext(
            extracted_code=code,
            detected_language="unsupported",
            request_type="general",
            is_supported=False
        )


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

IMPORTANT: When providing the optimized code, you MUST wrap it in a markdown fenced code block using triple backticks. Use the following EXACT format:

```sql
SELECT column FROM table WHERE condition;
```

Do NOT omit the triple backticks! The opening must be three backticks followed by the language name (sql, python, r, or sas), and the closing must be three backticks on their own line.

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
        prompt = build_advisor_prompt(message)
        
        # Use slightly higher temperature for more natural conversation
        advice = llm_service.chat(prompt, temperature=0.3)
        
        logger.info(f"Generated advice ({len(advice)} chars)")
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
