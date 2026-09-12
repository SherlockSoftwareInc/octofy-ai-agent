from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices, field_validator
from typing import Optional, Dict
from pathlib import Path
import json

_ROOT_ENV = str(Path(__file__).resolve().parents[2] / ".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, env_file_encoding="utf-8")
    PROJECT_NAME: str = "Database AI Agent"
    API_V1_STR: str = "/api/v1"
    
    # Vector DB (Milvus)
    VECTOR_DB_ENABLED: bool = True
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: str = "19630"
    MILVUS_COLLECTION_SCHEMA: str = "schemas"
    MILVUS_COLLECTION_SCHEMA_V2: str = "schemas"
    MILVUS_COLLECTION_FEWSHOT: str = "few_shots"
    MILVUS_COLLECTION_KNOWLEDGE_BASE: str = "few_shots"
    MILVUS_COLLECTION_CONTRIBUTIONS: str = "contribution_library"
    MILVUS_COLLECTION_VALUES: str = "value_index"
    
    # LLM Configuration (Provider Agnostic)
    # Supports any OpenAI-compatible API: OpenAI, DeepSeek, Ollama, Azure, etc.
    # Uses LiteLLM for maximum provider compatibility
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_ENDPOINT: Optional[str] = None  # Base URL for OpenAI-compatible endpoints
    LLM_TEMPERATURE: float = 0.0

    # Embedding Configuration (Provider Agnostic)
    # Supports: openai, azure, openai_compatible, huggingface
    # Works with any OpenAI-compatible embedding API
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_BASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "EMBEDDING_BASE_URL",
            "embedding_base_url",
            "LLM_EMBEDDING_ENDPOINT",
            "llm_embedding_endpoint",
        ),
    )  # Supports legacy LLM_EMBEDDING_ENDPOINT for backward compatibility
    LLM_EMBEDDING_ENDPOINT: Optional[str] = None  # Deprecated; kept for backward compatibility
    EMBEDDING_API_KEY: Optional[str] = None  # Falls back to LLM_API_KEY if not set
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    VECTOR_PROVIDER: str = "milvus"
    VECTOR_HOST: str = "localhost"
    VECTOR_PORT: str = "19630"
    VECTOR_SQLITE_PATH: Optional[str] = None  # default: ./data/vector-index.sqlite
    BUILTIN_SQL_GENERATOR: bool = True
    PRECOMPUTED_QUERY_DIRECT_MATCH_THRESHOLD: float = 0.93
    PRECOMPUTED_QUERY_FEW_SHOT_THRESHOLD: float = 0.82
    OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD: float = 0.50
    ENABLE_BM25_RETRIEVAL: bool = False
    BM25_WEIGHT: float = 0.5
    BM25_K1: float = 1.2
    BM25_B: float = 0.75
    ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE: Dict[str, bool] = Field(default_factory=dict)
    SEMANTIC_COMPILATION_FALLBACK_TO_RAW_SQL: bool = True
    ENABLE_AI_DATA_ANALYSIS: bool = True

    APP_NAME: str = "Octofy AI Agent"
    APP_VERSION: str = "1.0.0"
    
    # Database
    SQL_SERVER_CONNECTION_STRING: Optional[str] = None
    
    # PostgreSQL for user management
    POSTGRES_USER: str = "octofy"
    POSTGRES_PASSWORD: str = "***REMOVED***"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "octofy_users"
    
    # API Security
    API_KEY: str = "change-this-to-a-secure-key"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "***REMOVED***"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    
    # Code Advisor settings
    CODE_ADVISOR_RATE_LIMIT: int = 10  # Maximum requests per window
    CODE_ADVISOR_RATE_WINDOW: int = 60  # Time window in seconds
    CODE_ADVISOR_TEMPERATURE: float = 0.3  # LLM temperature for conversational advice
    
    # Join-Path Validation
    ENABLE_JOIN_PATH_VALIDATION: bool = True  # Use enhanced join-path validation (vs legacy sufficiency check)

    @field_validator("ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE", mode="before")
    @classmethod
    def _parse_semantic_layer_map(cls, value):
        if value is None or value == "":
            return {}
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE must be a JSON object")
            return parsed
        return value

    def semantic_layer_enabled_for(self, source_id: Optional[str]) -> Optional[bool]:
        """Return the per-source semantic-layer flag, or None when unset."""
        if not source_id:
            return None
        mapping = self.ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE or {}
        if source_id not in mapping:
            return None
        return bool(mapping[source_id])

    def object_search_vector_score_threshold(self) -> float:
        return max(0.0, min(1.0, float(self.OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD)))
    
settings = Settings()
