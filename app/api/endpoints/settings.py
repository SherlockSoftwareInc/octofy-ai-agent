"""
Settings API Endpoints - Manage agent configuration
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine, text
from app.models.schemas import (
    AgentSettings, ConnectionTestRequest, ConnectionTestResponse,
    FetchModelsRequest, FetchModelsResponse, EnvApiKeyResponse, EnvApiKeyUpdateRequest
)
from app.services.settings_service import (
    load_settings, save_settings, get_settings_for_display,
    encrypt_string, decrypt_string, build_connection_string, mask_password,
    validate_milvus_settings
)
from app.services.vector_store import refresh_vector_store
from app.services.llm_service import fetch_available_models
from app.core.auth import verify_api_key
import urllib.parse
import os
from dotenv import dotenv_values
from typing import Optional
import re

router = APIRouter()

def _get_env_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))

def _read_env_api_key() -> Optional[str]:
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        return None
    api_key = dotenv_values(env_path).get("API_KEY")
    if api_key:
        return str(api_key)
    return None

def _write_env_api_key(api_key: str) -> None:
    env_path = _get_env_path()
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    updated_line = f"API_KEY={api_key}\n"
    found = False
    for index, line in enumerate(lines):
        if re.match(r"^\s*API_KEY\s*=", line):
            lines[index] = updated_line
            found = True
            break
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        lines.append(updated_line)
    with open(env_path, "w", encoding="utf-8") as handle:
        handle.writelines(lines)

@router.get("/settings", response_model=AgentSettings)
def get_settings(api_key: str = Depends(verify_api_key)):
    """Get current agent settings with masked sensitive data"""
    try:
        return get_settings_for_display()
    except Exception as e:
        print(f"Error loading settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")

@router.get("/api-key", response_model=EnvApiKeyResponse)
def get_env_api_key():
    api_key = _read_env_api_key()
    return EnvApiKeyResponse(api_key=api_key, exists=bool(api_key))

@router.post("/api-key", response_model=EnvApiKeyResponse)
def set_env_api_key(request: EnvApiKeyUpdateRequest):
    api_key = request.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")

    current = _read_env_api_key()
    if current:
        raise HTTPException(status_code=409, detail="API key is already set in .env.")

    _write_env_api_key(api_key)
    return EnvApiKeyResponse(api_key=api_key, exists=True)

@router.put("/settings", response_model=AgentSettings)
def update_settings(settings: AgentSettings, api_key: str = Depends(verify_api_key)):
    """Update agent settings"""
    try:
        current_settings = load_settings()

        # Validate Milvus settings only when host/port/provider changes
        vector_changed = (
            settings.vector_config.host != current_settings.vector_config.host or
            settings.vector_config.port != current_settings.vector_config.port or
            settings.vector_config.provider != current_settings.vector_config.provider
        )
        if vector_changed:
            validate_milvus_settings(settings.vector_config)
        
        success = save_settings(settings)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save settings")

        # Refresh runtime vector store to pick up new settings
        refresh_vector_store()

        return get_settings_for_display()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")

@router.post("/test-connection", response_model=ConnectionTestResponse)
def test_connection(request: ConnectionTestRequest, api_key: str = Depends(verify_api_key)):
    """Test database connection with provided credentials"""
    try:
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
        
        # Convert to SQLAlchemy URL format
        params = urllib.parse.quote_plus(conn_str)
        engine_url = f"mssql+pyodbc:///?odbc_connect={params}"
        
        # Attempt connection
        engine = create_engine(engine_url, pool_pre_ping=True, connect_args={"timeout": 5})
        
        with engine.connect() as connection:
            # Try a simple query
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        
        engine.dispose()
        
        return ConnectionTestResponse(
            success=True,
            message="Connection successful",
            connection_string_masked=mask_password(conn_str)
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
            connection_string_masked=None
        )

@router.get("/models")
def get_available_models(api_key: str = Depends(verify_api_key)):
    """Get list of available LLM models"""
    # Try to fetch from configured endpoint first
    try:
        settings = load_settings()
        if settings.llm_config.llm_endpoint:
            models = fetch_available_models(settings.llm_config.llm_endpoint, settings.llm_config.llm_api_key)
            return {"models": models}
    except Exception as e:
        print(f"Failed to fetch from configured endpoint: {e}")
        # Fallback to default list

    # For OpenAI/Default, return common models
    # In production, you might want to fetch this from the API
    models = [
        {"id": "gpt-4o", "name": "GPT-4 Omni", "provider": "openai"},
        {"id": "gpt-4o-mini", "name": "GPT-4 Omni Mini", "provider": "openai"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "openai"},
        {"id": "gpt-4", "name": "GPT-4", "provider": "openai"},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "openai"}
    ]
    return {"models": models}

@router.post("/fetch-models", response_model=FetchModelsResponse)
def fetch_models(request: FetchModelsRequest, api_key: str = Depends(verify_api_key)):
    """Fetch available models from the specified endpoint"""
    try:
        models = fetch_available_models(request.llm_endpoint, request.llm_api_key)
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")

@router.post("/build-connection-string")
def build_connection_string_endpoint(request: ConnectionTestRequest, api_key: str = Depends(verify_api_key)):
    """Build and return a connection string from components"""
    try:
        conn_str = build_connection_string(
            driver=request.driver,
            server=request.server,
            database=request.database,
            auth_type=request.auth_type,
            username=request.username,
            password=request.password,
            trust_server_certificate=request.trust_server_certificate
        )
        
        # Build Python connection string (SQLAlchemy URL format)
        # Format: mssql+pyodbc://user:pass@server,port/database?driver=...&param=value
        
        # Start building the URL
        if request.auth_type == 'sql' and request.username and request.password:
            # SQL Authentication: include username and password in URL
            username_encoded = urllib.parse.quote_plus(request.username)
            password_encoded = urllib.parse.quote_plus(request.password)
            auth_part = f"{username_encoded}:{password_encoded}@"
        else:
            # Windows/AD Authentication: use @ with no credentials
            auth_part = "@"
        
        # Build the base URL with server and database
        python_conn_str = f"mssql+pyodbc://{auth_part}{request.server}/{request.database}?"
        
        # Add query parameters
        params = []
        params.append(f"driver={urllib.parse.quote_plus(request.driver)}")
        
        if request.trust_server_certificate:
            params.append("TrustServerCertificate=yes")
            params.append("Encrypt=yes")
        
        # Add authentication-specific parameters
        if request.auth_type == 'windows':
            params.append("trusted_connection=yes")
        elif request.auth_type in ['ad_integrated', 'ad_password', 'ad_interactive', 'ad_service_principal']:
            params.append(f"Authentication={request.auth_type.replace('ad_', 'ActiveDirectory')}")
        
        python_conn_str += "&".join(params)
        
        return {
            "connection_string": conn_str,
            "connection_string_masked": mask_password(conn_str),
            "encrypted": encrypt_string(conn_str),
            "python_connection_string": python_conn_str,
            "python_encrypted": encrypt_string(python_conn_str)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to build connection string: {str(e)}")

@router.post("/verify-settings")
def verify_settings(api_key: str = Depends(verify_api_key)):
    """
    Verify the basic connectivity of the current settings (Database, LLM, and Vector Store).
    """
    results = {
        "db_connected": False,
        "db_message": "",
        "llm_connected": False,
        "llm_message": "",
        "milvus_connected": False,
        "milvus_message": ""
    }

    settings_obj = None
    try:
        settings_obj = load_settings()
    except Exception as e:
        msg = f"Failed to load settings: {str(e)}"
        results["db_message"] = msg
        results["llm_message"] = msg
        results["milvus_message"] = msg
        return results

    # 1. Verify Database
    try:
        from app.core.config import settings as app_settings
        conn_str = app_settings.SQL_SERVER_CONNECTION_STRING
        if conn_str:
            params = urllib.parse.quote_plus(conn_str)
            engine_url = f"mssql+pyodbc:///?odbc_connect={params}"
            engine = create_engine(engine_url, pool_pre_ping=True, connect_args={"timeout": 5})
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()

            results["db_connected"] = True
            results["db_message"] = "Successfully connected to the database."
        else:
            results["db_message"] = "No connection string configured."

    except Exception as e:
        results["db_connected"] = False
        results["db_message"] = f"Database connection failed: {str(e)}"

    # 2. Verify LLM
    try:
        if settings_obj.llm_config.llm_endpoint:
            fetch_available_models(settings_obj.llm_config.llm_endpoint, settings_obj.llm_config.llm_api_key)
            results["llm_connected"] = True
            results["llm_message"] = "Successfully connected to LLM Provider."
        else:
             results["llm_message"] = "LLM Endpoint not configured."
    except Exception as e:
        results["llm_connected"] = False
        results["llm_message"] = f"LLM connection failed: {str(e)}"

    # 3. Verify Milvus (Vector Store)
    try:
        from pymilvus import connections, utility
        from app.core.config import settings as app_settings
        
        milvus_host = settings_obj.vector_config.host
        milvus_port = settings_obj.vector_config.port
        
        # Connect
        connections.connect(alias="verify_test", host=milvus_host, port=milvus_port, timeout=5)
        
        # Check Collections
        required_collections = [
            app_settings.MILVUS_COLLECTION_SCHEMA,
            app_settings.MILVUS_COLLECTION_FEWSHOT,
            app_settings.MILVUS_COLLECTION_VALUES
        ]
        
        missing_collections = []
        for col_name in required_collections:
            if not utility.has_collection(col_name, using="verify_test"):
                missing_collections.append(col_name)
        
        connections.disconnect("verify_test")
        
        if missing_collections:
            results["milvus_connected"] = False
            results["milvus_message"] = f"Connected to Milvus, but missing collections: {', '.join(missing_collections)}. Please rebuild vector store."
        else:
            results["milvus_connected"] = True
            results["milvus_message"] = "Successfully connected to Milvus and verified required collections."
            
    except Exception as e:
        results["milvus_connected"] = False
        results["milvus_message"] = f"Milvus connection failed: {str(e)}"

    return results
