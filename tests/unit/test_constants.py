from app.core import constants


def test_frozen_constants():
    assert constants.MaxRetries == 5
    assert constants.KbExactMatchThreshold == 0.05
    assert constants.KbConfidenceThreshold == 0.70
    assert constants.KbScoreThreshold == 0.35
    assert constants.DefaultObjectSearchVectorScoreThreshold == 0.50
    assert constants.DefaultPrecomputedQueryDirectMatchThreshold == 0.93
    assert constants.DefaultPrecomputedQueryFewShotThreshold == 0.82
    assert constants.PrecomputedQueryTopK == 3
    assert constants.RrfK == 60.0
    assert constants.RRF_WEIGHT_DATA_GROUP == 2.0
    assert constants.RRF_WEIGHT_BM25_DEFAULT == 0.5
    assert constants.MaxRerankTables == 8
    assert constants.SchemaContextTokenBudget == 6400
    assert constants.PromptContextDiscoveryCap == 8
    assert constants.MissingObjectBreakThreshold == 2
    assert constants.MissingGroupMemberValidationStatus == "MISSING_GROUP_MEMBER"
    assert constants.FuzzyMatchMinConfidence == 0.85
    assert constants.MaxGenerationTimeMs == 120_000
    assert constants.NoDiscoveryTimeBudgetMs == 90_000
    assert constants.SemanticCompilationTimeoutMs == 5_000
    assert constants.EmbeddingDimensions == 1536
    assert constants.PresencePenaltyAfterLoop == 0.4
    assert constants.HallucinationExitThreshold == 2
