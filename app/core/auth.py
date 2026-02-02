from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from app.core.config import settings
from app.core.user_database import get_user_db
from app.services.auth_service import decode_access_token
from app.models.user_models import User
from dotenv import dotenv_values
import os


def get_expected_api_key() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "../../.env")
    dotenv_key = None
    if os.path.exists(env_path):
        dotenv_key = dotenv_values(env_path).get("API_KEY")
    return dotenv_key or settings.API_KEY


# Security scheme for bearer token
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_user_db)
) -> Optional[User]:
    """
    Get current user from JWT token or API key (optional).
    
    Supports three authentication methods:
    1. JWT Bearer token (Authorization: Bearer <token>)
    2. User-specific API key (X-API-Key: <user_api_key>)
    3. Legacy system API key (X-API-Key: <system_api_key>)
    
    Returns:
        User object if authenticated, None otherwise
    """
    # Try JWT token first
    if credentials:
        token_data = decode_access_token(credentials.credentials)
        if token_data:
            from app.services.user_service import get_user_by_id
            user = get_user_by_id(db, token_data.user_id)
            if user and user.is_active:
                return user
    
    # Try user-specific API key
    if x_api_key:
        from app.services.user_service import get_user_by_api_key
        user = get_user_by_api_key(db, x_api_key)
        if user and user.is_active:
            return user
        
        # Fall back to legacy system API key
        expected_key = get_expected_api_key()
        if x_api_key == expected_key:
            # Legacy authentication - no user object, just pass through
            return None
    
    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_user_db)
) -> User:
    """
    Get current user from JWT token or API key (required).
    
    Supports three authentication methods:
    1. JWT Bearer token (Authorization: Bearer <token>)
    2. User-specific API key (X-API-Key: <user_api_key>)
    3. Legacy system API key (X-API-Key: <system_api_key>) - DEPRECATED
    
    Returns:
        User object
        
    Raises:
        HTTPException: 401 if not authenticated
    """
    user = await get_current_user_optional(credentials, x_api_key, db)
    
    # Check legacy system API key if no user found
    if not user and x_api_key:
        expected_key = get_expected_api_key()
        if x_api_key == expected_key:
            # Legacy authentication accepted but warn in logs
            import logging
            logging.getLogger(__name__).warning(
                "Legacy system API key used. Please migrate to user-based authentication."
            )
            raise HTTPException(
                status_code=401,
                detail="Legacy API key authentication requires user migration. Please contact administrator."
            )
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication credentials"
        )
    
    return user


async def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify current user is an active administrator.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User object if user is admin
        
    Raises:
        HTTPException: 403 if user is not an admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions. Admin access required."
        )
    
    return current_user


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Legacy API key verification (backward compatibility).
    
    DEPRECATED: Use get_current_user instead.
    
    Currently validates against a fixed API key from environment variable.
    
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
