from fastapi import Header, HTTPException
from app.core.config import settings
from dotenv import dotenv_values
import os


def get_expected_api_key() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "../../.env")
    dotenv_key = None
    if os.path.exists(env_path):
        dotenv_key = dotenv_values(env_path).get("API_KEY")
    return dotenv_key or settings.API_KEY


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Verify API key from request header.
    
    Currently validates against a fixed API key from environment variable.
    Future enhancement: Validate against database of user-specific API keys.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: 401 if API key is invalid or missing
    """
    expected_key = get_expected_api_key()
    if x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return x_api_key


# Future enhancement: Database-based API key validation
# Uncomment and implement when user profile database is ready
"""
from app.services.user_service import get_user_by_api_key

async def verify_api_key_from_db(x_api_key: str = Header(..., alias="X-API-Key")):
    '''
    Verify API key against user profile database.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        User profile associated with the API key
        
    Raises:
        HTTPException: 401 if API key is invalid, expired, or user is inactive
    '''
    user = await get_user_by_api_key(x_api_key)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="API key is disabled"
        )
    
    if user.api_key_expired:
        raise HTTPException(
            status_code=401,
            detail="API key has expired"
        )
    
    return user
"""
