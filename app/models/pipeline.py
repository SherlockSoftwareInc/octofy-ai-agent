"""Internal pipeline models for the built-in SQL generator port."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.branch_taxonomy import GenerationMode, RouteKind


class ConversationTurn(BaseModel):
    question: str
    answer: Optional[str] = None
    failed: bool = False
    canceled: bool = False


class AgentRequest(BaseModel):
    query: str
    existing_code: Optional[str] = None
    error_message: Optional[str] = None
    database_objects: List[str] = Field(default_factory=list)
    top_k: int = 8
    conversation_history: List[ConversationTurn] = Field(default_factory=list)
    is_user_code: bool = False
    source_id: Optional[str] = None
    table_override: List[str] = Field(default_factory=list)
    semantic_mode: Optional[bool] = None
    force_general: bool = False


class SchemaMetadata(BaseModel):
    hydrated_objects: List[str] = Field(default_factory=list)
    resolved_object_names: List[str] = Field(default_factory=list)
    resolution_notes: List[str] = Field(default_factory=list)


class AgentContext(BaseModel):
    request: AgentRequest
    schema_metadata: SchemaMetadata = Field(default_factory=SchemaMetadata)
    intent: Optional[str] = None
    generation_mode: GenerationMode = GenerationMode.FRESH_START
    is_error_recovery: bool = False
    combined_query: str = ""
    dbms_type: str = "SQL Server"


class BuiltInAttemptReport(BaseModel):
    attempt_number: int
    stage: str
    what_was_tried: str
    why_it_failed: Optional[str] = None
    recovery_action: Optional[str] = None
    candidate_objects: List[str] = Field(default_factory=list)


class ScoredObject(BaseModel):
    schema_name: str
    object_name: str
    object_type: str = "Table"
    data_source: Optional[str] = None
    score: float = 0.0
    vector_score: Optional[float] = None
    matched_columns: List[str] = Field(default_factory=list)
    priority: bool = False
    required: bool = False
    description: Optional[str] = None
    markdown: Optional[str] = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.object_name}"

    def merge_key(self) -> str:
        stripped = self.object_name.split(" (Segment")[0].strip()
        ds = self.data_source or ""
        return f"{ds}|{self.schema_name}|{stripped}".lower()


class BuiltInFailureReport(BaseModel):
    summary: str = ""
    resolution_plan: List[str] = Field(default_factory=list)
    attempts: List[BuiltInAttemptReport] = Field(default_factory=list)
    final_resolution_guidance: str = ""
    candidate_objects: List[ScoredObject] = Field(default_factory=list)


class BuiltInGenerateResult(BaseModel):
    success: bool
    sql: str = ""
    message: Optional[str] = None
    discovery_branch: Optional[str] = None
    attempts: int = 0
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    processing_time_ms: int = 0
    hallucination_count: int = 0
    agentic_retry_count: int = 0
    canonical_question: Optional[str] = None
    context_text: Optional[str] = None
    failure_report: Optional[BuiltInFailureReport] = None
    error_category: Optional[str] = None
    candidates: List[ScoredObject] = Field(default_factory=list)
    source_id: Optional[str] = None
    explanation: Optional[str] = None
    query_type: str = "database"


class RouteDecision(BaseModel):
    route: RouteKind
    context: AgentContext
    immediate_result: Optional[BuiltInGenerateResult] = None
    skip_discovery: bool = False
    skip_preanalysis: bool = False


class QueryAnalysis(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    complexity: str = "simple"  # simple | moderate | complex
    entities: List[str] = Field(default_factory=list)
    date_ranges: List[str] = Field(default_factory=list)
    filter_values: List[str] = Field(default_factory=list)
    extracted_columns: List[str] = Field(default_factory=list)
    resolved_tool_results: List[str] = Field(default_factory=list)


class ActiveDataGroupContext(BaseModel):
    top_groups: List[Dict[str, Any]] = Field(default_factory=list)
    member_groups: Dict[str, List[str]] = Field(default_factory=dict)
    summary: str = ""


class FewShotExample(BaseModel):
    question: str
    sql: str
    score: float = 0.0
    is_exact_match: bool = False
    smq_query: str = ""
    source: str = "few_shot"  # few_shot | precomputed


class DiscoveryResult(BaseModel):
    objects: List[ScoredObject] = Field(default_factory=list)
    branch: str
    few_shot_examples: List[FewShotExample] = Field(default_factory=list)
    value_mappings: List[Dict[str, Any]] = Field(default_factory=list)
    allowed_schemas: List[str] = Field(default_factory=list)
    active_groups: ActiveDataGroupContext = Field(default_factory=ActiveDataGroupContext)
    query_analysis: QueryAnalysis = Field(default_factory=QueryAnalysis)
    selected_object_context: str = ""
    supplementary_objects: str = ""
    schema_context: str = ""
    schema_context_for_validation: str = ""


class CombinedValidationResult(BaseModel):
    requirements_satisfied: bool = True
    schema_valid: bool = True
    feedback: str = ""
    mismatches: List[str] = Field(default_factory=list)
    status: Optional[str] = None
    missing_group_members: List[str] = Field(default_factory=list)
    canonical_question: Optional[str] = None
    missing_objects: List[str] = Field(default_factory=list)


class SemanticMeasure(BaseModel):
    name: str
    expression: str
    description: str = ""


class SemanticDimension(BaseModel):
    name: str
    column: str
    table: str
    description: str = ""


class SemanticJoin(BaseModel):
    from_table: str
    to_table: str
    join_expression: str
    join_type: str = "INNER"


class SemanticModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    data_source_key: Optional[str] = None
    label: str
    is_active: bool = True
    measures: List[SemanticMeasure] = Field(default_factory=list)
    dimensions: List[SemanticDimension] = Field(default_factory=list)
    joins: List[SemanticJoin] = Field(default_factory=list)
    governance_predicates: List[str] = Field(default_factory=list)


class SmqPayload(BaseModel):
    metrics: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    timeframes: List[Dict[str, Any]] = Field(default_factory=list)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens

    def as_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }
