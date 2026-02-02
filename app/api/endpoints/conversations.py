"""
Conversation management API endpoints.

Provides conversation history storage and retrieval for users.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.user_database import get_user_db
from app.core.auth import get_current_user
from app.models.user_models import User
from app.models.user_schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse,
    ConversationListResponse, ConversationListItem
)
from app.services.user_service import (
    get_user_conversations, get_user_conversation_count,
    get_conversation_by_id, create_conversation, update_conversation,
    delete_conversation, conversation_to_list_item
)

router = APIRouter()


# ============================================================================
# Conversation Endpoints
# ============================================================================

@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    List all conversations for the current user.
    
    Returns conversations sorted by most recently updated.
    Supports pagination with skip and limit parameters.
    """
    conversations = get_user_conversations(db, current_user.id, skip=skip, limit=limit)
    total = get_user_conversation_count(db, current_user.id)
    
    conversation_items = [conversation_to_list_item(conv) for conv in conversations]
    
    return ConversationListResponse(
        conversations=conversation_items,
        total=total
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    Get a specific conversation by ID.
    
    Returns the full conversation including all messages.
    Users can only access their own conversations.
    """
    conversation = get_conversation_by_id(db, conversation_id, current_user.id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse.model_validate(conversation)


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_new_conversation(
    conversation_create: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    Create a new conversation.
    
    Initialize with optional title and messages.
    """
    conversation = create_conversation(db, current_user.id, conversation_create)
    
    return ConversationResponse.model_validate(conversation)


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_endpoint(
    conversation_id: int,
    conversation_update: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    Update a conversation.
    
    Can update title and/or append/modify messages.
    Users can only update their own conversations.
    """
    conversation = update_conversation(db, conversation_id, current_user.id, conversation_update)
    
    return ConversationResponse.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_user_db)
):
    """
    Delete a conversation.
    
    Permanently removes the conversation and all its messages.
    Users can only delete their own conversations.
    """
    delete_conversation(db, conversation_id, current_user.id)
