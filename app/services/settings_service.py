"""
Settings Service - Manages agent configuration with encryption for sensitive data
"""
import os
import logging
import hashlib
from typing import Optional, Union
from cryptography.fernet import Fernet
import base64
from dotenv import dotenv_values
from app.models.schemas import AgentSettings, TargetDBConfig, LLMConfig, VectorConfig, EmbeddingConfig, AppMeta, AgentSettingsV2, TargetDBConfigV2
from app.core.config import settings as app_settings

# Encryption key derivation (in production, use a proper secret management system)
def get_encryption_key() -> bytes:
    """
    Derive an encryption key from environment variable or generate one.
    In production, store this in a secure vault (Azure Key Vault, AWS Secrets Manager, etc.)
    """
    secret = os.getenv("SETTINGS_ENCRYPTION_KEY", "default-insecure-key-change-me")
    salt = b"sql_agent_salt"  # In production, store salt separately
    
    # Use PBKDF2 via hashlib
    key = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt, iterations=100000, dklen=32)
    return base64.urlsafe_b64encode(key)

def encrypt_string(plaintext: str) -> str:
    """Encrypt a string using Fernet (AES-128)"""
    if not plaintext:
        return ""
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode())
    return encrypted.decode()

def decrypt_string(encrypted: str) -> str:
    """Decrypt a string using Fernet"""
    if not encrypted:
        return ""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Decryption failed: {e}")
        return ""

def mask_password(connection_string: str) -> str:
    """Mask password in connection string for display"""
    import re
    # Match PWD=xxx; or Password=xxx;
    masked = re.sub(r'(PWD|Password)=([^;]+)', r'\1=******', connection_string, flags=re.IGNORECASE)
    return masked

def build_connection_string(driver: str, server: str, database: str, auth_type: str, 
                           username: Optional[str] = None, password: Optional[str] = None,
                           trust_server_certificate: Optional[bool] = False) -> str:
    """Build SQL Server connection string from components"""
    parts = [
        f"Driver={{{driver}}}",
        f"Server={server}",
        f"Database={database}",
        "Encrypt=yes"
    ]
    if trust_server_certificate:
        parts.append("TrustServerCertificate=yes")

    normalized_auth = auth_type.lower()
    if normalized_auth == "sql":
        if username and password:
            parts.append(f"UID={username}")
            parts.append(f"PWD={password}")
    elif normalized_auth == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        auth_map = {
            "ad_integrated": "ActiveDirectoryIntegrated",
            "ad_password": "ActiveDirectoryPassword",
            "ad_interactive": "ActiveDirectoryInteractive",
            "ad_service_principal": "ActiveDirectoryServicePrincipal"
        }
        if normalized_auth not in auth_map:
            raise ValueError(f"Unsupported authentication type: {auth_type}")

        parts.append(f"Authentication={auth_map[normalized_auth]}")

        if normalized_auth in {"ad_password", "ad_service_principal"}:
            if not username or not password:
                raise ValueError("Username and password are required for this authentication mode.")
            parts.append(f"UID={username}")
            parts.append(f"PWD={password}")
        elif normalized_auth == "ad_interactive" and username:
            parts.append(f"UID={username}")

    return ";".join(parts)

def _get_env_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))


def _read_env_lines() -> list[str]:
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        return []
    with open(env_path, "r", encoding="utf-8") as handle:
        return handle.readlines()


def _write_env_lines(lines: list[str]) -> None:
    env_path = _get_env_path()
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as handle:
        handle.writelines(lines)


def _update_env_value(lines: list[str], key: str, value: Optional[str]) -> None:
    updated_line = f"{key}={value or ''}\n"
    found = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(f"{key}="):
            lines[index] = updated_line
            found = True
            break
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        lines.append(updated_line)


def _is_masked_secret(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    return value.startswith("sk-") and "..." in value


def _resolve_value(value: Optional[str], existing: Optional[str]) -> Optional[str]:
    if value is None:
        return existing
    return value


def _resolve_secret(value: Optional[str], existing: Optional[str]) -> Optional[str]:
    if _is_masked_secret(value):
        return existing
    return _resolve_value(value, existing)


def get_default_settings() -> AgentSettings:
    """Return settings derived from environment variables (.env)."""
    llm_api_key = app_settings.LLM_API_KEY or app_settings.OPENAI_API_KEY
    llm_model = app_settings.LLM_MODEL or app_settings.OPENAI_MODEL
    llm_endpoint = app_settings.LLM_ENDPOINT
    if not llm_endpoint and llm_api_key and str(llm_api_key).startswith("sk-"):
        llm_endpoint = "https://api.openai.com/v1"

    embedding_api_key = app_settings.EMBEDDING_API_KEY or app_settings.OPENAI_API_KEY
    embedding_base_url = app_settings.EMBEDDING_BASE_URL or app_settings.OPENAI_EMBEDDING_ENDPOINT
    embedding_model = app_settings.EMBEDDING_MODEL or "text-embedding-3-small"
    embedding_dimensions = app_settings.EMBEDDING_DIMENSIONS or 1536

    vector_host = app_settings.VECTOR_HOST or app_settings.MILVUS_HOST
    vector_port = app_settings.VECTOR_PORT or app_settings.MILVUS_PORT

    # Note: target_db removed - connection info now comes from _data-source.md
    return AgentSettings(
        llm_config=LLMConfig(
            llm_model=llm_model,
            temperature=app_settings.LLM_TEMPERATURE,
            llm_endpoint=llm_endpoint,
            llm_api_key=llm_api_key
        ),
        embedding_config=EmbeddingConfig(
            provider=app_settings.EMBEDDING_PROVIDER,
            model=embedding_model,
            dimensions=embedding_dimensions,
            api_key=embedding_api_key,
            base_url=embedding_base_url
        ),
        vector_config=VectorConfig(
            provider=app_settings.VECTOR_PROVIDER,
            host=vector_host,
            port=vector_port
        ),
        app_meta=AppMeta(
            app_name=app_settings.APP_NAME,
            version=app_settings.APP_VERSION,
            project_name=app_settings.PROJECT_NAME
        )
    )


def load_settings() -> Union[AgentSettings, AgentSettingsV2]:
    """Load settings from environment variables (.env)."""
    return get_default_settings()


# --- Multi-Source Helper Functions (V2) ---

def encrypt_connection_string(connection_string: str) -> str:
    """
    Encrypt a connection string using Fernet.
    Alias for encrypt_string for better readability in multi-source context.
    """
    return encrypt_string(connection_string)


def decrypt_connection_string(encrypted_string: str) -> str:
    """
    Decrypt a connection string using Fernet.
    Alias for decrypt_string for better readability in multi-source context.
    """
    return decrypt_string(encrypted_string)


def get_data_source(source_id: str) -> Optional[TargetDBConfigV2]:
    """
    DEPRECATED: Data sources are stored in skills/_data-source.md files.
    Use skills_service.load_data_source() instead to load from skills directory.
    
    Args:
        source_id: Data source identifier
        
    Returns:
        Always returns None (deprecated functionality)
    """
    logger = logging.getLogger(__name__)
    logger.warning(
        "get_data_source() is deprecated. Data sources are only loaded from skills/_data-source.md files. "
        "Use skills_service.load_data_source() instead."
    )
    return None


def add_data_source(source: TargetDBConfigV2) -> None:
    """
    DEPRECATED: Data sources are stored in skills/_data-source.md files.
    Use the Admin UI to add data sources via skills directory.
    
    Args:
        source: TargetDBConfigV2 instance to add
        
    Raises:
        ValueError: Always raises - functionality is deprecated
    """
    raise ValueError(
        "add_data_source() is deprecated. Data sources are only managed via skills/_data-source.md files. "
        "Use the Admin > Data Sources UI to add new data sources."
    )


def remove_data_source(source_id: str) -> bool:
    """
    DEPRECATED: Data sources are stored in skills/_data-source.md files.
    Use the Admin UI to manage data sources via skills directory.
    
    Args:
        source_id: Data source identifier
        
    Returns:
        Always returns False (deprecated functionality)
    """
    logger = logging.getLogger(__name__)
    logger.warning(
        "remove_data_source() is deprecated. Data sources are only managed via skills/_data-source.md files. "
        "Use the Admin > Data Sources UI to manage data sources."
    )
    return False


def set_primary_source(source_id: str) -> bool:
    """
    Set a data source as the primary (default) source.
    
    Args:
        source_id: Data source identifier
        
    Returns:
        True if set, False if source not found
    """
    settings = load_settings()
    
    if not hasattr(settings, 'data_sources'):
        return False
    
    # Verify source exists
    if not any(s.source_id == source_id for s in settings.data_sources):
        return False
    
    settings.primary_source_id = source_id
    save_settings(settings)
    return True


def update_source_last_synced(source_id: str, timestamp: str) -> bool:
    """
    Update the last_synced timestamp for a data source.
    
    Args:
        source_id: Data source identifier
        timestamp: ISO format timestamp string
        
    Returns:
        True if updated, False if source not found
    """
    settings = load_settings()
    
    if not hasattr(settings, 'data_sources'):
        return False
    
    for source in settings.data_sources:
        if source.source_id == source_id:
            source.last_synced = timestamp
            save_settings(settings)
            return True
    
    return False


def update_source_object_count(source_id: str, count: int) -> bool:
    """
    Update the object_count for a data source.
    
    Args:
        source_id: Data source identifier
        count: Number of indexed objects
        
    Returns:
        True if updated, False if source not found
    """
    settings = load_settings()
    
    if not hasattr(settings, 'data_sources'):
        return False
    
    for source in settings.data_sources:
        if source.source_id == source_id:
            source.object_count = count
            save_settings(settings)
            return True
    
    return False


def save_settings(agent_settings: AgentSettings) -> bool:
    """Persist settings to .env (source of truth)."""
    try:
        env_path = _get_env_path()
        existing_env = dotenv_values(env_path) if os.path.exists(env_path) else {}
        lines = _read_env_lines()

        llm_api_key = _resolve_secret(agent_settings.llm_config.llm_api_key, existing_env.get("LLM_API_KEY") or existing_env.get("OPENAI_API_KEY"))
        embedding_api_key = _resolve_secret(agent_settings.embedding_config.api_key, existing_env.get("EMBEDDING_API_KEY") or existing_env.get("OPENAI_API_KEY"))

        llm_endpoint = _resolve_value(agent_settings.llm_config.llm_endpoint, existing_env.get("LLM_ENDPOINT"))
        llm_model = _resolve_value(agent_settings.llm_config.llm_model, existing_env.get("LLM_MODEL") or existing_env.get("OPENAI_MODEL"))
        llm_temperature = _resolve_value(str(agent_settings.llm_config.temperature), existing_env.get("LLM_TEMPERATURE"))

        embedding_provider = _resolve_value(agent_settings.embedding_config.provider, existing_env.get("EMBEDDING_PROVIDER"))
        embedding_base_url = _resolve_value(agent_settings.embedding_config.base_url, existing_env.get("EMBEDDING_BASE_URL") or existing_env.get("OPENAI_EMBEDDING_ENDPOINT"))
        embedding_model = _resolve_value(agent_settings.embedding_config.model, existing_env.get("EMBEDDING_MODEL"))
        embedding_dimensions = _resolve_value(str(agent_settings.embedding_config.dimensions), existing_env.get("EMBEDDING_DIMENSIONS"))

        vector_provider = _resolve_value(agent_settings.vector_config.provider, existing_env.get("VECTOR_PROVIDER"))
        vector_host = _resolve_value(agent_settings.vector_config.host, existing_env.get("VECTOR_HOST") or existing_env.get("MILVUS_HOST"))
        vector_port = _resolve_value(agent_settings.vector_config.port, existing_env.get("VECTOR_PORT") or existing_env.get("MILVUS_PORT"))

        app_name = _resolve_value(agent_settings.app_meta.app_name, existing_env.get("APP_NAME"))
        app_version = _resolve_value(agent_settings.app_meta.version, existing_env.get("APP_VERSION"))
        project_name = _resolve_value(agent_settings.app_meta.project_name, existing_env.get("PROJECT_NAME"))

        updates = {
            "LLM_API_KEY": llm_api_key,
            "LLM_ENDPOINT": llm_endpoint,
            "LLM_MODEL": llm_model,
            "LLM_TEMPERATURE": llm_temperature,
            "EMBEDDING_PROVIDER": embedding_provider,
            "EMBEDDING_BASE_URL": embedding_base_url,
            "EMBEDDING_API_KEY": embedding_api_key,
            "EMBEDDING_MODEL": embedding_model,
            "EMBEDDING_DIMENSIONS": embedding_dimensions,
            "VECTOR_PROVIDER": vector_provider,
            "VECTOR_HOST": vector_host,
            "VECTOR_PORT": vector_port,
            "APP_NAME": app_name,
            "APP_VERSION": app_version,
            "PROJECT_NAME": project_name
        }

        openai_api_key = llm_api_key or embedding_api_key or existing_env.get("OPENAI_API_KEY")
        updates["OPENAI_API_KEY"] = openai_api_key
        updates["OPENAI_MODEL"] = llm_model or existing_env.get("OPENAI_MODEL")
        updates["OPENAI_EMBEDDING_ENDPOINT"] = embedding_base_url or existing_env.get("OPENAI_EMBEDDING_ENDPOINT")
        updates["MILVUS_HOST"] = vector_host or existing_env.get("MILVUS_HOST")
        updates["MILVUS_PORT"] = vector_port or existing_env.get("MILVUS_PORT")

        for key, value in updates.items():
            _update_env_value(lines, key, value)

        _write_env_lines(lines)
        return True
    except Exception as e:
        print(f"Failed to save settings to .env: {e}")
        return False


def validate_milvus_settings(vector_config: VectorConfig) -> None:
    """
    Validate Milvus connectivity and required collections.
    Raises ValueError on failure.
    """
    if not vector_config or vector_config.provider.lower() != "milvus":
        return

    host = vector_config.host
    port = vector_config.port

    if not host or not port:
        raise ValueError("Milvus host and port must be provided.")

    from pymilvus import connections, utility

    alias = "settings_validation"
    required_collections = [
        app_settings.MILVUS_COLLECTION_SCHEMA,
        app_settings.MILVUS_COLLECTION_FEWSHOT,
        app_settings.MILVUS_COLLECTION_VALUES
    ]

    try:
        connections.connect(alias=alias, host=host, port=port)
        missing = [name for name in required_collections if not utility.has_collection(name, using=alias)]
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(f"Milvus collections missing: {missing_list}")
    except Exception as e:
        raise ValueError(f"Milvus validation failed: {e}")
    finally:
        try:
            connections.disconnect(alias=alias)
        except Exception:
            pass

def _mask_api_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    key_str = str(value)
    if len(key_str) <= 10:
        return key_str
    return f"{key_str[:3]}...{key_str[-4:]}"


def _populate_connection_metadata(connection_string: str, fallback_server: str, fallback_db: str) -> tuple[str, str]:
    import re
    server = fallback_server
    database = fallback_db
    if connection_string:
        server_match = re.search(r'SERVER=([^;]+)', connection_string, re.IGNORECASE)
        db_match = re.search(r'DATABASE=([^;]+)', connection_string, re.IGNORECASE)
        if server_match:
            server = server_match.group(1)
        if db_match:
            database = db_match.group(1)
    return server, database


def get_settings_for_display() -> Union[AgentSettings, AgentSettingsV2]:
    """Get settings with masked sensitive data for frontend display."""
    settings = load_settings()

    # Handle multi-source configuration (v2)
    if isinstance(settings, AgentSettingsV2):
        display_settings = settings.model_copy(deep=True)

        for source in display_settings.data_sources:
            decrypted = decrypt_string(source.connection_string_encrypted)
            server, database = _populate_connection_metadata(decrypted, source.server or "", source.database_name or "")
            source.server = server
            source.database_name = database
            source.connection_string_decrypted = None
            source.python_connection_string_decrypted = None

        display_settings.embedding_config.api_key = _mask_api_key(display_settings.embedding_config.api_key)
        return display_settings

    # Note: target_db handling removed - connection info now comes from _data-source.md
    # Mask sensitive API keys for display
    settings.llm_config.llm_api_key = _mask_api_key(settings.llm_config.llm_api_key)
    settings.embedding_config.api_key = _mask_api_key(settings.embedding_config.api_key)
    return settings
