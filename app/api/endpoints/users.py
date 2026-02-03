"""
User management API endpoints.

Provides authentication, user profile, and admin user management operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.user_database import get_user_db
from app.core.auth import get_current_user, get_current_active_admin
from app.models.user_models import User
from app.models.user_schemas import (
    LoginRequest, LoginResponse, UserResponse, UserDetailResponse,
    UserUpdate, UserListResponse, AdminUserCreate, AdminUserUpdate,
    ApiKeyRegenerateResponse
)
from app.services.user_service import (
    authenticate_user, get_user_by_id, get_users, get_user_count,
    create_user, update_user, admin_update_user, delete_user,
    regenerate_api_key
)
from app.services.auth_service import create_access_token

router = APIRouter()


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/auth/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    db: Session = Depends(get_user_db)
):
    """
    User login with username and password.
    
    Returns the user's unique API key that should be used for all subsequent requests.
    The API key is sent in the X-API-Key header.
    """
    user = authenticate_user(db, login_request.username, login_request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Return the user's API key (no JWT token)
    return LoginResponse(
        access_token=user.api_key,  # Return API key as access_token for frontend compatibility
        token_type="api-key",
        user=UserResponse.model_validate(user)
    )


@router.get("/auth/me", response_model=UserDetailResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's information including API key.
    """
    return UserDetailResponse.model_validate(current_user)


# ============================================================================
# User Profile Endpoints
# ============================================================================

@router.put("/users/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    Update current user's profile.
    
    Users can update their own email, full name, and password.
    """
    return update_user(db, current_user.id, user_update)


@router.post("/users/me/regenerate-api-key", response_model=ApiKeyRegenerateResponse)
async def regenerate_current_user_api_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    Regenerate API key for current user.
    
    WARNING: Old API key will be invalidated immediately.
    """
    new_api_key = regenerate_api_key(db, current_user.id)
    
    return ApiKeyRegenerateResponse(
        api_key=new_api_key,
        message="API key regenerated successfully. Please update your applications."
    )


# ============================================================================
# Admin User Management Endpoints
# ============================================================================

@router.get("/admin/users", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    List all users (admin only).
    
    Supports pagination with skip and limit parameters.
    """
    users = get_users(db, skip=skip, limit=limit)
    total = get_user_count(db)
    
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total
    )


@router.get("/admin/users/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: int,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Get detailed user information by ID (admin only).
    """
    user = get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserDetailResponse.model_validate(user)


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_create: AdminUserCreate,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Create a new user (admin only).
    
    Automatically generates an API key for the new user.
    """
    return create_user(db, user_create)


@router.put("/admin/users/{user_id}", response_model=UserResponse)
async def update_user_by_admin(
    user_id: int,
    user_update: AdminUserUpdate,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Update user information (admin only).
    
    Admins can update any user's information including role.
    """
    return admin_update_user(db, user_id, user_update)


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_admin(
    user_id: int,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Delete a user (admin only).
    
    WARNING: This will also delete all conversations associated with the user.
    """
    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    delete_user(db, user_id)


@router.post("/admin/users/{user_id}/regenerate-api-key", response_model=ApiKeyRegenerateResponse)
async def regenerate_user_api_key_by_admin(
    user_id: int,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Regenerate API key for any user (admin only).
    
    WARNING: Old API key will be invalidated immediately.
    """
    new_api_key = regenerate_api_key(db, user_id)
    
    return ApiKeyRegenerateResponse(
        api_key=new_api_key,
        message="API key regenerated successfully"
    )
