"""
Initialize user database and create default admin account.

Run this script once after setting up PostgreSQL to create tables
and set up the default administrator account.

Usage:
    python scripts/init_user_db.py
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.user_database import init_user_db, SessionLocal
from app.models.user_models import User
from app.services.auth_service import hash_password
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_default_admin():
    """Create default administrator account if no users exist."""
    db = SessionLocal()
    
    try:
        # Check if any users exist
        user_count = db.query(User).count()
        
        if user_count > 0:
            logger.info(f"Database already has {user_count} user(s). Skipping default admin creation.")
            return False
        
        # Create default admin
        logger.info("Creating default administrator account...")
        
        default_username = "admin"
        default_password = "admin123"  # CHANGE THIS IN PRODUCTION!
        
        admin_user = User(
            username=default_username,
            email="admin@example.com",
            full_name="System Administrator",
            hashed_password=hash_password(default_password),
            role="admin",
            is_active=True,
            api_key=User.generate_api_key()
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        logger.info("=" * 80)
        logger.info("DEFAULT ADMINISTRATOR ACCOUNT CREATED")
        logger.info("=" * 80)
        logger.info(f"Username: {default_username}")
        logger.info(f"Password: {default_password}")
        logger.info(f"API Key: {admin_user.api_key}")
        logger.info("=" * 80)
        logger.info("⚠️  WARNING: Change the default password immediately after first login!")
        logger.info("=" * 80)
        
        return True
    
    except Exception as e:
        logger.error(f"Error creating default admin: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


def main():
    """Initialize database and create default admin."""
    try:
        logger.info("Initializing user database...")
        logger.info(f"PostgreSQL Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        logger.info(f"Database: {settings.POSTGRES_DB}")
        
        # Create tables
        init_user_db()
        logger.info("✅ Database tables created successfully")
        
        # Create default admin if needed
        created = create_default_admin()
        
        if created:
            logger.info("✅ User database initialization complete!")
        else:
            logger.info("✅ User database is already initialized")
    
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        logger.error(f"Please ensure PostgreSQL is running and credentials are correct")
        sys.exit(1)


if __name__ == "__main__":
    main()
