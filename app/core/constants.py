"""Built-in SQL generator constants. Values must match the C# engine; do not retune."""

from typing import Optional

# Retry / time budgets
MaxRetries = 5
MaxGenerationTimeMs = 120_000
NoDiscoveryTimeBudgetMs = 90_000
SemanticCompilationTimeoutMs = 5_000

# Knowledge-base thresholds (cosine distance unless noted)
KbExactMatchThreshold = 0.05
KbConfidenceThreshold = 0.70
KbScoreThreshold = 0.35

# Vector / precomputed
DefaultObjectSearchVectorScoreThreshold = 0.50
DefaultPrecomputedQueryDirectMatchThreshold = 0.93
DefaultPrecomputedQueryFewShotThreshold = 0.82
PrecomputedQueryTopK = 3

# Reciprocal Rank Fusion
RrfK = 60.0
RRF_WEIGHT_VALUE_INDEX = 1.0
RRF_WEIGHT_FEW_SHOT = 1.0
RRF_WEIGHT_SCHEMA_VECTOR = 1.0
RRF_WEIGHT_DATA_GROUP = 2.0
RRF_WEIGHT_BM25_DEFAULT = 0.5
MaxRerankTables = 8

# Discovery / hydration
ActiveDataGroupTopN = 3
SchemaContextTokenBudget = 6_400
PromptContextDiscoveryCap = 8
MissingObjectBreakThreshold = 2
MissingGroupMemberValidationStatus = "MISSING_GROUP_MEMBER"
FuzzyMatchMinConfidence = 0.85
MaxRecoveryExpansion = 5
MaxAutoExtractedObjects = 5
CatalogCacheTtlSeconds = 300
MaxDiscoveryCacheEntries = 256
MaxQueryAnalysisCacheEntries = 100
RelativeColumnScoreThreshold = 0.85
ColumnDetailValueSeedScore = 0.80
KeywordMatchScore = 1.0
ApplyColumnBoost = 0.15
ApplyColumnBoostCap = 1.0
SemanticModelDiscoveryTopK = 3

# Hallucination / recovery
HallucinationExitThreshold = 2
HallucinationExitThresholdWithBreaker = 1
PresencePenaltyAfterLoop = 0.4

# Semantic layer
SemanticSmqParseRetryOnFailure = True
SemanticCompilationFallbackToRawSql = True

# Embedding cache
EmbeddingCacheL1Size = 512
EmbeddingCacheL2Size = 10_000
EmbeddingCacheL2EvictBatch = 1_000
EmbeddingDimensions = 1536

# Conversation folding
OlderAnswerTruncateChars = 200
CanonicalQuestionMaxWords = 25

# Simple fast-path heuristics
SimplePreAnalysisMaxCollapsedChars = 180
SimplePreAnalysisMaxWords = 40
LikelyDbQueryMaxWords = 50

VECTOR_SCHEMA_VERSION = "1.0.0"


def effective_object_search_threshold(override: Optional[float] = None) -> float:
    if override is None:
        from app.core.config import settings
        return settings.object_search_vector_score_threshold()
    return max(0.0, min(1.0, float(override)))


def precomputed_direct_match_threshold() -> float:
    from app.core.config import settings
    return float(settings.PRECOMPUTED_QUERY_DIRECT_MATCH_THRESHOLD)


def precomputed_few_shot_threshold() -> float:
    from app.core.config import settings
    return float(settings.PRECOMPUTED_QUERY_FEW_SHOT_THRESHOLD)


def semantic_compilation_fallback_to_raw_sql() -> bool:
    from app.core.config import settings
    return bool(settings.SEMANTIC_COMPILATION_FALLBACK_TO_RAW_SQL)
