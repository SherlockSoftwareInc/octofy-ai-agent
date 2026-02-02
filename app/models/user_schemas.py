"""
Pydantic schemas for user management API.

Defines request/response models for authentication and user operations.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime


# ============================================================================
# Authentication Schemas
# ============================================================================

class LoginRequest(BaseModel):
    """User login request."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """User login response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: int
    username: str
    role: str


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    role: Literal["admin", "user"] = "user"


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=6)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response (public info)."""
    id: int
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(UserResponse):
    """Schema for detailed user info including API key."""
    api_key: str


class UserListResponse(BaseModel):
    """Schema for listing users."""
    users: List[UserResponse]
    total: int


# ============================================================================
# Conversation Schemas
# ============================================================================

class Message(BaseModel):
    """Single message in a conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""
    title: Optional[str] = Field(None, max_length=255)
    messages: List[Message] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""
    title: Optional[str] = Field(None, max_length=255)
    messages: Optional[List[Message]] = None


class ConversationResponse(BaseModel):
    """Schema for conversation response."""
    id: int
    user_id: int
    title: Optional[str]
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ConversationListItem(BaseModel):
    """Schema for conversation list item (without full messages)."""
    id: int
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_preview: Optional[str] = None  # First 100 chars of last message


class ConversationListResponse(BaseModel):
    """Schema for listing conversations."""
    conversations: List[ConversationListItem]
    total: int


# ============================================================================
# Admin Schemas
# ============================================================================

class AdminUserCreate(UserCreate):
    """Admin schema for creating users with role assignment."""
    role: Literal["admin", "user"] = "user"


class AdminUserUpdate(UserUpdate):
    """Admin schema for updating users including role."""
    role: Optional[Literal["admin", "user"]] = None


class ApiKeyRegenerateResponse(BaseModel):
    """Response after regenerating API key."""
    api_key: str
    message: str = "API key regenerated successfully"
