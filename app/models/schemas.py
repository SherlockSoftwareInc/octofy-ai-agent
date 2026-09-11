from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal
from enum import Enum
import time
import uuid


# --- Shared Models ---

class ObjectType(str, Enum):
    """Database object types supported in schema tree"""
    TABLE = "table"
    VIEW = "view"
    STORED_PROCEDURE = "stored_procedure"
    FUNCTION = "function"

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
    source_guid: Optional[str] = None  # Links to data source for partitioning

class DataObject(BaseModel):
    """Unified model for all database objects (tables, views, SPs, functions)"""
    source_id: Optional[str] = None  # Links to data source
    schema_name: str
    object_name: str
    object_type: ObjectType
    description: Optional[str] = None
    definition: Optional[str] = None  # For stored procedures and functions
    parameters: Optional[List[Dict[str, Any]]] = []  # For stored procedures and functions
    return_type: Optional[str] = None  # For functions
    columns: List[ColumnInfo] = []  # For tables and views
    
class DiscoveryContext(BaseModel):
    relevant_tables: List[TableSchema]
    similar_queries: Any = [] # Disable validation for now
    glossary_terms: Dict[str, str] = {}
    
# --- API Request/Response ---

class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="User's natural language question")
    top_k: int = 5
    source_id: Optional[str] = None  # Required by POST /discovery (HTTP layer)

class DiscoveryResponse(BaseModel):
    query: str
    reasoning: str
    context: DiscoveryContext


# --- Schema Sufficiency Check Models ---

class RequiredDataPoint(BaseModel):
    """A single data point required to answer the user's query"""
    name: str  # e.g., "customer name", "order total", "sales tax"
    column_mapping: Optional[str] = None  # e.g., "[dbo].[Customers].[CustomerName]" or None if not found
    found: bool = False
    reasoning: str = ""  # Why this data point is needed


class SchemaSufficiencyResult(BaseModel):
    """Result of the pre-flight schema sufficiency check"""
    status: Literal["sufficient", "insufficient_data"] = "sufficient"
    required_data_points: List[RequiredDataPoint] = []
    missing_data_points: List[RequiredDataPoint] = []
    search_suggestions: List[str] = []  # Suggested search terms for missing data
    analysis: str = ""  # LLM's reasoning about sufficiency


# --- Join-Path Validation Models ---

class ValidationDetail(BaseModel):
    """A single validation check performed during join-path validation"""
    requirement: str  # e.g., "customer name column"
    mapping: Optional[str] = None  # e.g., "[dbo].[Customers].[CustomerName]" or "DERIVED: ..."
    found: bool = False
    reason: str = ""  # Why this passed/failed


class JoinPathValidationResult(BaseModel):
    """Result of the enhanced join-path schema validation (replaces SchemaSufficiencyResult for new flow)"""
    status: Literal["sufficient", "insufficient_data", "insufficient_joins"] = "sufficient"
    join_path: Optional[str] = None  # e.g., "Orders -> OrderDetails ON OrderID -> Products ON ProductID"
    validation_details: List[ValidationDetail] = []
    missing_logic: Optional[str] = None  # e.g., "No FK path between Customers and Invoices"
    search_suggestions: List[str] = []  # Suggested search terms for auto-discovery
    analysis: str = ""  # LLM's reasoning about sufficiency


# Define chart types as a reusable type alias for consistency
ChartTypeLiteral = Literal['line', 'pie', 'scatter', 'column', 'stackedColumn', 'clusteredColumn', 'area', 'radar', 'treemap', 'funnel', 'none']

class GenerateSQLRequest(BaseModel):
    query: str
    context: Optional[DiscoveryContext] = None # Can be passed from frontend if they modified the discovery result
    previousSQL: Optional[str] = None # Previous SQL query for reference
    queryHistory: Optional[str] = None # Accumulated query history from conversation
    database_objects: Optional[List[str]] = None # Prioritized tables/views/columns for generation
    existing_code: Optional[str] = None # Base code for optimization or expansion
    error_message: Optional[str] = None # Error message or stack trace for debugging
    is_user_code: bool = False # True if provided code was written by the user
    forceGeneral: bool = False # If True, skip classification and go straight to general LLM chat
    queryMode: Literal["generate", "search", "plan", "ask", "code_advisor"] = "generate"
    table_override: Optional[List[str]] = None # Explicit schema.table list from user selection
    chart_type_override: Optional[ChartTypeLiteral] = None  # User-specified chart type
    user_selected_tables: Optional[List[str]] = None  # User's checkbox selections from threshold prompt
    planning_context: Optional[Dict[str, Any]] = None  # Structured planning state for conversational exploration
    source_id: Optional[str] = None  # Required by generate-sql/python/r/sas HTTP endpoints
    top_k: Optional[int] = None
    semantic_mode: Optional[bool] = None


# --- Turn-Type Classification Models ---

class TurnType(str, Enum):
    """Classification of user message intent relative to planning context"""
    REFINEMENT = "refinement"      # Adding detail to existing goal
    CORRECTION = "correction"      # Changing a specific detail
    PIVOT = "pivot"                # Switching topics
    CONFIRMATION = "confirmation"  # Agreeing to proceed
    CLARIFICATION = "clarification" # Answering system questions
    TABLE_SELECTION = "table_selection"  # User selected/deselected tables without text input


class IntentData(BaseModel):
    """Enhanced intent analysis with turn-type classification"""
    # Existing fields (preserve backward compatibility)
    goal_clear: bool
    goal_statement: str
    critical_ambiguities: List[str] = []
    ready_for_search: bool
    required_questions: List[Dict[str, Any]] = []
    requirements_extracted: List[Dict[str, Any]] = []
    
    # NEW: Turn-type classification fields
    turn_type: TurnType
    topic_similarity: float = Field(ge=0.0, le=1.0, description="Similarity to previous goal (0-1)")
    confidence_in_classification: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    changed_requirements: List[str] = []
    new_requirements: List[str] = []
    removed_requirements: List[str] = []
    needs_pivot_confirmation: bool = False


class SearchObject(BaseModel):
    schema_name: str = Field(..., alias="schema")
    name: str
    type: Optional[str] = None
    auto_checked: Optional[bool] = False  # High-confidence flag for essential tables
    model_config = {"populate_by_name": True}

class GenerateSQLResponse(BaseModel):
    sql: str
    explanation: Optional[str] = None
    query_type: str = "database"  # "database" or "general"
    context_text: Optional[str] = None  # The raw context sent to LLM (last one)
    context_history: Optional[List[str]] = None # History of contexts for each attempt
    objects: Optional[List[SearchObject]] = None
    discovery_branch: Optional[str] = None  # "kb_direct", "kb_gap_fill", or "dual_prong"
    source_id: Optional[str] = None  # Data source ID to use when executing this SQL
    is_code_edit: Optional[bool] = None  # If True, frontend should update the previous code box in place
    success: Optional[bool] = None
    attempts: Optional[int] = None
    token_usage: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[int] = None
    hallucination_count: Optional[int] = None
    agentic_retry_count: Optional[int] = None
    canonical_question: Optional[str] = None
    error_category: Optional[str] = None
    failure_report: Optional[Dict[str, Any]] = None
    tool_event: Optional[str] = None  # Discuss/Ask tool chip name when a lookup ran

class AgentStatus(BaseModel):
    step_id: int
    message: str
    type: str = "status" # "status", "result", "error"
    details: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)

class ExecutePythonRequest(BaseModel):
    code: str
    context: Optional[Dict[str, Any]] = None
    chart_type_override: Optional[ChartTypeLiteral] = None  # User-specified chart type
    preserved_x_axis: Optional[str] = None  # Preserve original x_axis column when changing chart type
    preserved_y_axis: Optional[List[str]] = None  # Preserve original y_axis columns when changing chart type
    enable_profiling: Optional[bool] = False  # Enable data profiling and insights generation
    source_id: Optional[str] = None  # Required by POST /execute-python (HTTP layer)


class ExecuteSQLRequest(BaseModel):
    sql: str  # SQL query to execute
    context: Optional[Dict[str, Any]] = None  # Optional execution context (user_query, schema_context, etc.)
    source_id: Optional[str] = None  # Required by POST /execute-sql (HTTP layer)
    chart_type_override: Optional[ChartTypeLiteral] = None  # User-specified chart type preference
    preserved_x_axis: Optional[str] = None  # Preserve original x_axis column when changing chart type
    preserved_y_axis: Optional[List[str]] = None  # Preserve original y_axis columns when changing chart type
    timeout_seconds: Optional[int] = 60  # Configurable timeout for query execution (default: 60 seconds)
    max_rows: Optional[int] = 10000  # Row limit for results to prevent memory exhaustion
    enable_profiling: Optional[bool] = False  # Enable data profiling and insights generation


class ChartRecommendation(BaseModel):
    chart_type: ChartTypeLiteral
    x_axis: Optional[str] = None
    y_axis: Optional[List[str]] = None
    title: Optional[str] = None
    explanation: Optional[str] = None
    colors: Optional[List[str]] = None


# --- Workflow Analysis Models ---

class NumericStats(BaseModel):
    """Statistical profile for numeric columns"""
    min: float
    max: float
    mean: float
    median: float
    std: float
    q25: float
    q75: float
    null_count: int
    null_percentage: float
    outliers: List[Any] = []  # Values beyond 3*IQR


class CategoricalStats(BaseModel):
    """Statistical profile for categorical columns"""
    unique_count: int
    top_values: List[Dict[str, Any]] = []  # [{value, count, percentage}]
    null_count: int
    null_percentage: float


class ColumnProfile(BaseModel):
    """Profile for a single column"""
    column_name: str
    data_type: str
    numeric_stats: Optional[NumericStats] = None
    categorical_stats: Optional[CategoricalStats] = None


class DataProfile(BaseModel):
    """Complete data profiling result"""
    row_count: int
    column_count: int
    columns: List[ColumnProfile]
    correlations: Optional[List[Dict[str, Any]]] = None  # [{col1, col2, correlation}]
    has_datetime: bool = False
    datetime_columns: List[str] = []
    profiling_level: Literal["basic", "distribution", "relationship"] = "basic"


class Insight(BaseModel):
    """Generated insight from data analysis"""
    insight_type: Literal["outlier", "trend", "correlation", "missing_data", "distribution", "recommendation"]
    title: str
    description: str
    severity: Literal["info", "warning", "critical"] = "info"
    related_columns: List[str] = []
    confidence: float = 1.0  # 0-1 score


class RefinementIntent(BaseModel):
    """Detected user refinement intent"""
    intent_type: Literal["drill_down", "filter", "compare", "trend", "forecast", "new_query"]
    confidence: float  # 0-1 score
    target_columns: List[str] = []  # e.g., ["region"] for drill_down
    comparison_dimension: Optional[str] = None  # e.g., "year" for temporal comparison
    filter_values: List[str] = []


class AnalysisContext(BaseModel):
    """Workflow analysis context for a message"""
    data_profile: Optional[DataProfile] = None
    insights: List[Insight] = []
    refinement_history: List[Dict[str, Any]] = []  # [{intent, query, timestamp}]
    suggested_refinements: List[str] = []  # Prompt suggestions


class WorkflowTemplate(BaseModel):
    """Reusable workflow template"""
    id: str
    name: str
    description: str
    query_pattern: str  # Original user query
    tables_used: List[str]
    refinement_sequence: List[Dict[str, str]] = []  # [{step, intent, description}]
    created_at: str
    user_id: str  # For per-user storage


class ExecutePythonResponse(BaseModel):
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    recommendation: Optional[ChartRecommendation] = None
    execution_time: float
    data_profile: Optional[DataProfile] = None  # NEW: Auto-generated data profile
    insights: List[Insight] = []  # NEW: Auto-generated insights
    code: Optional[str] = None  # NEW: The final working code (if auto-fixed)
    auto_fixed: bool = False  # NEW: Flag indicating auto-retry happened
    fix_attempt: int = 1  # NEW: Which attempt succeeded (1-5)
    original_error: Optional[str] = None  # NEW: Original error before auto-fix


class ExecuteSQLResponse(BaseModel):
    success: bool
    output: Optional[Any] = None  # Structured query results (columns + rows)
    error: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None  # List of result sets (for multi-query support)
    recommendation: Optional[ChartRecommendation] = None
    execution_time: float = 0.0
    rows_affected: Optional[int] = None  # Number of rows returned or affected
    data_profile: Optional[DataProfile] = None  # Auto-generated data profile
    insights: List[Insight] = []  # Auto-generated insights
    sql: Optional[str] = None  # The final working SQL (if auto-fixed)
    auto_fixed: bool = False  # Flag indicating auto-retry happened
    fix_attempt: int = 1  # Which attempt succeeded (1-5)
    original_error: Optional[str] = None  # Original error before auto-fix



# --- Admin / Knowledge Management Models ---

class AdminSchemaStatus(BaseModel):
    schema_name: str
    table_name: str  # display name; same as object_name from the schemas collection
    object_name: Optional[str] = None
    object_type: Optional[str] = None
    table_type: Optional[str] = "table"
    entity_type: Optional[str] = None
    is_indexed: bool
    description: Optional[str] = None
    column_count: int
    last_updated: Optional[str] = None
    source_id: Optional[str] = None

class FewShotItem(BaseModel):
    id: Optional[str] = None # Milvus ID (string to handle large integers)
    question: str
    sql_query: str  # Also used for R code and SAS code
    knowledge_type: str = "sql_query"  # "general", "sql_query", "r_code", "sas_code"
    verified: bool = False
    source_id: Optional[str] = None

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
    source_id: Optional[str] = Field(None, description="Data source ID to use for database connection")

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
    db_type: str = "mssql"  # mssql, postgresql, mysql, etc.
    server: str = ""
    database_name: str = ""
    connection_string_encrypted: str = ""  # AES encrypted connection string
    connection_string_decrypted: Optional[str] = None # Debug field, not persisted
    driver: str = "ODBC Driver 17 for SQL Server"
    auth_type: AuthType = "windows"
    username: Optional[str] = None
    trust_server_certificate: Optional[bool] = False
    python_connection_string_encrypted: Optional[str] = None
    python_connection_string_decrypted: Optional[str] = None

class TargetDBConfigV2(TargetDBConfig):
    """Extended version with unique identifier for multi-source support"""
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True  # Allow disabling without deleting
    last_synced: Optional[str] = None  # ISO timestamp of last sync
    object_count: int = 0  # Total indexed objects

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

class EnvApiKeyResponse(BaseModel):
    api_key: Optional[str] = None
    exists: bool

class EnvApiKeyUpdateRequest(BaseModel):
    api_key: str

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
    target_db: Optional[TargetDBConfig] = None  # Optional - connection info now from _data-source.md
    llm_config: LLMConfig
    embedding_config: EmbeddingConfig
    vector_config: VectorConfig
    app_meta: AppMeta

class AgentSettingsV2(BaseModel):
    """Multi-source configuration with backward compatibility"""
    data_sources: List[TargetDBConfigV2] = []  # Multiple data sources
    primary_source_id: Optional[str] = None  # Default source for queries
    llm_config: LLMConfig
    embedding_config: EmbeddingConfig
    vector_config: VectorConfig
    app_meta: AppMeta
    
    @property
    def target_db(self) -> Optional[TargetDBConfigV2]:
        """Returns primary source for legacy code compatibility"""
        if self.primary_source_id:
            return next((s for s in self.data_sources if s.source_id == self.primary_source_id), None)
        return self.data_sources[0] if self.data_sources else None

class ConnectionTestRequest(BaseModel):
    driver: str = "ODBC Driver 17 for SQL Server"
    server: str
    database: str
    auth_type: AuthType = "windows"
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


# --- Skills-Based Data Discovery Models ---

class DataSource(BaseModel):
    """Parsed from _data-source.md"""
    source_id: Optional[str] = None
    name: str
    type: str  # "SQL Server", "Excel", "JSON API", etc.
    description: str
    keywords: List[str] = []
    status: str = "Active"  # "Active", "Archive", "Deprecated"
    connection_info: Optional[Dict[str, Any]] = None
    data_groups: List[str] = []  # Paths to group files
    file_path: Optional[str] = None  # Path to the _data-source.md file

class DataGroup(BaseModel):
    """Parsed from _data-group.md"""
    name: str
    data_source: str
    description: str
    keywords: List[str] = []
    tables: List[str] = []  # Paths to table .md files
    schema_notes: Optional[str] = None
    category: Optional[str] = None
    file_path: Optional[str] = None  # Path to the _data-group.md file

class RankedTable(BaseModel):
    """Discovery result with scoring"""
    schema_name: str
    table_name: str
    score: int = 0
    matched_by: List[str] = []  # ["skills", "value_index", "knowledge_base"]
    data_source: Optional[str] = None
    data_group: Optional[str] = None
    file_path: Optional[str] = None  # Path to table .md file

class ThresholdDecision(BaseModel):
    """Smart threshold analysis result"""
    auto_proceed: bool
    total_tables: int
    cross_schema: bool = False
    cross_database: bool = False
    trigger_reason: Optional[str] = None

class SelectionPrompt(BaseModel):
    """User selection UI data"""
    recommended: List[RankedTable] = []  # LLM confidence > 80%
    ambiguous_groups: List[Dict[str, Any]] = []  # Requires user choice
    additional_options: List[Dict[str, Any]] = []  # Extra possibilities

class SkillsDiscoveryResult(BaseModel):
    """Result from skills navigation"""
    matched_groups: List[DataGroup] = []
    candidate_tables: List[RankedTable] = []
    keywords_used: List[str] = []

class ThreeProngedResult(BaseModel):
    """Combined result from three-pronged discovery"""
    skills_tables: List[RankedTable] = []
    value_tables: List[RankedTable] = []
    knowledge_base_tables: List[RankedTable] = []
    merged_candidates: List[RankedTable] = []
    # New fields for enhanced discovery flow
    exact_match_found: bool = False
    exact_match_query: Optional[Dict[str, Any]] = None  # Contains: question, sql, tables, score
    requires_user_selection: bool = False
    selection_candidates: List[RankedTable] = []  # Top N candidates for user to choose from

class KBAssessment(BaseModel):
    """Result of LLM evaluation of knowledge base examples against user query"""
    is_sufficient: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    adjustments_needed: List[str] = []  # e.g., ["Change date filter to 2024", "Add GROUP BY region"]
    missing_entities: List[str] = []  # Entities/dimensions not covered by the KB example
    missing_tables: List[str] = []  # Tables needed but not in the KB SQL
    suggested_search_terms: List[str] = []  # Terms to search schema/value index for gap-filling
    original_sql: str = ""  # The SQL from the knowledge base example
    original_question: str = ""  # The question from the knowledge base example

class EnhanceSchemaRequest(BaseModel):
    """Request to enhance schema descriptions with AI"""
    file_path: str
    current_content: str
    user_context: Optional[str] = None

class EnhanceSchemaResponse(BaseModel):
    """Response with enhanced markdown content"""
    enhanced_markdown: str


# --- Multi-Source Schema Tree Models ---

class AddDataSourceRequest(BaseModel):
    """Request to add a new data source"""
    friendly_name: str
    description: str = ""
    keywords: List[str] = []
    server: str = ""
    database_name: str = ""
    db_type: str = "mssql"
    auth_type: AuthType = "windows"
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string_encrypted: Optional[str] = None
    driver: str = "ODBC Driver 17 for SQL Server"
    trust_server_certificate: bool = False
    skip_auto_scan: bool = False

class ScanDataSourceRequest(BaseModel):
    """Optional request body for scan endpoint to provide connection info"""
    server: str = ""
    database_name: str = ""
    auth_type: AuthType = "windows"
    driver: str = "ODBC Driver 17 for SQL Server"
    username: Optional[str] = None
    password: Optional[str] = None
    trust_server_certificate: bool = True

class DataSourceResponse(BaseModel):
    """Response for data source information"""
    source_id: str
    friendly_name: str
    description: str
    keywords: List[str] = []
    server: str
    database_name: str
    db_type: str = "mssql"
    enabled: bool
    is_primary: bool
    object_count: int
    last_synced: Optional[str] = None

class DataSourceListResponse(BaseModel):
    """Response listing all data sources"""
    data_sources: List[DataSourceResponse]
    primary_source_id: Optional[str] = None
    total_objects: int = 0


class ResolveDataSourceResponse(BaseModel):
    """Response schema for data source resolution."""
    source_id: str = Field(..., description="Resolved data source GUID")
    name: str = Field(..., description="Friendly name of the data source")
    type: str = Field(..., description="Data source type: SQL Server, Excel, etc.")
    server: Optional[str] = Field(None, description="Server name (for SQL Server)")
    database: Optional[str] = Field(None, description="Database name (for SQL Server)")
    file_path: Optional[str] = Field(None, description="File path (for Excel)")
    status: str = Field(default="active", description="Data source status")
    object_count: int = Field(default=0, description="Number of indexed objects")


class SchemaTreeNode(BaseModel):
    """Hierarchical tree node for schema browser"""
    node_id: str  # Format: "source_id" or "source_id:schema" or "source_id:schema:object"
    name: str
    type: Literal["source", "schema", "table", "view", "stored_procedure", "function"]
    parent_id: Optional[str] = None
    children: List['SchemaTreeNode'] = []
    metadata: Dict[str, Any] = {}  # Description, row counts, etc.
    is_indexed: bool = False

class SchemaTreeResponse(BaseModel):
    """Full tree structure response"""
    roots: List[SchemaTreeNode]
    total_sources: int
    total_objects: int

class AddObjectRequest(BaseModel):
    """Request to add object to vector index"""
    source_id: str
    schema_name: str
    object_name: str
    object_type: ObjectType
    description: Optional[str] = None

class SyncObjectRequest(BaseModel):
    """Request to sync object from database"""
    source_id: str
    schema_name: str
    object_name: str
    object_type: ObjectType

class DiscoverObjectsRequest(BaseModel):
    """Request to discover objects from database"""
    source_id: str
    schema_name: Optional[str] = None  # If None, discover from all schemas
    object_types: List[ObjectType] = [ObjectType.TABLE, ObjectType.VIEW]

class DiscoverObjectsResponse(BaseModel):
    """Response with discovered objects"""
    discovered: List[DataObject]
    total_count: int
    by_type: Dict[str, int] = {}  # Count by object type
