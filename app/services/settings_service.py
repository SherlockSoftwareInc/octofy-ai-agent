"""
Settings Service - Manages agent configuration with encryption for sensitive data
"""
import json
import os
import logging
import hashlib
from typing import Optional, Union
from cryptography.fernet import Fernet
import base64
from app.models.schemas import AgentSettings, TargetDBConfig, LLMConfig, VectorConfig, EmbeddingConfig, AppMeta, AgentSettingsV2, TargetDBConfigV2
from app.core.config import settings as app_settings

# Path to store settings file
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "../../config/agent_settings.json")

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

def get_default_settings() -> AgentSettings:
    """Return default settings if no configuration exists"""
    # Note: target_db removed - connection info now comes from _data-source.md
    return AgentSettings(
        llm_config=LLMConfig(
            llm_model=app_settings.OPENAI_MODEL,
            temperature=0.0
        ),
        embedding_config=EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-small",
            dimensions=1536,
            api_key=app_settings.OPENAI_API_KEY or None,
            base_url=app_settings.OPENAI_EMBEDDING_ENDPOINT or None
        ),
        vector_config=VectorConfig(
            provider="milvus",
            host="localhost",
            port="19630"
        ),
        app_meta=AppMeta(
            app_name="Octofy AI Agent",
            version="1.0.0",
            project_name=app_settings.PROJECT_NAME
        )
    )

def _apply_runtime_defaults(settings_obj: Union[AgentSettings, AgentSettingsV2]) -> Union[AgentSettings, AgentSettingsV2]:
    """Apply environment-based fallbacks without overwriting explicit config."""

    # LLM defaults
    if not settings_obj.llm_config.llm_api_key and app_settings.OPENAI_API_KEY:
        settings_obj.llm_config.llm_api_key = app_settings.OPENAI_API_KEY

    if not settings_obj.llm_config.llm_model and app_settings.OPENAI_MODEL:
        settings_obj.llm_config.llm_model = app_settings.OPENAI_MODEL

    if (not settings_obj.llm_config.llm_endpoint
            and settings_obj.llm_config.llm_api_key
            and str(settings_obj.llm_config.llm_api_key).startswith("sk-")):
        settings_obj.llm_config.llm_endpoint = "https://api.openai.com/v1"

    # Embedding defaults
    if not settings_obj.embedding_config.api_key and app_settings.OPENAI_API_KEY:
        settings_obj.embedding_config.api_key = app_settings.OPENAI_API_KEY
    if not settings_obj.embedding_config.base_url and app_settings.OPENAI_EMBEDDING_ENDPOINT:
        settings_obj.embedding_config.base_url = app_settings.OPENAI_EMBEDDING_ENDPOINT

    # Vector defaults (stay within config file values when possible)
    if not settings_obj.vector_config.host:
        settings_obj.vector_config.host = "localhost"
    if not settings_obj.vector_config.port:
        settings_obj.vector_config.port = "19630"

    return settings_obj


def _load_v1_settings(data: dict) -> AgentSettings:
    """Load v1 settings format.
    
    Note: Data sources are NEVER loaded from agent_settings.json.
    They are always loaded from skills/_data-source.md files.
    """
    data = data.copy()

    # Legacy migration for embedding config
    if "embedding_config" not in data:
        vec_conf = data.get("vector_config", {})
        old_model = vec_conf.get("embedding_model", "text-embedding-3-small")
        data["embedding_config"] = {
            "provider": "openai",
            "model": old_model,
            "dimensions": 1536,
            "api_key": None,
            "base_url": None
        }

    # IMPORTANT: target_db is now deprecated - connection info comes from _data-source.md
    # Remove it from data to avoid validation errors
    data.pop("target_db", None)
    
    data.setdefault("llm_config", {})
    data.setdefault("embedding_config", {})
    data.setdefault("vector_config", {})
    data.setdefault("app_meta", {})

    settings = AgentSettings(**data)
    return _apply_runtime_defaults(settings)


def _load_v2_settings(data: dict) -> AgentSettingsV2:
    """Load v2 settings format.
    
    Note: Data sources are NEVER loaded from agent_settings.json.
    They are always loaded from skills/_data-source.md files.
    The data_sources field is deprecated and ignored.
    """
    normalized = {
        "data_sources": [],  # Always empty - data sources come from skills directory
        "primary_source_id": None,  # Not used when loading from skills
        "llm_config": data.get("llm_config", {}),
        "embedding_config": data.get("embedding_config", {}),
        "vector_config": data.get("vector_config", {}),
        "app_meta": data.get("app_meta", {})
    }

    settings_v2 = AgentSettingsV2(**normalized)
    return _apply_runtime_defaults(settings_v2)


def load_settings() -> Union[AgentSettings, AgentSettingsV2]:
    """Load settings from file, handling both v1 and v2 formats.
    
    Note: Data sources are NEVER loaded from agent_settings.json.
    The presence of 'data_sources' key is ignored - all data sources
    are loaded from skills/_data-source.md files.
    """
    if not os.path.exists(SETTINGS_FILE):
        return get_default_settings()

    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Settings file must be a JSON object")

        # Always load as v1 format (skills-based data sources)
        # The 'data_sources' key is deprecated and ignored
        return _load_v1_settings(data)

    except Exception as e:
        print(f"Error loading settings: {e}")
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
    DEPRECATED: Data sources are no longer stored in agent_settings.json.
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
    DEPRECATED: Data sources are no longer stored in agent_settings.json.
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
    DEPRECATED: Data sources are no longer stored in agent_settings.json.
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
    """Save settings to file.
    
    Note: Data sources are NEVER saved to agent_settings.json.
    They are only managed via skills/_data-source.md files.
    """
    try:
        # Ensure config directory exists
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        # Prepare for save - remove debug fields
        data = agent_settings.model_dump()
        
        # CRITICAL: Remove data_sources and primary_source_id if present
        # Data sources are ONLY stored in skills directory, never in agent_settings.json
        data.pop('data_sources', None)
        data.pop('primary_source_id', None)
        
        if 'target_db' in data:
             if 'connection_string_decrypted' in data['target_db']:
                del data['target_db']['connection_string_decrypted']
             if 'python_connection_string_decrypted' in data['target_db']:
                del data['target_db']['python_connection_string_decrypted']

        # Ensure env defaults are persisted if missing in the object to be saved
        # This handles cases where frontend might send empty values but we want to persist active env config
        llm_conf = data.get('llm_config', {})
        
        # Check API Key
        # Force check if key is falsy (None or empty string)
        if not llm_conf.get('llm_api_key') and app_settings.OPENAI_API_KEY:
             llm_conf['llm_api_key'] = app_settings.OPENAI_API_KEY
             
        # Check Model
        if not llm_conf.get('llm_model') and app_settings.OPENAI_MODEL:
             llm_conf['llm_model'] = app_settings.OPENAI_MODEL
             
        # Check Endpoint
        # If endpoint is missing, and we have a valid OpenAI key (either existing or just populated), default to OpenAI
        current_key = llm_conf.get('llm_api_key')
        if not llm_conf.get('llm_endpoint') and current_key and str(current_key).startswith("sk-"):
             llm_conf['llm_endpoint'] = "https://api.openai.com/v1"
             
        data['llm_config'] = llm_conf

        # Embedding config defaults
        emb_conf = data.get('embedding_config', {})
        if not emb_conf.get('api_key') and app_settings.OPENAI_API_KEY:
            emb_conf['api_key'] = app_settings.OPENAI_API_KEY
        if not emb_conf.get('base_url') and app_settings.OPENAI_EMBEDDING_ENDPOINT:
            emb_conf['base_url'] = app_settings.OPENAI_EMBEDDING_ENDPOINT
        data['embedding_config'] = emb_conf

        # Vector config defaults (persist existing file values, not .env)
        vec_conf = data.get('vector_config', {})
        current_settings_on_disk = load_settings()
        if not vec_conf.get('host'):
            vec_conf['host'] = current_settings_on_disk.vector_config.host
        if not vec_conf.get('port'):
            vec_conf['port'] = current_settings_on_disk.vector_config.port
        data['vector_config'] = vec_conf

        # --- FIX: Handle Masked Text from Frontend ---
        # If the frontend sends back a masked string (e.g. "sk-...1234"), 
        # we must NOT save that literal string. We should keep the existing key.
        
        # Load current settings from disk to compare
        current_settings_on_disk = load_settings()
        
        # 1. Check Embedding API Key
        incoming_emb_key = data.get('embedding_config', {}).get('api_key')
        if incoming_emb_key and isinstance(incoming_emb_key, str):
            if "..." in incoming_emb_key and incoming_emb_key.startswith("sk-"):
                # It looks like a masked key. 
                # Be conservative: if it matches the masked version of the current key, or just looks masked, restore original.
                current_emb_key = current_settings_on_disk.embedding_config.api_key
                if current_emb_key:
                    # Check if restoring is appropriate
                    # (Simple check: if we mask the current key, does it equal the incoming one?)
                    key_str = str(current_emb_key)
                    expected_mask = f"{key_str[:3]}...{key_str[-4:]}" if len(key_str) > 10 else key_str
                    
                    if incoming_emb_key == expected_mask:
                        data['embedding_config']['api_key'] = current_emb_key
                    else:
                        # Fallback: If it definitely looks like a mask but doesn't match roughly, 
                        # it's safer to keep the old valid key than save "..." which will break everything.
                        # Unless the user literally typed "sk-...".
                        # For now, let's assume if it has "..." it's a mask.
                        data['embedding_config']['api_key'] = current_emb_key

        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save settings: {e}")
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
    settings.embedding_config.api_key = _mask_api_key(settings.embedding_config.api_key)
    return settings
