from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.core.user_database import get_user_db
from app.models.user_models import User


async def get_current_user_optional(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_user_db)
) -> Optional[User]:
    """
    Get current user from API key (optional).
    
    Uses user-specific API key (X-API-Key: <user_api_key>) to identify the user.
    
    Returns:
        User object if authenticated, None otherwise
    """
    # Authenticate using user-specific API key
    if x_api_key:
        from app.services.user_service import get_user_by_api_key
        user = get_user_by_api_key(db, x_api_key)
        if user and user.is_active:
            return user
    
    return None


async def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_user_db)
) -> User:
    """
    Get current user from API key (required).
    
    Uses user-specific API key (X-API-Key: <user_api_key>) to identify the user.
    Each user has a unique API key that identifies them.
    
    Returns:
        User object
        
    Raises:
        HTTPException: 401 if not authenticated or API key is invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Please provide X-API-Key header."
        )
    
    user = await get_current_user_optional(x_api_key, db)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
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


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_user_db)
) -> User:
    """
    Legacy API key verification (backward compatibility).
    
    Now validates user-specific API keys. For generation endpoints, all authenticated
    users are allowed. Admin endpoints should use get_current_active_admin instead.
    
    Args:
        x_api_key: API key from X-API-Key header
        db: Database session
        
    Returns:
        User object if authenticated
        
    Raises:
        HTTPException: 401 if API key is invalid or missing
    """
    from app.services.user_service import get_user_by_api_key
    
    user = get_user_by_api_key(db, x_api_key)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    
    return user
