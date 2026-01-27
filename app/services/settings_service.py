"""
Settings Service - Manages agent configuration with encryption for sensitive data
"""
import json
import os
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
import base64
from app.models.schemas import AgentSettings, TargetDBConfig, LLMConfig, VectorConfig, EmbeddingConfig, AppMeta
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
    return AgentSettings(
        target_db=TargetDBConfig(
            friendly_name="Northwind Database",
            description="Sales database for imported and exported specialty foods",
            keywords=["sales", "customers", "orders", "products", "employees", "shipping"],
            db_type="mssql",
            server="",
            database_name="",
            connection_string_encrypted="",
            python_connection_string_encrypted="",
            driver="ODBC Driver 17 for SQL Server",
            auth_type="sql",
            username=None,
            trust_server_certificate=False
        ),
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

def load_settings() -> AgentSettings:
    """Load settings from file, return defaults if not found"""
    if not os.path.exists(SETTINGS_FILE):
        return get_default_settings()
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
            
            if not isinstance(data, dict):
                raise ValueError("Settings file must be a JSON object")
            
            # --- MIGRATION LOGIC ---
            # If embedding_config is missing, migrate from vector_config
            if "embedding_config" not in data:
                print("Migrating old vector config to new embedding config...")
                vec_conf = data.get("vector_config", {})
                old_model = vec_conf.get("embedding_model", "text-embedding-3-small")
                
                # Assume OpenAI default for migration
                data["embedding_config"] = {
                    "provider": "openai",
                    "model": old_model,
                    "dimensions": 1536, # Default for text-embedding-3-small
                    "api_key": None,
                    "base_url": None
                }
                # vector_config will be cleaned up by Pydantic model validation (extra fields ignored/removed)
            elif data.get("embedding_config") is None:
                data["embedding_config"] = {}
            
            if data.get("target_db") is None:
                data["target_db"] = {}
            if data.get("llm_config") is None:
                data["llm_config"] = {}
            if data.get("vector_config") is None:
                data["vector_config"] = {}
            if data.get("app_meta") is None:
                data["app_meta"] = {}
            
            data.setdefault("target_db", {})
            data.setdefault("llm_config", {})
            data.setdefault("embedding_config", {})
            data.setdefault("vector_config", {})
            data.setdefault("app_meta", {})
            
            settings = AgentSettings(**data)
            
            # Populate defaults from environment if missing
            if not settings.llm_config.llm_api_key and app_settings.OPENAI_API_KEY:
                settings.llm_config.llm_api_key = app_settings.OPENAI_API_KEY
                
            if not settings.llm_config.llm_model and app_settings.OPENAI_MODEL:
                settings.llm_config.llm_model = app_settings.OPENAI_MODEL
                
            # Default endpoint for OpenAI if missing
            if not settings.llm_config.llm_endpoint and settings.llm_config.llm_api_key and str(settings.llm_config.llm_api_key).startswith("sk-"):
                settings.llm_config.llm_endpoint = "https://api.openai.com/v1"

            # Embedding config fallbacks
            if not settings.embedding_config.api_key and app_settings.OPENAI_API_KEY:
                settings.embedding_config.api_key = app_settings.OPENAI_API_KEY
            if not settings.embedding_config.base_url and app_settings.OPENAI_EMBEDDING_ENDPOINT:
                settings.embedding_config.base_url = app_settings.OPENAI_EMBEDDING_ENDPOINT

            # Vector config fallbacks (do not read from .env)
            if not settings.vector_config.host:
                settings.vector_config.host = "localhost"
            if not settings.vector_config.port:
                settings.vector_config.port = "19630"
                
            return settings
    except Exception as e:
        print(f"Failed to load settings: {e}")
        return get_default_settings()

def save_settings(agent_settings: AgentSettings) -> bool:
    """Save settings to file"""
    try:
        # Ensure config directory exists
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        # Prepare for save - remove debug fields
        data = agent_settings.model_dump()
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

def get_settings_for_display() -> AgentSettings:
    """Get settings with masked sensitive data for frontend display"""
    settings = load_settings()
    
    # Decrypt and mask connection string for display
    if settings.target_db.connection_string_encrypted:
        decrypted = decrypt_string(settings.target_db.connection_string_encrypted)
        # Parse server and database from connection string if empty
        if decrypted:
            import re
            server_match = re.search(r'SERVER=([^;]+)', decrypted, re.IGNORECASE)
            db_match = re.search(r'DATABASE=([^;]+)', decrypted, re.IGNORECASE)
            
            server = server_match.group(1) if server_match else settings.target_db.server
            database = db_match.group(1) if db_match else settings.target_db.database_name
            
            # Create a new settings object with updated values
            settings = AgentSettings(
                target_db=TargetDBConfig(
                    friendly_name=settings.target_db.friendly_name,
                    description=settings.target_db.description,
                    keywords=settings.target_db.keywords,
                    db_type=settings.target_db.db_type,
                    server=server,
                    database_name=database,
                    connection_string_encrypted=settings.target_db.connection_string_encrypted,
                    connection_string_decrypted=None,
                    python_connection_string_encrypted=settings.target_db.python_connection_string_encrypted,
                    python_connection_string_decrypted=None,
                    driver=settings.target_db.driver,
                    auth_type=settings.target_db.auth_type,
                    username=settings.target_db.username,
                    trust_server_certificate=settings.target_db.trust_server_certificate
                ),
                llm_config=settings.llm_config,
                embedding_config=settings.embedding_config, # Start with raw config
                vector_config=settings.vector_config,
                app_meta=settings.app_meta
            )
            
            # Mask Embedding API Key if present
            if settings.embedding_config.api_key:
                 # Simple masking: sk-...1234
                 key_str = str(settings.embedding_config.api_key)
                 if len(key_str) > 10:
                     masked = f"{key_str[:3]}...{key_str[-4:]}"
                     # We can't modify the model in place cleanly if it's frozen, 
                     # but Pydantic models are mutable by default.
                     # However, creating a copy is safer.
                     settings.embedding_config.api_key = masked

    return settings
