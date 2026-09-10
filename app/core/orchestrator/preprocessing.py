"""Request preprocessing: PII mask, object auto-extraction, hydration hints."""

from __future__ import annotations

from typing import List, Optional

from app.core.constants import MaxAutoExtractedObjects, OlderAnswerTruncateChars
from app.models.pipeline import AgentContext, AgentRequest, ConversationTurn, SchemaMetadata
from app.models.schemas import GenerateSQLRequest
from app.utils.pii import mask_pii
from app.utils.regexes import extract_qualified_object_names


def parse_query_history(raw: Optional[str]) -> List[ConversationTurn]:
    if not raw:
        return []
    turns: List[ConversationTurn] = []
    parts = [p.strip() for p in raw.replace(" | ", "\n").split("\n") if p.strip()]
    current_q = None
    for part in parts:
        if part.lower().startswith("q:"):
            current_q = part[2:].strip()
        elif part.lower().startswith("a:"):
            turns.append(ConversationTurn(question=current_q or "", answer=part[2:].strip()))
            current_q = None
        else:
            turns.append(ConversationTurn(question=part, answer=None))
    return turns


def fold_conversation(query: str, history: List[ConversationTurn]) -> str:
    if not history:
        return query
    chunks = []
    last_idx = len(history) - 1
    for i, turn in enumerate(history):
        q = turn.question or ""
        if turn.failed:
            a = "[failed]"
        elif turn.canceled:
            a = "[canceled]"
        else:
            a = turn.answer or ""
            if i != last_idx and len(a) > OlderAnswerTruncateChars:
                a = a[:OlderAnswerTruncateChars]
        chunks.append(f"Q: {q} | A: {a}")
    return f"{query}\n" + "\n".join(chunks)


def build_agent_request(http: GenerateSQLRequest, source_id: Optional[str]) -> AgentRequest:
    masked = mask_pii(http.query or "")
    history = parse_query_history(http.queryHistory)
    pins = list(http.database_objects or [])
    override = list(http.table_override or [])
    existing = http.existing_code or http.previousSQL
    return AgentRequest(
        query=masked,
        existing_code=existing,
        error_message=http.error_message,
        database_objects=pins,
        top_k=http.top_k or 8,
        conversation_history=history,
        is_user_code=bool(http.is_user_code),
        source_id=source_id,
        table_override=override,
        semantic_mode=http.semantic_mode,
        force_general=bool(http.forceGeneral),
    )


def preprocess(request: AgentRequest, stores=None) -> AgentContext:
    notes: List[str] = []
    resolved: List[str] = []
    if not request.database_objects:
        extracted = extract_qualified_object_names(request.query, MaxAutoExtractedObjects)
        resolved = extracted
        if extracted:
            notes.append(f"Auto-extracted objects: {', '.join(extracted)}")
    combined = fold_conversation(request.query, request.conversation_history)
    mode = "fresh_start"
    is_recovery = False
    if request.error_message and request.existing_code:
        mode = "debugging"
        is_recovery = True
    elif request.existing_code:
        mode = "optimization"
    from app.core.branch_taxonomy import GenerationMode

    return AgentContext(
        request=request,
        schema_metadata=SchemaMetadata(resolved_object_names=resolved, resolution_notes=notes),
        generation_mode=GenerationMode(mode),
        is_error_recovery=is_recovery,
        combined_query=combined,
    )
