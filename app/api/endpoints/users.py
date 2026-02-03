"""
User management API endpoints.

Provides authentication, user profile, and admin user management operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

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
    regenerate_api_key, get_user_conversation_count
)
from app.services.auth_service import create_access_token
from app.services.activity_service import (
    get_user_activities, get_activity_count, get_user_statistics,
    get_all_users_overview
)

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


# ============================================================================
# User Statistics & Activity Endpoints (Admin Only)
# ============================================================================

@router.get("/admin/users/{user_id}/stats")
async def get_user_stats(
    user_id: int,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to include in statistics"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Get comprehensive statistics for a specific user (admin only).
    
    Returns:
        - Total activities by type
        - Success/failure rates
        - Token usage
        - Execution time metrics
        - Recent activity timeline
        - Daily activity trend
    """
    # Verify user exists
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get conversation count
    conversation_count = get_user_conversation_count(db, user_id)
    
    # Get activity statistics
    stats = get_user_statistics(db, user_id, days=days)
    stats["conversation_count"] = conversation_count
    stats["user_info"] = UserResponse.model_validate(user).model_dump()
    
    return stats


@router.get("/admin/users/{user_id}/activities")
async def get_user_activity_log(
    user_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    activity_type: Optional[str] = Query(default=None, description="Filter by activity type"),
    success_only: Optional[bool] = Query(default=None, description="Filter by success status"),
    start_date: Optional[datetime] = Query(default=None, description="Filter activities after this date"),
    end_date: Optional[datetime] = Query(default=None, description="Filter activities before this date"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Get paginated activity log for a specific user (admin only).
    
    Supports filtering by:
    - activity_type: Type of activity (sql_generated, sql_executed, etc.)
    - success_only: Filter by success/failure
    - start_date/end_date: Date range filtering
    """
    # Verify user exists
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get activities
    activities = get_user_activities(
        db=db,
        user_id=user_id,
        skip=skip,
        limit=limit,
        activity_type=activity_type,
        success_only=success_only,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get total count for pagination
    total_count = get_activity_count(
        db=db,
        user_id=user_id,
        activity_type=activity_type,
        success_only=success_only,
        start_date=start_date,
        end_date=end_date
    )
    
    return {
        "activities": [activity.to_dict() for activity in activities],
        "total": total_count,
        "skip": skip,
        "limit": limit
    }


@router.get("/admin/users/overview")
async def get_users_overview_stats(
    days: int = Query(default=7, ge=1, le=365, description="Number of days to include"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    Get system-wide user statistics overview (admin only).
    
    Returns:
        - Total users
        - Active users
        - Total activities
        - Total tokens used
        - Top users by activity
        - Activity breakdown by type
    """
    # Get basic user counts
    total_users = get_user_count(db)
    
    # Get activity overview
    activity_overview = get_all_users_overview(db, days=days)
    
    return {
        "total_users": total_users,
        **activity_overview
    }

