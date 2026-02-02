"""
User service for user management operations.

Handles user CRUD operations, authentication, and conversation management.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from fastapi import HTTPException, status

from app.models.user_models import User, Conversation
from app.models.user_schemas import (
    UserCreate, UserUpdate, AdminUserCreate, AdminUserUpdate,
    ConversationCreate, ConversationUpdate, ConversationListItem,
    Message
)
from app.services.auth_service import hash_password, verify_password


# ============================================================================
# User Operations
# ============================================================================

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_api_key(db: Session, api_key: str) -> Optional[User]:
    """Get user by API key."""
    return db.query(User).filter(User.api_key == api_key).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get all users with pagination."""
    return db.query(User).offset(skip).limit(limit).all()


def get_user_count(db: Session) -> int:
    """Get total user count."""
    return db.query(User).count()


def create_user(db: Session, user_create: UserCreate) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user_create: User creation data
        
    Returns:
        Created user
        
    Raises:
        HTTPException: If username already exists
    """
    # Check if username already exists
    if get_user_by_username(db, user_create.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create user
    db_user = User(
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
        hashed_password=hash_password(user_create.password),
        role=user_create.role,
        api_key=User.generate_api_key()
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> User:
    """
    Update user information.
    
    Args:
        db: Database session
        user_id: User ID to update
        user_update: User update data
        
    Returns:
        Updated user
        
    Raises:
        HTTPException: If user not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields if provided
    if user_update.email is not None:
        db_user.email = user_update.email
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    if user_update.password is not None:
        db_user.hashed_password = hash_password(user_update.password)
    if user_update.is_active is not None:
        db_user.is_active = user_update.is_active
    
    db.commit()
    db.refresh(db_user)
    
    return db_user


def admin_update_user(db: Session, user_id: int, user_update: AdminUserUpdate) -> User:
    """
    Admin-level user update including role changes.
    
    Args:
        db: Database session
        user_id: User ID to update
        user_update: Admin user update data
        
    Returns:
        Updated user
        
    Raises:
        HTTPException: If user not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields if provided
    if user_update.email is not None:
        db_user.email = user_update.email
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    if user_update.password is not None:
        db_user.hashed_password = hash_password(user_update.password)
    if user_update.is_active is not None:
        db_user.is_active = user_update.is_active
    if user_update.role is not None:
        db_user.role = user_update.role
    
    db.commit()
    db.refresh(db_user)
    
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    """
    Delete a user.
    
    Args:
        db: Database session
        user_id: User ID to delete
        
    Returns:
        True if deleted
        
    Raises:
        HTTPException: If user not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.delete(db_user)
    db.commit()
    
    return True


def regenerate_api_key(db: Session, user_id: int) -> str:
    """
    Regenerate user's API key.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        New API key
        
    Raises:
        HTTPException: If user not found
    """
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db_user.api_key = User.generate_api_key()
    db.commit()
    db.refresh(db_user)
    
    return db_user.api_key


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username and password.
    
    Args:
        db: Database session
        username: Username
        password: Password
        
    Returns:
        User if authenticated, None otherwise
    """
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    
    # Update last login time
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return user


# ============================================================================
# Conversation Operations
# ============================================================================

def get_user_conversations(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50
) -> List[Conversation]:
    """Get all conversations for a user."""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_conversation_count(db: Session, user_id: int) -> int:
    """Get conversation count for a user."""
    return db.query(Conversation).filter(Conversation.user_id == user_id).count()


def get_conversation_by_id(db: Session, conversation_id: int, user_id: int) -> Optional[Conversation]:
    """Get conversation by ID (must belong to user)."""
    return (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )


def create_conversation(
    db: Session,
    user_id: int,
    conversation_create: ConversationCreate
) -> Conversation:
    """
    Create a new conversation.
    
    Args:
        db: Database session
        user_id: User ID
        conversation_create: Conversation creation data
        
    Returns:
        Created conversation
    """
    # Convert Pydantic Message models to dicts with JSON-serializable values
    messages_data = [msg.model_dump(mode='json') for msg in conversation_create.messages]
    
    db_conversation = Conversation(
        user_id=user_id,
        title=conversation_create.title,
        messages=messages_data
    )
    
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    
    return db_conversation


def update_conversation(
    db: Session,
    conversation_id: int,
    user_id: int,
    conversation_update: ConversationUpdate
) -> Conversation:
    """
    Update a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID (for permission check)
        conversation_update: Conversation update data
        
    Returns:
        Updated conversation
        
    Raises:
        HTTPException: If conversation not found or doesn't belong to user
    """
    db_conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not db_conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Update fields if provided
    if conversation_update.title is not None:
        db_conversation.title = conversation_update.title
    if conversation_update.messages is not None:
        messages_data = [msg.model_dump(mode='json') for msg in conversation_update.messages]
        db_conversation.messages = messages_data
    
    db.commit()
    db.refresh(db_conversation)
    
    return db_conversation


def delete_conversation(db: Session, conversation_id: int, user_id: int) -> bool:
    """
    Delete a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID (for permission check)
        
    Returns:
        True if deleted
        
    Raises:
        HTTPException: If conversation not found or doesn't belong to user
    """
    db_conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not db_conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    db.delete(db_conversation)
    db.commit()
    
    return True


def conversation_to_list_item(conversation: Conversation) -> ConversationListItem:
    """Convert Conversation model to ConversationListItem."""
    last_message_preview = None
    if conversation.messages:
        last_msg = conversation.messages[-1]
        content = last_msg.get("content", "")
        last_message_preview = content[:100] if len(content) > 100 else content
    
    return ConversationListItem(
        id=conversation.id,
        title=conversation.title,
        message_count=len(conversation.messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_message_preview=last_message_preview
    )
