"""
SQLAlchemy models for user activity tracking.

Database Table:
- user_activities: Logs user actions, queries, token usage, and performance metrics
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.user_database import Base


class UserActivity(Base):
    """
    User activity logging model.
    
    Tracks all user actions including:
    - SQL query generation and execution
    - Python code execution
    - R/SAS code generation
    - Conversation creation/updates
    - Login events
    - Token usage and execution metrics
    """
    __tablename__ = "user_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Activity classification
    activity_type = Column(String(50), nullable=False, index=True)
    # Types: 'sql_generated', 'sql_executed', 'python_executed', 'r_generated', 'sas_generated',
    #        'conversation_created', 'conversation_updated', 'login', 'api_key_regenerated'
    
    # Activity details stored as JSON for flexibility
    activity_data = Column(JSON, nullable=True)
    # Example: {"query": "Show me all users", "sql": "SELECT * FROM users", "table_override": ["users"]}
    
    # Performance metrics
    tokens_used = Column(Integer, nullable=True)  # LLM tokens consumed
    execution_time = Column(Float, nullable=True)  # Execution time in seconds
    
    # Status
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="activities")
    
    def __repr__(self):
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, type='{self.activity_type}', success={self.success})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "activity_type": self.activity_type,
            "activity_data": self.activity_data,
            "tokens_used": self.tokens_used,
            "execution_time": self.execution_time,
            "success": self.success,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
