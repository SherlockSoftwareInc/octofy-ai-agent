"""Multi-scenario routing: fresh_start / optimization / refinement / drill_down.

The historical router treated *any* SQL in the editor as ``optimization``. That binary
check is what let refinement turns (``I need all order details``) silently degrade into a
schema-free rewrite of the editor SQL — dropping the established filters and refusing to
add the base tables the new grain needs.

This module keeps optimization **narrow and safe** (semantics-, filter-, entity- and
grain-preserving edits) and moves every request that changes the output grain, adds or
removes attributes, or replaces an established filter value into ``refinement`` /
``drill_down``, which keeps discovery enabled.

Ordering matters: explicit reset > drill-down > refinement > optimization > default.
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.core.branch_taxonomy import GenerationMode
from app.models.pipeline import ScenarioDecision

# --- Scenario signal patterns (checked in this order) -----------------------

RESET_PATTERNS: List[str] = [
    r"\bstart\s+over\b",
    r"\bstart\s+from\s+scratch\b",
    r"\bnew\s+query\b",
    r"\bbrand\s+new\s+query\b",
    r"\breset\s+(the\s+)?(query|context)\b",
    r"\bforget\s+(the\s+)?(previous|prior|earlier|last)\b",
    r"\bignore\s+(the\s+)?(previous|prior|earlier|last)\b",
    r"\bscratch\s+that\b",
    r"\bnever\s+mind\b",
    r"\bcompletely\s+different\b",
]

# Explicit filter negation (Phase 2.2): the *filters* go away, the query structure stays.
FILTER_CLEAR_PATTERNS: List[str] = [
    r"\bclear\s+(all\s+)?filters?\b",
    r"\breset\s+(the\s+)?filters?\b",
    r"\b(remove|drop|delete)\s+(the\s+|all\s+)?filters?\b",
    r"\b(no|without\s+any|remove\s+all)\s+filters?\b",
    r"\bignore\s+(the\s+)?filters?\b",
    r"\bunfiltered\b",
    r"\bfor\s+(all|every)\b",
]

DRILL_DOWN_PATTERNS: List[str] = [
    r"\bdrill\s*(down|into|through)\b",
    r"\bbreak\s*(this|it|that|them)?\s*down\b",
    r"\bbreakdown\s+by\b",
    r"\bbreak\s+it\s+out\b",
    r"\bgroup(ed)?\s+by\s+\w+",
    r"\bsplit\s+(this|it|them)?\s*(out\s+)?by\b",
    r"\bsegment(ed)?\s+by\b",
    r"\bcategoriz(e|ed)\s+by\b",
    r"\bfor\s+each\s+\w+",
    r"\bper\s+(customer|product|category|region|country|employee|order|month|quarter|year|day|week|supplier|shipper|territory|store)\b",
    r"\bshow\s+(me\s+)?(the\s+)?\w+\s+by\s+\w+",
    r"\bsummar(y|ize|ise)\s+(this|it)\s+by\b",
]

# Refinement: output grain / attribute set / scope changes that keep prior context.
REFINEMENT_PATTERNS: List[str] = [
    r"\ball\s+(the\s+)?(order\s+)?details?\b",
    r"\b(full|complete|entire)\s+(order\s+)?details?\b",
    r"\bline\s+items?\b",
    r"\btransaction[\s-]level\b",
    r"\b(detail|row)[\s-]level\b",
    r"\bexpand\s+(this|it|the\s+query)\b",
    r"\bgo\s+deeper\b",
    r"\bmore\s+detail(s)?\b",
    r"\b(add|include|append|bring\s+in|pull\s+in|also\s+show|show\s+also|as\s+well\s+as)\b",
    r"\b(exclude|drop|remove)\s+(the\s+)?\w*\s*(date|name|amount|quantity|column|field|attribute|dimension)\b",
    r"\bchange\s+the\s+grain\b",
    r"\bnow\s+(do|show|run)\s+(this|it)\s+for\b",
    r"\binstead\s+(use|do|show|for)\b",
    r"\b(show|give|do|run|use|switch|try)\b[^.]{0,25}\binstead\b",
    r"\b(change|switch)\s+(it|this|that)?\s*(to|into)\b",
    r"\b(same|again)\s+(but\s+)?by\s+\w+",
    r"\bswitch\s+(it\s+)?to\s+\w+\s+instead\b",
    r"\bwhat\s+about\s+\w+",
    r"\bhow\s+about\s+\w+",
]

# Optimization: semantics-, filter-, entity- and grain-preserving edits.
OPTIMIZATION_PATTERNS: List[str] = [
    r"\bmake\s+(it|this)\s+(faster|quicker|more\s+efficient|perform)\b",
    r"\b(optimi[sz]e|tune|speed\s+up|improve)\b.*\b(performance|query|it|this|sql)\b",
    r"\bperformance\b",
    r"\bmore\s+efficient\b",
    r"\bsargable\b",
    r"\b(execution|query)\s+plan\b",
    r"\badd\s+(an?\s+)?(index|indexes|indices|indexing|hint|optimizer\s+hint)\b",
    r"\b(create|add)\s+(an?\s+)?nonclustered\s+index\b",
    r"\bformat(ted|ting)?\b",
    r"\bbeautify\b",
    r"\bpretty\s?print\b",
    r"\bindent(ation)?\b",
    r"\bclean\s+up\s+(the\s+)?(sql|query|code|formatting)\b",
    r"\brefactor\b",
    r"\brewrite\s+(this|it)\s+(for\s+)?(readability|clarity|style|performance)\b",
    r"\bconvert\s+(this|it|the\s+query)?\s*to\s+(a\s+)?(cte|common\s+table\s+expression|with\s+clause)\b",
    r"\buse\s+(a\s+)?cte\b",
    r"\bwrap\s+(this|it)\s+in\s+(a\s+)?cte\b",
    r"\b(remove|drop|delete)\s+(the\s+)?(unused|redundant|extra)\s+(joins?|columns?|ctes?|subquer(y|ies))\b",
    r"\b(remove|drop)\s+(the\s+)?(unused|redundant)\s+joins?\b",
    r"\bparameteri[sz]e\b",
    r"\badd\s+(some\s+)?comments?\b",
    r"\bcomment\s+(the\s+)?(sql|query|code)\b",
    r"\brenam(e|ing)\s+(the\s+)?alias(es)?\b",
    r"\badd\s+(an?\s+)?alias(es)?\b",
    r"\buppercase\b",
    r"\blowercase\b",
    r"\btrailing\s+semicolon\b",
    r"\bsyntax\b",
    r"\bdialect\b",
    r"\bfix\s+(the\s+)?formatting\b",
]

_COMPILED = {
    GenerationMode.FRESH_START.value: [re.compile(p, re.IGNORECASE) for p in RESET_PATTERNS],
    "filter_clear": [re.compile(p, re.IGNORECASE) for p in FILTER_CLEAR_PATTERNS],
    GenerationMode.DRILL_DOWN.value: [re.compile(p, re.IGNORECASE) for p in DRILL_DOWN_PATTERNS],
    GenerationMode.REFINEMENT.value: [re.compile(p, re.IGNORECASE) for p in REFINEMENT_PATTERNS],
    GenerationMode.OPTIMIZATION.value: [re.compile(p, re.IGNORECASE) for p in OPTIMIZATION_PATTERNS],
}

# Refinement/optimization conflicts resolved toward optimization when the added object is
# structural rather than a data attribute (e.g. "add an index").
_STRUCTURAL_ADDITION = re.compile(
    r"\b(add|include)\b[^.]{0,30}\b(index(es|ing)?|indices|hints?|alias(es)?|comments?|cte|"
    r"formatting|semicolon|parameters?)\b",
    re.IGNORECASE,
)

LLM_SCENARIO_LABELS = (
    GenerationMode.OPTIMIZATION.value,
    GenerationMode.REFINEMENT.value,
    GenerationMode.DRILL_DOWN.value,
    GenerationMode.FRESH_START.value,
)

SCENARIO_SYSTEM_PROMPT = (
    "You classify how a user wants to modify an existing SQL query. Reply with exactly one label.\n"
    "- optimization: the change preserves semantics, filters, entities and output grain "
    "(formatting, indexing, performance, converting to a CTE, removing unused joins, aliases, comments).\n"
    "- refinement: the change adds or removes output attributes or narrows/replaces an established "
    "filter value while keeping the prior domain context (e.g. 'add shipping date', 'now do this for coffee').\n"
    "- drill_down: the change moves to a deeper output grain or a new grouping dimension "
    "(e.g. 'break this down by customer', 'I need all order details', 'per order').\n"
    "- fresh_start: the user resets and wants a new query unrelated to the current SQL."
)


def _matches(patterns: List[re.Pattern], text: str) -> List[str]:
    hits: List[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            hit = match.group(0).strip()
            if hit and hit.lower() not in {h.lower() for h in hits}:
                hits.append(hit)
    return hits


def detect_reset(query: str) -> bool:
    """Explicit *full* reset language: drop the editor SQL and start clean."""
    return bool(_matches(_COMPILED[GenerationMode.FRESH_START.value], query or ""))


def detect_filter_clear(query: str) -> bool:
    """Explicit filter negation (Phase 2.2) — full reset or a bare filter clear."""
    text = query or ""
    return detect_reset(text) or bool(_matches(_COMPILED["filter_clear"], text))


def classify_scenario(
    query: str,
    has_existing_code: bool,
    error_message: Optional[str] = None,
    llm=None,
    allow_llm: bool = True,
) -> ScenarioDecision:
    """Classify the turn scenario. Deterministic first; LLM only for genuine ambiguity."""
    text = (query or "").strip()

    if error_message and has_existing_code:
        return ScenarioDecision(
            scenario=GenerationMode.DEBUGGING,
            confidence=1.0,
            signals=["error_message"],
            source="deterministic",
        )

    if not has_existing_code:
        # No editor SQL to preserve: every request is a fresh start for routing purposes.
        return ScenarioDecision(
            scenario=GenerationMode.FRESH_START,
            confidence=1.0,
            signals=["no_existing_code"],
            source="deterministic",
        )

    reset = _matches(_COMPILED[GenerationMode.FRESH_START.value], text)
    if reset:
        return ScenarioDecision(
            scenario=GenerationMode.FRESH_START,
            confidence=0.95,
            signals=reset,
            source="deterministic",
        )

    drill = _matches(_COMPILED[GenerationMode.DRILL_DOWN.value], text)
    if drill:
        return ScenarioDecision(
            scenario=GenerationMode.DRILL_DOWN,
            confidence=0.9,
            signals=drill,
            source="deterministic",
        )

    refine = _matches(_COMPILED[GenerationMode.REFINEMENT.value], text)
    if detect_filter_clear(text):
        # "for all products" / "clear filters" keeps the query but changes its scope.
        refine = refine + _matches(_COMPILED["filter_clear"], text)
    optimize = _matches(_COMPILED[GenerationMode.OPTIMIZATION.value], text)
    structural_add = _STRUCTURAL_ADDITION.search(text)

    if refine and not structural_add:
        return ScenarioDecision(
            scenario=GenerationMode.REFINEMENT,
            confidence=0.85 if optimize else 0.9,
            signals=refine + optimize,
            source="deterministic",
        )

    if structural_add:
        return ScenarioDecision(
            scenario=GenerationMode.OPTIMIZATION,
            confidence=0.85,
            signals=[structural_add.group(0).strip()] + optimize,
            source="deterministic",
        )

    if optimize:
        return ScenarioDecision(
            scenario=GenerationMode.OPTIMIZATION,
            confidence=0.9,
            signals=optimize,
            source="deterministic",
        )

    # No deterministic signal: preserve the historical default, but ask the LLM when the
    # turn is short enough to be genuinely ambiguous.
    if allow_llm and llm is not None and len(text.split()) <= 12:
        decided = _llm_scenario(text, llm)
        if decided is not None:
            return decided

    return ScenarioDecision(
        scenario=GenerationMode.OPTIMIZATION,
        confidence=0.5,
        signals=[],
        source="default",
    )


def _llm_scenario(query: str, llm) -> Optional[ScenarioDecision]:
    prompt = f"{SCENARIO_SYSTEM_PROMPT}\n\nEDITOR SQL: present\nUSER REQUEST: {query}\nLABEL:"
    try:
        text = llm.complete(
            [
                {"role": "system", "content": "You are a query-modification scenario classifier."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=16,
        )
    except Exception:
        return None
    label = (text or "").strip().lower().replace(" ", "_").strip("`.\n")
    for candidate in (GenerationMode.DRILL_DOWN.value, GenerationMode.REFINEMENT.value, GenerationMode.OPTIMIZATION.value, GenerationMode.FRESH_START.value):
        if candidate in label:
            return ScenarioDecision(
                scenario=GenerationMode(candidate),
                confidence=0.7,
                signals=[f"llm:{candidate}"],
                source="llm",
            )
    return None
