"""
SQLAlchemy models for user management.

Database Tables:
- users: User accounts with credentials and roles
- conversations: Chat conversation history stored as JSON
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.user_database import Base
import secrets

# Import UserActivity to ensure it's registered before relationships are built
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.activity_models import UserActivity


class User(Base):
    """
    User account model.
    
    Stores user credentials, role, and authentication information.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Role: 'admin' or 'user'
    role = Column(String(20), default="user", nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Auto-generated API key for programmatic access
    api_key = Column(String(64), unique=True, index=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    # UserActivity relationship - lazy loaded to avoid circular imports
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure random API key."""
        return secrets.token_urlsafe(48)  # 64 characters


class Conversation(Base):
    """
    Conversation history model.
    
    Stores complete chat conversations as JSON for easy retrieval.
    Each conversation belongs to a single user.
    """
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Conversation metadata
    title = Column(String(255), nullable=True)  # Auto-generated or user-provided title
    
    # Full conversation stored as JSON array of messages
    # Format: [{"role": "user", "content": "...", "timestamp": "...", ...extra_fields}, ...]
    messages = Column(JSON, nullable=False, default=list)
    
    # Extra conversation data (selectedObjects, planningContext, etc.)
    extra_data = Column(JSON, nullable=True, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title='{self.title}')>"
