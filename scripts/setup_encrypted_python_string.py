
import sys
import os
import json
import urllib.parse
import re

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.settings_service import load_settings, save_settings, decrypt_string, encrypt_string

def setup_python_string():
    print("Loading settings...")
    settings = load_settings()
    
    target_db = settings.target_db
    
    # 1. Get current connection string
    if not target_db.connection_string_encrypted:
        print("Error: No existing SQL connection string found.")
        return

    print("Decrypting existing SQL connection string...")
    sql_conn_str = decrypt_string(target_db.connection_string_encrypted)
    
    if not sql_conn_str:
        print("Error: Failed to decrypt SQL connection string.")
        return

    # 2. Convert to Python/SQLAlchemy format
    # Simpler approach: Use the exact same connection string but wrap it for SQLAlchemy if needed, 
    # OR just provide the raw ODBC string if using pyodbc directly.
    # The prompt expects DB_CONNECTION_STRING to be passed to create_engine.
    # SQLAlchemy for MSSQL+pyodbc supports passing the raw connection string via `odbc_connect` query param.
    
    # Format: mssql+pyodbc:///?odbc_connect={quoted_connection_string}
    quoted_conn_str = urllib.parse.quote_plus(sql_conn_str)
    python_conn_str = f"mssql+pyodbc:///?odbc_connect={quoted_conn_str}"
    
    print(f"Generated Python Connection String (Hidden)")
    
    # 3. Encrypt
    print("Encrypting Python connection string...")
    encrypted_python_str = encrypt_string(python_conn_str)
    
    # 4. Save
    print("Saving to settings...")
    # Update the setting
    settings.target_db.python_connection_string_encrypted = encrypted_python_str
    
    if save_settings(settings):
        print("Success! Agent settings updated with encrypted Python connection string.")
    else:
        print("Failed to save settings.")

if __name__ == "__main__":
    setup_python_string()
