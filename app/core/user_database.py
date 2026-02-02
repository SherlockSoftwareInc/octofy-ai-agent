"""
PostgreSQL database connection for user management.

Separate from the main SQL Server database used for data querying.
This database stores user accounts, conversations, and API keys.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from typing import Generator

# Build PostgreSQL connection URL
POSTGRES_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

# Create SQLAlchemy engine
engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_user_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_user_db)):
            return db.query(User).all()
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_user_db():
    """
    Initialize the user database.
    Creates all tables defined in models.
    
    Should be called during application startup.
    """
    from app.models.user_models import User, Conversation  # Import here to avoid circular imports
    Base.metadata.create_all(bind=engine)
