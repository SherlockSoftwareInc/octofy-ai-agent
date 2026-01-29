"""
Input sanitization utilities for LLM prompts and user inputs.

Protects against prompt injection, limits input sizes, and escapes special characters.
"""
import re
from typing import List, Optional


# Maximum lengths for different input types
MAX_USER_QUERY_LENGTH = 500
MAX_CONVERSATION_HISTORY_LENGTH = 5000
MAX_COLUMN_NAME_LENGTH = 100
MAX_TABLE_NAME_LENGTH = 200


def sanitize_for_llm_prompt(
    text: str,
    max_length: int = MAX_USER_QUERY_LENGTH,
    allow_newlines: bool = False
) -> str:
    """
    Sanitize user input before inserting into LLM prompts.
    
    Protects against prompt injection by:
    - Escaping quote characters
    - Removing/replacing control characters
    - Truncating to safe length
    - Optionally removing newlines
    
    Args:
        text: User input to sanitize
        max_length: Maximum allowed length (default: 500)
        allow_newlines: Whether to preserve newline characters
        
    Returns:
        Sanitized text safe for LLM prompt insertion
        
    Examples:
        >>> sanitize_for_llm_prompt('Show sales "ignore instructions"')
        'Show sales \\"ignore instructions\\"'
        
        >>> sanitize_for_llm_prompt('A' * 1000, max_length=10)
        'AAAAAAAAAA...'
    """
    if not text:
        return ""
    
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    # Escape quote characters to prevent breaking out of prompt strings
    text = text.replace('"', '\\"').replace("'", "\\'")
    
    # Remove control characters except allowed ones
    if not allow_newlines:
        # Remove all control characters including newlines
        text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    else:
        # Keep newlines, tabs, but remove other control chars
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    
    # Remove common prompt injection patterns (defensive)
    injection_patterns = [
        r'ignore\s+(previous|all)\s+instructions',
        r'disregard\s+(previous|all)\s+instructions',
        r'system\s*:',
        r'<\s*system\s*>',
        r'\[INST\]',
        r'<\|im_start\|>',
    ]
    
    for pattern in injection_patterns:
        text = re.sub(pattern, '[removed]', text, flags=re.IGNORECASE)
    
    return text.strip()


def sanitize_column_name(column_name: str) -> Optional[str]:
    """
    Validate and sanitize column names to prevent SQL injection and code execution.
    
    Args:
        column_name: Column name from user input or data source
        
    Returns:
        Sanitized column name if valid, None if invalid
        
    Examples:
        >>> sanitize_column_name('user_id')
        'user_id'
        
        >>> sanitize_column_name('user; DROP TABLE users--')
        None
    """
    if not column_name or not isinstance(column_name, str):
        return None
    
    # Truncate to safe length
    if len(column_name) > MAX_COLUMN_NAME_LENGTH:
        return None
    
    # Only allow alphanumeric, underscore, and spaces
    # This matches most database column naming conventions
    safe_pattern = re.compile(r'^[a-zA-Z0-9_\s]+$')
    
    if not safe_pattern.match(column_name):
        return None
    
    return column_name.strip()


def sanitize_column_list(columns: List[str]) -> List[str]:
    """
    Sanitize a list of column names, filtering out invalid ones.
    
    Args:
        columns: List of column names to sanitize
        
    Returns:
        List of valid, sanitized column names
    """
    sanitized = []
    for col in columns:
        safe_col = sanitize_column_name(col)
        if safe_col:
            sanitized.append(safe_col)
    return sanitized


def sanitize_conversation_history(
    messages: List[str],
    max_messages: int = 10,
    max_total_length: int = MAX_CONVERSATION_HISTORY_LENGTH
) -> str:
    """
    Sanitize and format conversation history for LLM prompts.
    
    Args:
        messages: List of user messages from conversation
        max_messages: Maximum number of recent messages to include
        max_total_length: Maximum total character length
        
    Returns:
        Sanitized, formatted conversation history string
    """
    if not messages:
        return ""
    
    # Take only recent messages
    recent_messages = messages[-max_messages:]
    
    # Sanitize each message
    sanitized_messages = []
    total_length = 0
    
    for msg in recent_messages:
        # Sanitize with newlines allowed for conversation context
        sanitized = sanitize_for_llm_prompt(msg, max_length=500, allow_newlines=True)
        
        # Check if adding this message would exceed total length
        if total_length + len(sanitized) > max_total_length:
            break
        
        sanitized_messages.append(sanitized)
        total_length += len(sanitized)
    
    return "\n".join(f"- {msg}" for msg in sanitized_messages)


def sanitize_table_name(table_name: str) -> Optional[str]:
    """
    Validate and sanitize table names for SQL queries.
    
    Args:
        table_name: Table name to sanitize
        
    Returns:
        Sanitized table name if valid, None if invalid
        
    Examples:
        >>> sanitize_table_name('dbo.Users')
        'dbo.Users'
        
        >>> sanitize_table_name('Users; DELETE FROM passwords--')
        None
    """
    if not table_name or not isinstance(table_name, str):
        return None
    
    if len(table_name) > MAX_TABLE_NAME_LENGTH:
        return None
    
    # Allow schema.table format with brackets: [schema].[table] or schema.table
    safe_pattern = re.compile(r'^[\[\]a-zA-Z0-9_\.]+$')
    
    if not safe_pattern.match(table_name):
        return None
    
    return table_name.strip()


# Convenience function for common use case
def prepare_user_query_for_llm(query: str) -> str:
    """
    Convenience function to prepare user query for LLM prompt.
    
    This is the most common use case - sanitizing a user's natural language query
    before inserting it into an LLM prompt.
    
    Args:
        query: User's natural language query
        
    Returns:
        Sanitized query ready for LLM prompt
    """
    return sanitize_for_llm_prompt(query, max_length=MAX_USER_QUERY_LENGTH, allow_newlines=False)
