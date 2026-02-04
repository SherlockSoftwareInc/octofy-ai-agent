"""
Script to update SQL Server connection to use Windows authentication
and regenerate encrypted connection strings.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.settings_service import (
    load_settings, 
    save_settings, 
    build_connection_string,
    encrypt_string
)

def main():
    print("Loading current settings...")
    settings = load_settings()
    
    # Update target_db to use Windows authentication
    settings.target_db.auth_type = "windows"
    settings.target_db.username = None  # Not needed for Windows auth
    
    # Build new connection string for Windows authentication
    print(f"Building Windows authentication connection string...")
    print(f"  Server: {settings.target_db.server}")
    print(f"  Database: {settings.target_db.database_name}")
    print(f"  Driver: {settings.target_db.driver}")
    
    conn_str = build_connection_string(
        driver=settings.target_db.driver,
        server=settings.target_db.server,
        database=settings.target_db.database_name,
        auth_type="windows",
        username=None,
        password=None,
        trust_server_certificate=settings.target_db.trust_server_certificate
    )
    
    # Python connection string (similar but formatted for Python pyodbc)
    python_conn_str = conn_str
    
    print(f"\nNew connection string (masked):")
    print(f"  {conn_str}")
    
    # Encrypt the connection strings
    print("\nEncrypting connection strings...")
    settings.target_db.connection_string_encrypted = encrypt_string(conn_str)
    settings.target_db.python_connection_string_encrypted = encrypt_string(python_conn_str)
    
    # Save updated settings
    print("Saving updated settings...")
    success = save_settings(settings)
    
    if success:
        print("\n✅ Successfully updated to Windows authentication!")
        print("\nNext steps:")
        print("1. Verify database connection works with Windows authentication")
        print("2. Restart the application")
        print("3. Test database queries")
    else:
        print("\n❌ Failed to save settings")
        sys.exit(1)

if __name__ == "__main__":
    main()
