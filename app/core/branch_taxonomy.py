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
    REFINEMENT_PREFIX = "refinement/"
    DRILL_DOWN_PREFIX = "drill_down/"

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
    REFINE = "Refine"
    GENERATE = "Generate"
    CONVERSATIONAL = "Conversational"


class GenerationMode(str, Enum):
    """Scenario carried through the pipeline (see docs/AGENT_PROCESS.md §3)."""

    FRESH_START = "fresh_start"
    OPTIMIZATION = "optimization"
    REFINEMENT = "refinement"
    DRILL_DOWN = "drill_down"
    DEBUGGING = "debugging"


# Scenarios that keep prior domain context and are allowed to expand scope (Phase 3.2).
REFINEMENT_SCENARIOS = (GenerationMode.REFINEMENT, GenerationMode.DRILL_DOWN)


def is_refinement_scenario(mode: "GenerationMode | str | None") -> bool:
    if mode is None:
        return False
    value = mode.value if isinstance(mode, GenerationMode) else str(mode)
    return value in {m.value for m in REFINEMENT_SCENARIOS}


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


def scenario_branch(base_branch: str, mode) -> str:
    """Prefix a discovery branch with the active scenario so analytics can separate them."""
    if mode == GenerationMode.REFINEMENT or (isinstance(mode, str) and mode == GenerationMode.REFINEMENT.value):
        return f"{DiscoveryBranch.REFINEMENT_PREFIX}{base_branch}"
    if mode == GenerationMode.DRILL_DOWN or (isinstance(mode, str) and mode == GenerationMode.DRILL_DOWN.value):
        return f"{DiscoveryBranch.DRILL_DOWN_PREFIX}{base_branch}"
    return base_branch
