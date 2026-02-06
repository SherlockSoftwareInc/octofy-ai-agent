from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Database AI Agent"
    API_V1_STR: str = "/api/v1"
    
    # Vector DB (Milvus)
    VECTOR_DB_ENABLED: bool = True
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: str = "19630"
    MILVUS_COLLECTION_SCHEMA: str = "schema_index"  # Legacy collection (v1)
    MILVUS_COLLECTION_SCHEMA_V2: str = "schema_index_v2"  # Multi-source collection with SP/Function support
    MILVUS_COLLECTION_FEWSHOT: str = "fewshot_index"  # Legacy alias for knowledge_base
    MILVUS_COLLECTION_KNOWLEDGE_BASE: str = "knowledge_base"  # Renamed from fewshot_index
    MILVUS_COLLECTION_CONTRIBUTIONS: str = "contribution_library"  # Staging area for user contributions
    MILVUS_COLLECTION_VALUES: str = "value_index"
    
    # LLM (OpenAI compatible)
    OPENAI_API_KEY: str = "sk-..." 
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_ENDPOINT: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENAI_EMBEDDING_ENDPOINT",
            "OPENAI_EMBEDDING",
            "openai_embedding",
        ),
    )
    
    # Database
    SQL_SERVER_CONNECTION_STRING: Optional[str] = None
    
    # PostgreSQL for user management
    POSTGRES_USER: str = "octofy"
    POSTGRES_PASSWORD: str = "octofy_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "octofy_users"
    
    # API Security
    API_KEY: str = "change-this-to-a-secure-key"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "change-this-to-a-secure-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    
    # Code Advisor settings
    CODE_ADVISOR_RATE_LIMIT: int = 10  # Maximum requests per window
    CODE_ADVISOR_RATE_WINDOW: int = 60  # Time window in seconds
    CODE_ADVISOR_TEMPERATURE: float = 0.3  # LLM temperature for conversational advice
    
    # Join-Path Validation
    ENABLE_JOIN_PATH_VALIDATION: bool = True  # Use enhanced join-path validation (vs legacy sufficiency check)
    
settings = Settings()
