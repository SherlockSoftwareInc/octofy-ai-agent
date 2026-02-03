"""
Initialize activity logging table in the user database.

This script creates the user_activities table if it doesn't exist.
Run this after the initial user database setup.
"""
import sys
import os
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.user_database import engine, Base
from app.models.user_models import User, Conversation
from app.models.activity_models import UserActivity


def init_activity_table():
    """Create activity logging table."""
    print("🔧 Initializing activity logging table...")
    
    try:
        # Import all models to ensure they're registered with Base
        print("📋 Models registered:")
        print(f"  - User: {User.__tablename__}")
        print(f"  - Conversation: {Conversation.__tablename__}")
        print(f"  - UserActivity: {UserActivity.__tablename__}")
        
        # Create all tables (only creates if they don't exist)
        Base.metadata.create_all(bind=engine)
        
        print("\n✅ Activity logging table initialized successfully!")
        print("\nTable structure:")
        print("  user_activities:")
        print("    - id (primary key)")
        print("    - user_id (foreign key -> users.id)")
        print("    - activity_type (indexed)")
        print("    - activity_data (jsonb)")
        print("    - tokens_used")
        print("    - execution_time")
        print("    - success")
        print("    - error_message")
        print("    - ip_address")
        print("    - user_agent")
        print("    - created_at (indexed)")
        
        print("\n📊 Indexes created:")
        print("  - idx_user_activities_user_id ON user_id")
        print("  - idx_user_activities_type ON activity_type")
        print("  - idx_user_activities_created_at ON created_at DESC")
        
        print("\n🎉 Activity logging is now ready to use!")
        
    except Exception as e:
        print(f"\n❌ Error initializing activity table: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_activity_table()
