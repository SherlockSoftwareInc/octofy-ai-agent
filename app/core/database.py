from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Dict, Optional
from app.core.config import settings
from app.services.settings_service import load_settings, decrypt_string
from app.models.schemas import ConnectionTestRequest, ConnectionTestResponse
from app.services.data_source_registry_service import DataSourceRegistryService
from app.core.user_database import get_user_db_session
import urllib.parse
import logging

logger = logging.getLogger(__name__)

# Cache of database engines by source_id
_engines: Dict[str, Engine] = {}


def get_db_engine():
    """
    Legacy function for backward compatibility.
    Returns engine for primary data source or single database in v1 config.
    """
    return get_database_engine()


def _build_source_sqlalchemy_url(source_id: Optional[str] = None) -> tuple[str, str]:
    """Return (cache_key, sqlalchemy_url) for a data source from _data-source.md."""
    cache_key = source_id or "primary"

    if source_id:
        with get_user_db_session() as db_session:
            registry = DataSourceRegistryService(db_session)
            resolved_id = registry.resolve_source_id(source_id)

            if resolved_id and resolved_id != source_id:
                logger.info(f"Resolved source_id '{source_id}' to '{resolved_id}'")
                source_id = resolved_id
                cache_key = resolved_id
            elif not resolved_id:
                logger.warning(f"Could not resolve source_id '{source_id}' through registry")

    from app.services.skills_service import get_skills_service
    skills_service = get_skills_service()
    data_source = None
    if source_id:
        sources = skills_service.load_data_sources_index()
        for source in sources:
            if source.source_id == source_id:
                data_source = source
                break
        if not data_source:
            for source in sources:
                if source.name.lower() == source_id.lower():
                    data_source = source
                    break
        if not data_source:
            raise ValueError(f"Data source '{source_id}' not found in skills directory")
    else:
        data_source = skills_service.load_primary_data_source()
        if not data_source:
            raise ValueError("No data source configuration found in skills directory")

    import re
    server = None
    database = None
    if data_source.connection_info:
        server = data_source.connection_info.get("server") or server
        database = data_source.connection_info.get("database") or database

    if (not server or not database) and getattr(data_source, "file_path", None):
        from pathlib import Path
        file_content = Path(data_source.file_path).read_text(encoding='utf-8')
        if not server:
            server_match = re.search(r'\*\*Server:\*\*\s*([^\n]+)', file_content)
            server = server_match.group(1).strip() if server_match else server
        if not database:
            database_match = re.search(r'\*\*Database:\*\*\s*([^\n]+)', file_content)
            database = database_match.group(1).strip() if database_match else database

    if not server or not database:
        server_match = re.search(r'\*\*Server:\*\*\s*([^\n]+)', data_source.description or '')
        database_match = re.search(r'\*\*Database:\*\*\s*([^\n]+)', data_source.description or '')
        if not server and server_match:
            server = server_match.group(1).strip()
        if not database and database_match:
            database = database_match.group(1).strip()

    if not server or not database:
        conn_str = settings.SQL_SERVER_CONNECTION_STRING
        if not conn_str:
            raise ValueError("Could not extract Server/Database from _data-source.md and no fallback connection string available")
    else:
        driver = "ODBC Driver 17 for SQL Server"
        conn_str = f"Driver={{{driver}}};Server={server};Database={database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes"

    if not conn_str.startswith("mssql"):
        params = urllib.parse.quote_plus(conn_str)
        conn_str = f"mssql+pyodbc:///?odbc_connect={params}"

    return cache_key, conn_str


def get_source_sqlalchemy_url(source_id: Optional[str] = None) -> str:
    """SQLAlchemy URL for a data source — the same URL SQL execution uses."""
    _cache_key, conn_str = _build_source_sqlalchemy_url(source_id)
    return conn_str


def get_database_engine(source_id: Optional[str] = None) -> Engine:
    """
    Get database engine for a specific data source or the primary source.
    
    Connection string is built from _data-source.md in skills directory.
    Uses Windows Authentication by default.
    
    Args:
        source_id: Optional data source identifier. If None, uses primary source.
        
    Returns:
        SQLAlchemy Engine instance
        
    Raises:
        ValueError: If source not found or connection string not configured
    """
    cache_key = source_id or "primary"
    if cache_key in _engines:
        return _engines[cache_key]

    cache_key, conn_str = _build_source_sqlalchemy_url(source_id)
    if cache_key in _engines:
        return _engines[cache_key]

    engine = create_engine(conn_str)
    _engines[cache_key] = engine
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

