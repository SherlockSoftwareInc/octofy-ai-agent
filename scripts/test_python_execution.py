
import sys
import os
import pandas as pd
import sqlalchemy

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.execution_service import execute_python_code
from app.services.settings_service import load_settings, decrypt_string

def test_execution():
    print("--- Starting Python Execution Test ---")
    
    # 1. Simulate API Logic: Retrieve & Decrypt
    print("Loading settings...")
    settings = load_settings()
    encrypted_conn_str = settings.target_db.python_connection_string_encrypted
    
    exec_context = {}
    
    if encrypted_conn_str:
        print("Found encrypted string. Decrypting...")
        try:
            decrypted_conn_str = decrypt_string(encrypted_conn_str)
            if decrypted_conn_str:
                exec_context['DB_CONNECTION_STRING'] = decrypted_conn_str
                print("Injection successful: DB_CONNECTION_STRING added to context.")
            else:
                 print("Error: Decrypted string is empty.")
        except Exception as e:
            print(f"Error: Decryption failed: {e}")
            return
    else:
        print("Error: No encrypted python string in settings.")
        return

    # 2. Define Test Code
    code = """
import pandas as pd
import sqlalchemy

print("Inside executed code...")

if 'DB_CONNECTION_STRING' in locals():
    print(f"CONFIRMED: DB_CONNECTION_STRING is present.")
    # Mask logic for display
    secret = locals()['DB_CONNECTION_STRING']
    masked = secret[:15] + "..." if secret else "EMPTY"
    print(f"Value starts with: {masked}")
    
    try:
        # verify it looks like a connection string
        if "mssql" in secret or "odbc" in secret:
             print("Format validation: Looks like a valid connection string.")
        else:
             print("Format validation warning: Does not look like standard alchemy string.")
             
        # Optional: Attempt create_engine (lazy, doesn't connect yet)
        engine = sqlalchemy.create_engine(secret)
        print("sqlalchemy.create_engine() call succeeded.")
    except Exception as e:
        print(f"Engine creation failed: {e}")

else:
    print("FAILURE: DB_CONNECTION_STRING NOT found in locals().")

final_result_df = pd.DataFrame({"test": ["passed"]})
"""

    # 3. Execute
    print("\nExecuting code...")
    result = execute_python_code(code, exec_context)
    
    print("\n--- Execution Result ---")
    print(f"Success: {result['success']}")
    print(f"Output:\n{result['output']}")
    print(f"Error: {result['error']}")

if __name__ == "__main__":
    test_execution()
