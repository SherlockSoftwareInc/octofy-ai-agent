from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Dict, Optional
from app.core.config import settings
from app.services.settings_service import load_settings, decrypt_string
from app.models.schemas import ConnectionTestRequest, ConnectionTestResponse
import urllib.parse

# Cache of database engines by source_id
_engines: Dict[str, Engine] = {}


def get_db_engine():
    """
    Legacy function for backward compatibility.
    Returns engine for primary data source or single database in v1 config.
    """
    return get_database_engine()


def get_database_engine(source_id: Optional[str] = None) -> Engine:
    """
    Get database engine for a specific data source or the primary source.
    
    Args:
        source_id: Optional data source identifier. If None, uses primary source.
        
    Returns:
        SQLAlchemy Engine instance
        
    Raises:
        ValueError: If source not found or connection string not configured
    """
    # Load settings
    agent_settings = load_settings()
    
    # Determine which source to use
    if source_id is None:
        # Use primary source or single v1 source
        if hasattr(agent_settings, 'data_sources'):
            # V2 config - use primary
            if not agent_settings.data_sources:
                raise ValueError("No data sources configured")
            
            if agent_settings.primary_source_id:
                source_id = agent_settings.primary_source_id
            else:
                source_id = agent_settings.data_sources[0].source_id
        else:
            # V1 config - use target_db (use a fixed key)
            source_id = "legacy_v1"
    
    # Check cache
    if source_id in _engines:
        return _engines[source_id]
    
    # Build connection string
    conn_str = None
    
    if source_id == "legacy_v1":
        # V1 configuration
        if hasattr(agent_settings, 'target_db') and agent_settings.target_db.connection_string_encrypted:
            conn_str = decrypt_string(agent_settings.target_db.connection_string_encrypted)
    else:
        # V2 configuration
        if hasattr(agent_settings, 'data_sources'):
            source = next((s for s in agent_settings.data_sources if s.source_id == source_id), None)
            if source and source.connection_string_encrypted:
                conn_str = decrypt_string(source.connection_string_encrypted)
            else:
                raise ValueError(f"Data source {source_id} not found or not configured")
    
    # Fallback to environment variable
    if not conn_str:
        conn_str = settings.SQL_SERVER_CONNECTION_STRING
    
    if not conn_str:
        raise ValueError(f"Connection string not configured for source {source_id}")
    
    # Build SQLAlchemy connection string
    if not conn_str.startswith("mssql"):
        params = urllib.parse.quote_plus(conn_str)
        conn_str = f"mssql+pyodbc:///?odbc_connect={params}"
    
    # Create and cache engine
    engine = create_engine(conn_str)
    _engines[source_id] = engine
    
    return engine


def clear_engine_cache(source_id: Optional[str] = None):
    """
    Clear cached database engine(s).
    
    Args:
        source_id: Optional source ID. If None, clears all cached engines.
    """
    global _engines
    
    if source_id is None:
        _engines.clear()
    elif source_id in _engines:
        engine = _engines.pop(source_id)
        engine.dispose()  # Close all connections


def test_connection(request: ConnectionTestRequest) -> ConnectionTestResponse:
    """
    Test a database connection with the provided credentials.
    
    Args:
        request: ConnectionTestRequest with connection details
        
    Returns:
        ConnectionTestResponse with success status and message
    """
    try:
        from app.services.settings_service import build_connection_string
        
        # Build connection string
        conn_str = build_connection_string(
            driver=request.driver,
            server=request.server,
            database=request.database,
            auth_type=request.auth_type,
            username=request.username,
            password=request.password,
            trust_server_certificate=request.trust_server_certificate
        )
        
        # Mask password for display
        from app.services.settings_service import mask_password
        masked_conn_str = mask_password(conn_str)
        
        # Build SQLAlchemy connection string
        params = urllib.parse.quote_plus(conn_str)
        sqlalchemy_conn_str = f"mssql+pyodbc:///?odbc_connect={params}"
        
        # Try to create engine and connect
        engine = create_engine(sqlalchemy_conn_str)
        
        with engine.connect() as conn:
            # Test query
            result = conn.execute("SELECT 1 AS test")
            row = result.fetchone()
            
            if row and row[0] == 1:
                return ConnectionTestResponse(
                    success=True,
                    message="Connection successful",
                    connection_string_masked=masked_conn_str
                )
            else:
                return ConnectionTestResponse(
                    success=False,
                    message="Connection test query failed",
                    connection_string_masked=masked_conn_str
                )
    
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
            connection_string_masked=None
        )

