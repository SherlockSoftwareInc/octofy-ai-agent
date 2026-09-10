"""Discovery branch labels preserved for tests and analytics."""

from enum import Enum


class DiscoveryBranch:
    KB_EXACT = "kb_exact"
    PRECOMPUTED_EXACT = "precomputed_exact"
    PRECOMPUTED_RELATED_PREFIX = "precomputed_related/"
    TABLE_OVERRIDE = "table_override"
    KB_DIRECT = "kb_direct"
    KB_GAP_FILL = "kb_gap_fill"
    DUAL_PRONG = "dual_prong"
    GROUP_ANCHORED = "group_anchored"
    NO_DISCOVERY = "no_discovery"
    PRIORITY_VALIDATION_FAILED = "priority_validation_failed"
    APP_FEATURE = "app_feature"
    OFF_TOPIC = "off_topic"
    SYSTEM_CATALOG = "system_catalog"  # product-only; kept on HTTP wrapper

    ALL = (
        KB_EXACT,
        PRECOMPUTED_EXACT,
        TABLE_OVERRIDE,
        KB_DIRECT,
        KB_GAP_FILL,
        DUAL_PRONG,
        GROUP_ANCHORED,
        NO_DISCOVERY,
        PRIORITY_VALIDATION_FAILED,
        APP_FEATURE,
        OFF_TOPIC,
    )


class RouteKind(str, Enum):
    CODE_FIXING = "CodeFixing"
    OPTIMIZE = "Optimize"
    GENERATE = "Generate"
    CONVERSATIONAL = "Conversational"


class GenerationMode(str, Enum):
    FRESH_START = "fresh_start"
    OPTIMIZATION = "optimization"
    DEBUGGING = "debugging"


class PipelineStage:
    ROUTING = "routing"
    VALIDATE_PINS = "validate_pins"
    PREANALYSIS = "preanalysis"
    DISCOVERY = "discovery"
    ATTEMPT = "attempt"
    CRITIC = "critic"
    DB_VALIDATION = "db_validation"
    RECOVERY = "recovery"


def precomputed_related(base_branch: str) -> str:
    return f"{DiscoveryBranch.PRECOMPUTED_RELATED_PREFIX}{base_branch}"
