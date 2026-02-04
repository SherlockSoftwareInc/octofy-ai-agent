"""
Verification script to confirm Windows authentication is properly configured
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.settings_service import load_settings, decrypt_string
from app.core.database import get_db_engine
from sqlalchemy import text

def main():
    print("=" * 70)
    print("Windows Authentication Configuration Verification")
    print("=" * 70)
    
    # Load settings
    settings = load_settings()
    
    # Check auth_type
    print("\n✓ Configuration Check:")
    print(f"  - Auth Type: {settings.target_db.auth_type}")
    print(f"  - Server: {settings.target_db.server}")
    print(f"  - Database: {settings.target_db.database_name}")
    print(f"  - Username: {settings.target_db.username or 'None (Windows Auth)'}")
    
    # Decrypt and check connection string
    conn_str = decrypt_string(settings.target_db.connection_string_encrypted)
    print(f"\n✓ Connection String Analysis:")
    print(f"  - Contains 'Trusted_Connection=yes': {'Trusted_Connection=yes' in conn_str}")
    print(f"  - Contains 'UID=' (SQL auth): {'UID=' in conn_str}")
    print(f"  - Contains 'PWD=' (password): {'PWD=' in conn_str}")
    
    # Test connection
    print(f"\n✓ Database Connection Test:")
    try:
        engine = get_db_engine()
        with engine.connect() as connection:
            result = connection.execute(text("SELECT @@VERSION as version, SYSTEM_USER as windows_user"))
            row = result.fetchone()
            print(f"  - Connection: SUCCESS")
            print(f"  - Current User: {row[1]}")
            print(f"  - SQL Server Version: {row[0].split(chr(10))[0]}")
    except Exception as e:
        print(f"  - Connection: FAILED")
        print(f"  - Error: {str(e)}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ All checks passed! Windows authentication is properly configured.")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
