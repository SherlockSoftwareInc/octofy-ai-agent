from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Database AI Agent"
    API_V1_STR: str = "/api/v1"
    
    # Vector DB (Milvus)
    VECTOR_DB_ENABLED: bool = True
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: str = "19530"
    MILVUS_COLLECTION_SCHEMA: str = "schema_index"
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
    
    # API Security
    API_KEY: str = "change-this-to-a-secure-key"
    
settings = Settings()
