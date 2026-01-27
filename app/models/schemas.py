from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal
from enum import Enum
import time


# --- Shared Models ---

class ColumnInfo(BaseModel):
    name: str
    data_type: str
    description: Optional[str] = None

class TableSchema(BaseModel):
    schema_name: str
    table_name: str
    table_type: Optional[str] = "table"  # 'table' or 'view'
    description: Optional[str] = None  # Rich Markdown description (also used for embedding)
    columns: List[ColumnInfo] = []
    
class DiscoveryContext(BaseModel):
    relevant_tables: List[TableSchema]
    similar_queries: Any = [] # Disable validation for now
    glossary_terms: Dict[str, str] = {}
    
# --- API Request/Response ---

class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="User's natural language question")
    top_k: int = 5

class DiscoveryResponse(BaseModel):
    query: str
    reasoning: str
    context: DiscoveryContext

class GenerateSQLRequest(BaseModel):
    query: str
    context: Optional[DiscoveryContext] = None # Can be passed from frontend if they modified the discovery result
    previousSQL: Optional[str] = None # Previous SQL query for reference
    queryHistory: Optional[str] = None # Accumulated query history from conversation
    forceGeneral: bool = False # If True, skip classification and go straight to general LLM chat
    queryMode: Literal["generate", "search"] = "generate"  # "generate" for SQL generation, "search" for object search
    table_override: Optional[List[str]] = None # Explicit schema.table list from user selection

class SearchObject(BaseModel):
    schema_name: str = Field(..., alias="schema")
    name: str
    type: Optional[str] = None
    model_config = {"populate_by_name": True}

class GenerateSQLResponse(BaseModel):
    sql: str
    explanation: Optional[str] = None
    query_type: str = "database"  # "database" or "general"
    context_text: Optional[str] = None  # The raw context sent to LLM (last one)
    context_history: Optional[List[str]] = None # History of contexts for each attempt
    objects: Optional[List[SearchObject]] = None

class AgentStatus(BaseModel):
    step_id: int
    message: str
    type: str = "status" # "status", "result", "error"
    details: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)

class ExecutePythonRequest(BaseModel):
    code: str
    context: Optional[Dict[str, Any]] = None


class ChartRecommendation(BaseModel):
    chart_type: Literal['bar', 'line', 'pie', 'scatter', 'kpi', 'none']
    x_axis: Optional[str] = None
    y_axis: Optional[List[str]] = None
    title: Optional[str] = None
    explanation: Optional[str] = None
    colors: Optional[List[str]] = None

class ExecutePythonResponse(BaseModel):
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    recommendation: Optional[ChartRecommendation] = None
    execution_time: float



# --- Admin / Knowledge Management Models ---

class AdminSchemaStatus(BaseModel):
    schema_name: str
    table_name: str
    table_type: Optional[str] = "table"  # 'table' or 'view'
    is_indexed: bool
    description: Optional[str] = None  # Rich Markdown description (also used for embedding)
    column_count: int
    last_updated: Optional[str] = None

class FewShotItem(BaseModel):
    id: Optional[str] = None # Milvus ID (string to handle large integers)
    question: str
    sql_query: str  # Also used for R code and SAS code
    knowledge_type: str = "sql_query"  # "general", "sql_query", "r_code", "sas_code"
    verified: bool = False

class ValueIndexItem(BaseModel):
    id: Optional[str] = None
    value: str
    schema_name: str
    table_name: str
    column_name: str
    metadata: Dict[str, Any] = {}
    
class ValueIndexConfig(BaseModel):
    table_name: str
    column_name: str
    is_indexed: bool = False
    
class SyncRequest(BaseModel):
    target_tables: Optional[List[str]] = None # If None, sync all
    force_update: bool = False

class BatchSyncRequest(BaseModel):
    table_names: List[str] = Field(..., description="List of table names to sync (format: 'table' or 'schema.table')")

class BatchSyncResult(BaseModel):
    table_name: str
    schema_name: str
    success: bool
    message: str

class BatchSyncResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[BatchSyncResult]


AuthType = Literal[
    "sql",
    "windows",
    "ad_integrated",
    "ad_password",
    "ad_interactive",
    "ad_service_principal"
]

# --- Settings / Configuration Models ---

class TargetDBConfig(BaseModel):
    friendly_name: str = "Northwind Database"
    description: str = "Sales database for imported and exported specialty foods"
    keywords: List[str] = ["sales", "customers", "orders", "products", "employees", "shipping"]
    db_type: str = "mssql"  # mssql, postgresql, mysql, etc.
    server: str = ""
    database_name: str = ""
    connection_string_encrypted: str = ""  # AES encrypted connection string
    connection_string_decrypted: Optional[str] = None # Debug field, not persisted
    driver: str = "ODBC Driver 17 for SQL Server"
    auth_type: AuthType = "sql"
    username: Optional[str] = None
    trust_server_certificate: Optional[bool] = False
    python_connection_string_encrypted: Optional[str] = None
    python_connection_string_decrypted: Optional[str] = None

class LLMConfig(BaseModel):
    llm_model: str = "gpt-4o"
    temperature: float = 0.0
    llm_endpoint: Optional[str] = None
    llm_api_key: Optional[str] = None

class FetchModelsRequest(BaseModel):
    llm_endpoint: str
    llm_api_key: Optional[str] = None

class FetchModelsResponse(BaseModel):
    models: List[Dict[str, str]]

class EmbeddingConfig(BaseModel):
    provider: str = "openai"  # openai, azure, huggingface, openai_compatible
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    
class VectorConfig(BaseModel):
    provider: str = "milvus"  # milvus, pinecone, weaviate, etc.
    host: str = "localhost"
    port: str = "19630"
    # embedding_model field removed from here, moved to EmbeddingConfig

class AppMeta(BaseModel):
    app_name: str = "Octofy AI Agent"
    version: str = "1.0.0"
    project_name: str = "Database AI Agent"

class AgentSettings(BaseModel):
    target_db: TargetDBConfig
    llm_config: LLMConfig
    embedding_config: EmbeddingConfig
    vector_config: VectorConfig
    app_meta: AppMeta

AuthType = Literal[
    "sql",
    "windows",
    "ad_integrated",
    "ad_password",
    "ad_interactive",
    "ad_service_principal"
]

class ConnectionTestRequest(BaseModel):
    driver: str = "ODBC Driver 17 for SQL Server"
    server: str
    database: str
    auth_type: AuthType = "sql"
    username: Optional[str] = None
    password: Optional[str] = None
    trust_server_certificate: Optional[bool] = False
    
class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    connection_string_masked: Optional[str] = None

# --- Contribution Library Models ---

class ContributionItem(BaseModel):
    id: Optional[str] = None  # Milvus ID (string to handle large integers)
    question: str
    sql_query: str
    knowledge_type: Optional[str] = "sql_query"  # "general", "sql_query", "r_code", "sas_code"
    submitted_at: Optional[str] = None  # ISO timestamp
    user_id: Optional[str] = None  # Optional user identifier
    status: str = "pending"  # "pending", "approved", "rejected"
    similarity_score: Optional[float] = None  # Similarity to existing knowledge base items
    similar_to_id: Optional[str] = None  # ID of most similar existing item if found

class ContributionRequest(BaseModel):
    question: str
    sql_query: str
    knowledge_type: Optional[str] = "sql_query"
    user_id: Optional[str] = None

class ContributionResponse(BaseModel):
    success: bool
    message: str
    contribution_id: Optional[str] = None
    similarity_warning: bool = False  # True if similar item exists in knowledge base
    similarity_score: Optional[float] = None

class ApproveContributionRequest(BaseModel):
    contribution_id: str
    edited_question: Optional[str] = None
    edited_sql: Optional[str] = None  # Allow editing the question during approval
    knowledge_type: Optional[str] = None

class ApproveContributionResponse(BaseModel):
    success: bool
    message: str
    knowledge_base_id: Optional[str] = None  # ID in the knowledge base after approval
