"""Session-level semantic context state and filter persistence (Phase 2).

Within one chat section the pipeline must remember *what the user is still filtering on*.
Otherwise every follow-up starts from zero: the optimizer path re-emits the editor SQL
unchanged, and a drill-down turn loses ``ProductName LIKE '%chocolate%'`` and scans the
whole fact table.

The state is intentionally small and explicit::

    {
      "session_id": "chat-section-id",
      "active_filters": [
        {"entity": "Products", "attribute": "ProductName", "operator": "LIKE",
         "value": "'%chocolate%'", "origin_turn": 1}
      ],
      "active_domains": ["Sales Analytics"],
      "target_grain": "summary_by_product"
    }

Lifecycle rules (Phase 2.2):

* **Inheritance** — filters carry forward unless explicitly negated, replaced or cleared.
* **Negation / clear** — "for all products", "clear filters", "start over" empties the state.
* **Replacement** — "now do this for coffee" rewrites the established value, keeping the
  attribute and the rest of the query structure.

The store is process-local, bounded (LRU) and thread-safe; it is keyed by the client's
session id namespaced by `source_id` when one is supplied. When no session id is available the
same rules still run against the filters parsed from the caller's own editor SQL, so filter
preservation never depends on the client opting in.
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

from app.core.branch_taxonomy import GenerationMode
from app.core.orchestrator.coreference import merge_filters, resolve_coreference
from app.core.orchestrator.preprocessing import fold_conversation
from app.core.orchestrator.scenario import classify_scenario, detect_filter_clear
from app.models.pipeline import (
    ActiveFilter,
    AgentContext,
    AgentRequest,
    ConversationContextResult,
    ConversationTurn,
    SessionSemanticContext,
)

MaxSessionContexts = 256
MaxActiveFilters = 12

_ALIAS_TABLE = re.compile(
    r"\b(?:from|join)\s+((?:\[[^\]]+\]|\w+)(?:\s*\.\s*(?:\[[^\]]+\]|\w+))?)\s*(?:as\s+)?(\w+)?",
    re.IGNORECASE,
)
_PREDICATE = re.compile(
    r"(?:(?P<qualifier>\w+)\s*\.\s*)?(?P<column>\[[^\]]+\]|\w+)\s*"
    r"(?P<operator><>|!=|>=|<=|=|<|>|(?<!not\s)like|not\s+like)\s*"
    r"(?P<value>N?'(?:[^']|'')*'|-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_VALUE_OPERATORS = {"=", "like", "<>", "!="}

_REPLACEMENT_PATTERNS = [
    re.compile(
        r"\b(?:now\s+)?(?:do|show|run|make|give)\s+(?:this|it|that)\s+for\s+(?P<value>[A-Za-z][\w\-]*)",
        re.IGNORECASE,
    ),
    re.compile(r"\binstead\s+(?:of\s+\w+\s+)?(?:use|do|show|for)\s+(?P<value>[A-Za-z][\w\-]*)", re.IGNORECASE),
    re.compile(r"\bswitch\s+(?:it\s+)?to\s+(?P<value>[A-Za-z][\w\-]*)", re.IGNORECASE),
    re.compile(r"\bchange\s+(?:it\s+)?to\s+(?P<value>[A-Za-z][\w\-]*)", re.IGNORECASE),
    re.compile(r"\bfor\s+(?P<value>[A-Za-z][\w\-]*)\s+instead\b", re.IGNORECASE),
]

_REPLACEMENT_STOPWORDS = {"all", "every", "the", "a", "an", "me", "them", "this", "that", "now", "instead"}


class SessionContextStore:
    """Thread-safe bounded store of per-session semantic state."""

    def __init__(self, max_entries: int = MaxSessionContexts):
        self._max = max_entries
        self._lock = threading.Lock()
        self._items: "OrderedDict[str, SessionSemanticContext]" = OrderedDict()

    def get(self, session_id: Optional[str]) -> Optional[SessionSemanticContext]:
        if not session_id:
            return None
        with self._lock:
            item = self._items.get(session_id)
            if item is None:
                return None
            self._items.move_to_end(session_id)
            return item.model_copy(deep=True)

    def put(self, context: SessionSemanticContext) -> None:
        if not context.session_id:
            return
        context.updated_at = time.time()
        with self._lock:
            self._items[context.session_id] = context.model_copy(deep=True)
            self._items.move_to_end(context.session_id)
            while len(self._items) > self._max:
                self._items.popitem(last=False)

    def clear(self, session_id: Optional[str] = None) -> None:
        with self._lock:
            if session_id:
                self._items.pop(session_id, None)
            else:
                self._items.clear()


_session_store = SessionContextStore()


def get_session_store() -> SessionContextStore:
    return _session_store


# --- Deterministic filter extraction ---------------------------------------


def _normalize_identifier(raw: str) -> str:
    return (raw or "").strip().strip("[]").strip()


def extract_filters_from_sql(sql: Optional[str], turn_index: int = 1) -> List[ActiveFilter]:
    """Parse simple literal predicates out of a SQL statement.

    Only predicates whose right-hand side is a literal are collected, so join conditions
    (``o.CustomerID = c.CustomerID``) and computed expressions are ignored.
    """
    text = (sql or "").strip()
    if not text:
        return []

    aliases: Dict[str, str] = {}
    tables: List[str] = []
    for match in _ALIAS_TABLE.finditer(text):
        table_ref = _normalize_identifier(match.group(1).split(".")[-1])
        if not table_ref:
            continue
        tables.append(table_ref)
        alias = _normalize_identifier(match.group(2) or "")
        if alias and alias.upper() not in {"ON", "WHERE", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "JOIN", "GROUP", "ORDER"}:
            aliases[alias.lower()] = table_ref
    single_table = tables[0] if len(tables) == 1 else ""

    filters: List[ActiveFilter] = []
    seen = set()
    for match in _PREDICATE.finditer(text):
        column = _normalize_identifier(match.group("column"))
        operator = re.sub(r"\s+", " ", match.group("operator").strip().upper())
        value = match.group("value").strip()
        qualifier = _normalize_identifier(match.group("qualifier") or "")
        if not column or not value:
            continue
        if column.lower() == "1" or value == "1":
            continue
        entity = aliases.get(qualifier.lower(), "") if qualifier else single_table
        if qualifier and not entity:
            entity = qualifier
        key = (entity.lower(), column.lower())
        if key in seen:
            continue
        seen.add(key)
        filters.append(
            ActiveFilter(
                entity=entity,
                attribute=column,
                operator=operator,
                value=value,
                origin_turn=turn_index,
                source="sql",
            )
        )
        if len(filters) >= MaxActiveFilters:
            break
    return filters


# --- Lifecycle rules --------------------------------------------------------


def _replacement_value(query: str) -> Optional[str]:
    for pattern in _REPLACEMENT_PATTERNS:
        match = pattern.search(query or "")
        if not match:
            continue
        value = (match.group("value") or "").strip()
        if value and value.lower() not in _REPLACEMENT_STOPWORDS:
            return value
    return None


def _requote(template: str, value: str) -> str:
    stripped = (template or "").strip()
    if stripped.lower().startswith("n'"):
        return f"N'%{value}%'" if "%" in stripped else f"N'{value}'"
    if stripped.startswith("'") and stripped.endswith("'"):
        return f"'%{value}%'" if "%" in stripped else f"'{value}'"
    return value


def apply_filter_lifecycle(
    filters: Sequence[ActiveFilter],
    query: str,
    turn_index: int,
) -> Tuple[List[ActiveFilter], bool, bool, List[str]]:
    """Apply clear/replace rules. Returns (filters, cleared, replaced, notes)."""
    notes: List[str] = []
    if detect_filter_clear(query):
        held = list(filters)
        if held:
            notes.append("Active filters cleared by explicit user negation")
        return [], bool(held), False, notes

    replacement = _replacement_value(query)
    if replacement:
        replaced_filters: List[ActiveFilter] = []
        replaced = False
        for f in filters:
            if f.operator.lower() in _VALUE_OPERATORS:
                replaced_filters.append(
                    ActiveFilter(
                        entity=f.entity,
                        attribute=f.attribute,
                        operator=f.operator,
                        value=_requote(f.value, replacement),
                        origin_turn=turn_index,
                        source="session",
                    )
                )
                replaced = True
            else:
                replaced_filters.append(f)
        if replaced:
            notes.append(f"Filter value replaced with '{replacement}'")
            return replaced_filters, False, True, notes
    return list(filters), False, False, notes


# --- Turn orchestration -----------------------------------------------------


def session_key(request: AgentRequest) -> Optional[str]:
    """Namespace the client-supplied session id by data source.

    ``session_id`` is a chat section / conversation id supplied by the caller (a GUID in
    practice). Namespacing by ``source_id`` keeps two data sources — or two tenants — from
    ever sharing one filter state.
    """
    if not request.session_id:
        return None
    if request.source_id:
        return f"session:{request.source_id}:{request.session_id}"
    return f"session:{request.session_id}"


def prepare_conversation_context(
    request: AgentRequest,
    llm=None,
    store: Optional[SessionContextStore] = None,
) -> ConversationContextResult:
    """Coreference rewrite + filter inheritance for one turn (Phases 1.2 and 2.2)."""
    store = store or _session_store
    key = session_key(request)
    previous = store.get(key) if key else None
    turn_index = (previous.turn_index + 1) if previous else 1

    filters: List[ActiveFilter] = list(previous.active_filters) if previous else []
    sql_filters = extract_filters_from_sql(request.existing_code, turn_index)
    if not sql_filters and previous and previous.last_sql:
        sql_filters = extract_filters_from_sql(previous.last_sql, turn_index)
    filters = merge_filters(filters, sql_filters)

    filters, cleared, replaced, notes = apply_filter_lifecycle(filters, request.query, turn_index)

    # A *directed* optimization edit ("format this", "make it faster") is not an elided
    # follow-up: its subject is the editor SQL, so the sentence must not be rewritten.
    preflight = classify_scenario(request.query, bool(request.existing_code), allow_llm=False)
    skip_coreference = bool(request.existing_code) and preflight.scenario == GenerationMode.OPTIMIZATION

    if skip_coreference:
        coref = ConversationContextResult(
            original_query=request.query,
            rewritten_query=request.query,
            active_filters=list(filters),
            notes=notes,
            source="skipped_optimization",
        )
    else:
        coref = resolve_coreference(
            request.query,
            conversation_history=request.conversation_history,
            active_filters=filters,
            llm=llm,
            turn_index=turn_index,
        )
        coref.active_filters = merge_filters(filters, coref.carried_filters)
        coref.notes = notes + coref.notes
    coref.filters_cleared = cleared
    coref.replacement_applied = replaced
    coref.session_id = key

    if key:
        store.put(
            SessionSemanticContext(
                session_id=key,
                source_id=request.source_id,
                active_filters=coref.active_filters,
                active_domains=list(previous.active_domains) if previous else [],
                target_grain=previous.target_grain if previous else None,
                turn_index=turn_index,
                last_sql=request.existing_code or (previous.last_sql if previous else None),
            )
        )
    return coref


def apply_conversation_context(context: AgentContext, result: ConversationContextResult) -> AgentContext:
    """Write the resolved context back onto the agent context used by routing/prompts."""
    context.session_id = result.session_id
    context.rewritten_query = result.rewritten_query
    context.coreference_notes = list(result.notes)
    context.active_filters = list(result.active_filters)
    context.filter_state_text = result.filter_state_text()
    if result.was_rewritten and result.rewritten_query:
        context.combined_query = fold_conversation(result.rewritten_query, context.request.conversation_history)
    return context


def record_generation_outcome(
    context: AgentContext,
    sql: Optional[str],
    target_grain: Optional[str] = None,
    store: Optional[SessionContextStore] = None,
) -> None:
    """Persist what the generated query actually filters on for the next turn."""
    store = store or _session_store
    key = context.session_id
    if not key:
        return
    current = store.get(key) or SessionSemanticContext(session_id=key, source_id=context.request.source_id)
    generated = extract_filters_from_sql(sql, current.turn_index) if sql else []
    current.active_filters = merge_filters(current.active_filters, generated)
    current.last_sql = sql or current.last_sql
    if target_grain:
        current.target_grain = target_grain
    if context.request.source_id:
        current.source_id = context.request.source_id
    store.put(current)
