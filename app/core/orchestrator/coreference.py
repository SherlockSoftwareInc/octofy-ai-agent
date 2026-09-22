"""Conversational query rewriting (coreference resolution) — Phase 1.2.

A vague follow-up such as ``I need all order details`` is meaningless on its own: the
semantic analyzer cannot tell which products, categories or date range the user is still
talking about, so the pipeline happily scans ``[dbo].[Order Details]`` unbounded.

Before intent classification and metadata retrieval, the raw turn is therefore rewritten
against the last 1-3 conversation turns plus the active filter state:

    "I need all order details"  ->  "I need all order details for chocolate products"

The rewrite is deliberately conservative: it only fires for short/underspecified turns,
it is validated (length, non-empty, actually different), and it always has a deterministic
fallback that folds the *session's own* active filters back into the sentence — so filter
preservation does not depend on an LLM being reachable.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

from app.models.pipeline import ActiveFilter, ConversationContextResult, ConversationTurn
from app.utils.regexes import extract_qualified_object_names
from app.utils.sanitization import prepare_user_query_for_llm, sanitize_conversation_history

MAX_REWRITE_CHARS = 400
MAX_TURNS_FOR_REWRITE = 3
VAGUE_QUERY_MAX_WORDS = 8

VAGUE_FOLLOWUP_PATTERNS: List[str] = [
    r"^\s*(all|the|show|give|list|get)\b[^.]{0,30}\bdetails?\b",
    r"\b(all|full|complete|entire)\s+(the\s+)?(\w+\s+){0,2}details?\b",
    r"\b(need|want|show|give|list|get|see)\b[^.]{0,30}\bdetails?\b",
    r"\bmore\s+detail(s)?\b",
    r"\b(and|then)\s+(the\s+)?(details?|rest|others?|same)\b",
    r"\bwhat\s+about\b",
    r"\bhow\s+about\b",
    r"\bbreak\s*(this|it|that)\s*down\b",
    r"\bdrill\s*(down|into)\b",
    r"\bline\s+items?\b",
    r"\bexpand\b",
    r"\bgo\s+deeper\b",
    r"^\s*(and|also|plus|now)\b",
    r"^\s*(it|this|that|those|these|them)\b",
]

_VAGUE_COMPILED = [re.compile(p, re.IGNORECASE) for p in VAGUE_FOLLOWUP_PATTERNS]

# A short turn only needs coreference when it actually leans on earlier context.
_ANAPHORIC = re.compile(
    r"\b(it|its|this|that|these|those|them|they|their|same|again|more|also|too|instead|"
    r"previous|earlier|above)\b",
    re.IGNORECASE,
)

# SQL-shaped input never needs an LLM rewrite round-trip.
_SQL_SHAPED = re.compile(r"\b(select|from|where|join|group\s+by|order\s+by)\b", re.IGNORECASE)

COREFERENCE_SYSTEM_PROMPT = (
    "You rewrite a short follow-up message into a standalone database question by resolving "
    "pronouns and elided context from the conversation so far and the active filters.\n"
    "Rules:\n"
    "1. Keep the user's language and intent. Never invent subjects, metrics or filters that are "
    "not present in the conversation or the active filters.\n"
    "2. Keep every active filter unless the user explicitly removes, replaces or negates it.\n"
    "3. Return JSON only: {\"rewritten_query\": string, \"carried_filters\": "
    "[{\"entity\": string, \"attribute\": string, \"operator\": string, \"value\": string}], "
    "\"changed\": boolean}.\n"
    "4. If the message is already self-contained, return it unchanged with \"changed\": false."
)


def is_vague_followup(query: str) -> bool:
    text = (query or "").strip()
    if not text:
        return False
    if len(text.split()) > VAGUE_QUERY_MAX_WORDS:
        return False
    return any(p.search(text) for p in _VAGUE_COMPILED)


def needs_coreference(query: str, active_filters: Sequence[ActiveFilter], has_history: bool) -> bool:
    text = (query or "").strip()
    if not text:
        return False
    if _SQL_SHAPED.search(text):
        return False
    if extract_qualified_object_names(text, 1):
        return False
    if is_vague_followup(text):
        return True
    # Short, anaphoric turn while the session already has context.
    if len(text.split()) <= VAGUE_QUERY_MAX_WORDS and _ANAPHORIC.search(text) and (active_filters or has_history):
        lowered = text.lower()
        for f in active_filters:
            token = f.value_token()
            if token and token in lowered:
                return False
        return True
    return False


def resolve_coreference(
    raw_query: str,
    conversation_history: Optional[Sequence[ConversationTurn]] = None,
    active_filters: Optional[Sequence[ActiveFilter]] = None,
    llm=None,
    turn_index: int = 1,
) -> ConversationContextResult:
    """Rewrite ``raw_query`` into a self-contained question, carrying session filters."""
    query = (raw_query or "").strip()
    history = list(conversation_history or [])
    filters = list(active_filters or [])
    result = ConversationContextResult(
        original_query=query,
        rewritten_query=query,
        active_filters=list(filters),
        carried_filters=[],
    )
    if not query or not needs_coreference(query, filters, bool(history)):
        return result

    if llm is not None:
        llm_result = _llm_rewrite(query, history, filters, llm, turn_index)
        if llm_result is not None:
            return llm_result

    return _deterministic_rewrite(query, filters, result)


def _llm_rewrite(
    query: str,
    history: Sequence[ConversationTurn],
    filters: Sequence[ActiveFilter],
    llm,
    turn_index: int,
) -> Optional[ConversationContextResult]:
    safe_query = prepare_user_query_for_llm(query)
    recent = history[-MAX_TURNS_FOR_REWRITE:]
    history_lines = []
    for turn in recent:
        question = (turn.question or "").strip()
        answer = (turn.answer or "").strip().replace("\n", " ")[:200]
        if question:
            history_lines.append(f"- Q: {question}")
        if answer:
            history_lines.append(f"  A: {answer}")
    history_text = sanitize_conversation_history(history_lines, max_messages=6) if history_lines else "(none)"
    filter_text = (
        "\n".join(f"- {f.entity + '.' if f.entity else ''}{f.attribute} {f.operator} {f.value}" for f in filters)
        if filters
        else "(none)"
    )
    user = (
        f"CONVERSATION SO FAR (oldest first):\n{history_text}\n\n"
        f"ACTIVE FILTERS (carry forward unless explicitly removed):\n{filter_text}\n\n"
        f"CURRENT TURN (turn {turn_index}):\n{safe_query}"
    )
    try:
        data = llm.complete_json(
            [
                {"role": "system", "content": COREFERENCE_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            max_tokens=256,
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    rewritten = str(data.get("rewritten_query") or "").strip()
    if not _valid_rewrite(query, rewritten):
        return None

    carried = _parse_carried_filters(data.get("carried_filters"), turn_index)
    merged = merge_filters(filters, carried)
    changed = bool(data.get("changed")) or rewritten != query
    return ConversationContextResult(
        original_query=query,
        rewritten_query=rewritten,
        was_rewritten=changed,
        carried_filters=carried,
        active_filters=merged,
        notes=[f"Coreference rewrite: \"{query}\" -> \"{rewritten}\""],
        source="llm",
    )


def _valid_rewrite(original: str, rewritten: str) -> bool:
    if not rewritten or rewritten == original:
        return False
    if len(rewritten) > MAX_REWRITE_CHARS:
        return False
    # A rewrite must not mangle the turn into something much shorter than the original.
    if len(rewritten) < max(8, int(len(original) * 0.5)):
        return False
    return True


def _parse_carried_filters(raw, turn_index: int) -> List[ActiveFilter]:
    if not isinstance(raw, list):
        return []
    carried: List[ActiveFilter] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        attribute = str(item.get("attribute") or "").strip()
        value = str(item.get("value") or "").strip()
        if not attribute or not value:
            continue
        carried.append(
            ActiveFilter(
                entity=str(item.get("entity") or "").strip(),
                attribute=attribute,
                operator=str(item.get("operator") or "=").strip() or "=",
                value=value,
                origin_turn=int(item.get("origin_turn") or turn_index),
                source="llm",
            )
        )
    return carried


def _deterministic_rewrite(
    query: str,
    filters: Sequence[ActiveFilter],
    result: ConversationContextResult,
) -> ConversationContextResult:
    """Fold the session's active filters back into the sentence without an LLM."""
    phrases: List[str] = []
    seen = set()
    lowered_query = query.lower()
    for f in filters:
        phrase = f.phrase()
        key = phrase.lower()
        if not phrase or key in seen:
            continue
        if key and key in lowered_query:
            continue
        token = f.value_token()
        if token and token in lowered_query:
            # The user already restated this filter (e.g. "now do this for coffee").
            continue
        seen.add(key)
        phrases.append(phrase)
    if not phrases:
        return result
    base = query.rstrip()
    if base.endswith((".", "?", "!")):
        base = base[:-1]
    rewritten = f"{base} for {' and '.join(phrases)}"
    if len(rewritten) > MAX_REWRITE_CHARS:
        return result
    result.rewritten_query = rewritten
    result.was_rewritten = True
    result.notes.append(f"Deterministic filter carry-forward: \"{query}\" -> \"{rewritten}\"")
    return result


def merge_filters(
    inherited: Sequence[ActiveFilter],
    discovered: Sequence[ActiveFilter],
) -> List[ActiveFilter]:
    """Merge two filter lists; later entries win on (entity, attribute)."""
    merged: List[ActiveFilter] = []
    for f in list(inherited) + list(discovered):
        key = (f.entity or "").lower(), (f.attribute or "").lower()
        replaced = False
        for idx, existing in enumerate(merged):
            if ((existing.entity or "").lower(), (existing.attribute or "").lower()) == key:
                merged[idx] = f
                replaced = True
                break
        if not replaced:
            merged.append(f)
    return merged
