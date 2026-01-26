from sqlalchemy import create_engine
from app.core.config import settings
from app.services.settings_service import load_settings, decrypt_string
import urllib.parse

def get_db_engine():
    # Priority 1: Load from dynamic settings file
    try:
        agent_settings = load_settings()
        if agent_settings.target_db.connection_string_encrypted:
            conn_str = decrypt_string(agent_settings.target_db.connection_string_encrypted)
        else:
            conn_str = None
    except Exception as e:
        print(f"Warning: Failed to load dynamic settings in get_db_engine: {e}")
        conn_str = None

    # Priority 2: Fallback to environment variable
    if not conn_str:
        conn_str = settings.SQL_SERVER_CONNECTION_STRING

    if not conn_str:
         raise ValueError("SQL_SERVER_CONNECTION_STRING is not set in settings or .env.")
    
    if not conn_str.startswith("mssql"):
        params = urllib.parse.quote_plus(conn_str)
        conn_str = f"mssql+pyodbc:///?odbc_connect={params}"
        
    return create_engine(conn_str)
