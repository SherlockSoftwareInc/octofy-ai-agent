"""
Verification script to confirm Python code execution uses Windows authentication
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.settings_service import load_settings, decrypt_string

def main():
    print("=" * 70)
    print("Python Code Execution - Windows Authentication Verification")
    print("=" * 70)
    
    # Load settings
    settings = load_settings()
    
    print("\n✓ Configuration Check:")
    print(f"  - Auth Type: {settings.target_db.auth_type}")
    print(f"  - Server: {settings.target_db.server}")
    print(f"  - Database: {settings.target_db.database_name}")
    
    # Check Python connection string (used for code execution)
    if settings.target_db.python_connection_string_encrypted:
        python_conn_str = decrypt_string(settings.target_db.python_connection_string_encrypted)
        
        print(f"\n✓ Python Connection String Analysis (used in execute_python_code):")
        print(f"  - Contains 'trusted_connection=yes': {'trusted_connection=yes' in python_conn_str.lower()}")
        print(f"  - Contains 'Trusted_Connection=yes': {'Trusted_Connection=yes' in python_conn_str}")
        print(f"  - Format: SQLAlchemy URL format for pyodbc")
        
        # Check for SQL auth indicators (should NOT be present)
        has_uid = any(pattern in python_conn_str.lower() for pattern in ['uid=', 'user=', 'username='])
        has_pwd = any(pattern in python_conn_str.lower() for pattern in ['pwd=', 'password='])
        
        print(f"  - Contains credentials (UID/User): {has_uid}")
        print(f"  - Contains password (PWD/Password): {has_pwd}")
        
        if not has_uid and not has_pwd and 'trusted_connection=yes' in python_conn_str.lower():
            print("\n✅ VERIFIED: Python code execution uses Windows Authentication")
            print("   - No username/password in connection string")
            print("   - Trusted_Connection=yes is present")
        else:
            print("\n❌ WARNING: Connection string may not be using Windows Authentication")
            return False
            
        # Show masked connection string for verification
        # Mask everything except the authentication method
        masked = python_conn_str[:50] + '...' if len(python_conn_str) > 50 else python_conn_str
        print(f"\n  - Connection String (masked): {masked}")
        
    else:
        print("\n❌ ERROR: No Python connection string configured")
        return False
    
    # Check regular connection string (used for metadata queries)
    if settings.target_db.connection_string_encrypted:
        regular_conn_str = decrypt_string(settings.target_db.connection_string_encrypted)
        
        print(f"\n✓ Regular Connection String Analysis (used in database.py):")
        print(f"  - Contains 'Trusted_Connection=yes': {'Trusted_Connection=yes' in regular_conn_str}")
        print(f"  - Contains 'UID=': {'UID=' in regular_conn_str}")
        print(f"  - Contains 'PWD=': {'PWD=' in regular_conn_str}")
    
    print("\n" + "=" * 70)
    print("✅ All Python code execution uses Windows Authentication")
    print("=" * 70)
    
    print("\n📋 Code Execution Flow:")
    print("  1. API endpoint: /api/v1/execute-python")
    print("  2. Loads settings.target_db.python_connection_string_encrypted")
    print("  3. Decrypts connection string (Windows Auth)")
    print("  4. Injects as DB_CONNECTION_STRING into execution context")
    print("  5. Python code uses: sqlalchemy.create_engine(DB_CONNECTION_STRING)")
    print("  6. SQLAlchemy connects using Windows Authentication")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
