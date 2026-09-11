"""Discuss/Ask turn pipeline: tool lookup, intent gate, prompt, conversational reply."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse
from app.services.discuss_prompts import (
    build_classifier_prompt,
    build_database_schema_context,
    build_discuss_persona,
    build_query_and_error_context,
    build_selected_objects_context,
    build_tool_selection_system_prompt,
    extract_json_object,
    format_recent_conversation_lines,
    is_thread_continuation,
    looks_like_sql_statement,
    parse_recent_conversation,
)
from app.services.markdown_tool_registry import MarkdownToolRegistryService
from app.services.tool_function_invoker import ToolFunctionInvoker
from app.utils.logging_utils import log_llm_interaction

logger = logging.getLogger(__name__)

ASK_QUERY_TYPE = "ask"


@dataclass
class DiscussToolResult:
    block: str
    tool_event_name: str = ""


def resolve_discuss_tool_folder(source_id: Optional[str]) -> Optional[Path]:
    if not source_id:
        return None
    try:
        from app.services.stores.skills_folder import resolve_data_source_folder

        return resolve_data_source_folder(source_id)
    except Exception as exc:
        logger.info("Discuss folder resolve failed source_id=%s error=%s", source_id, exc)
        return None


def try_resolve_tool_lookup(query: str, source_id: Optional[str]) -> Optional[DiscussToolResult]:
    if not (query or "").strip():
        return None
    folder = resolve_discuss_tool_folder(source_id)
    if folder is None:
        return None
    tools = MarkdownToolRegistryService().get_all_tools(folder)
    if not tools:
        return None
    if not ToolFunctionInvoker.matches_tool_hint(query, tools):
        return None

    selected_name, args = _select_tool(query, tools)
    if not selected_name:
        return None
    tool = next((item for item in tools if str(item.get("name") or "").lower() == selected_name.lower()), None)
    if tool is None:
        return None

    invoker = ToolFunctionInvoker(source_id or "", folder)
    protocol = str(tool.get("protocol") or "")
    text = ""
    if protocol == "sub_agent":
        text = invoker.execute_sub_agent_async(tool, args)
    elif protocol == "mcp":
        text = invoker.execute_mcp_tool_async(tool, invoker.sanitize_mcp_tool_arguments(tool, args))
    else:
        return None

    if text:
        block = (
            f"\n\n### TOOL RESULT ({tool.get('name')})\n{text}\n\n"
            "Use this tool result in your reply when it is relevant."
        )
        return DiscussToolResult(block=block, tool_event_name=str(tool.get("name") or ""))
    return DiscussToolResult(
        block=(
            "\n\n### TOOL LOOKUP FAILED\n"
            "The tool was selected but returned no value. Do not guess the value."
        ),
        tool_event_name=str(tool.get("name") or ""),
    )


def classify_discuss_intent(
    query: str,
    recent_turns: Sequence[Tuple[str, str]],
    source_id: Optional[str],
) -> Tuple[str, str]:
    if not (query or "").strip():
        return "db_query", ""
    folder = resolve_discuss_tool_folder(source_id)
    prompt = build_classifier_prompt(folder, recent_turns)
    try:
        from app.services.llm_client import LlmClient

        raw = LlmClient().complete(
            [{"role": "system", "content": prompt}, {"role": "user", "content": query}],
            max_tokens=4096,
        )
        log_llm_interaction({"discuss_classifier": True, "query": query}, raw)
    except Exception as exc:
        logger.warning("Discuss classifier failed: %s", exc)
        return "db_query", ""

    if not raw or looks_like_sql_statement(raw):
        return "db_query", ""
    parsed = extract_json_object(raw)
    intent = str(parsed.get("intent") or "").strip().lower().replace(" ", "_")
    reply = str(parsed.get("reply") or "").strip()
    if not intent:
        token = raw.strip().split()[0].lower().replace(" ", "_") if raw.strip() else ""
        intent = token
    if intent == "db_query":
        return "db_query", ""
    if intent in {"app_feature", "off_topic"}:
        if not reply:
            reply = (
                "I can help with questions about this database and Octofy."
                if intent == "app_feature"
                else "I can help with questions about this data. What would you like to explore?"
            )
        return intent, reply
    return "db_query", ""


def build_discuss_system_prompt(
    request: GenerateSQLRequest,
    tool_result: Optional[DiscussToolResult] = None,
) -> str:
    folder = resolve_discuss_tool_folder(request.source_id)
    selected = request.database_objects or request.user_selected_tables or request.table_override
    parts = [
        build_discuss_persona(),
        build_database_schema_context(folder),
        build_selected_objects_context(folder, selected),
        build_query_and_error_context(request.previousSQL, request.error_message),
    ]
    if tool_result and tool_result.block:
        parts.append(tool_result.block)
    return "\n\n".join(part for part in parts if part)


def discuss_conversation(request: GenerateSQLRequest) -> GenerateSQLResponse:
    query = (request.query or "").strip()
    recent_turns = parse_recent_conversation(request.queryHistory, exclude_current=True)
    recent_lines = format_recent_conversation_lines(recent_turns)

    tool_result: Optional[DiscussToolResult] = None
    try:
        tool_result = try_resolve_tool_lookup(query, request.source_id)
    except Exception as exc:
        logger.warning("Discuss tool lookup failed: %s", exc)

    if tool_result is None:
        try:
            intent, reply = classify_discuss_intent(query, recent_turns, request.source_id)
        except Exception as exc:
            logger.warning("Discuss intent classification failed: %s", exc)
            intent, reply = "db_query", ""
        if intent in {"app_feature", "off_topic"} and reply and not is_thread_continuation(recent_lines, query):
            return _ask_response(reply, tool_event="")

    system_prompt = build_discuss_system_prompt(request, tool_result)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for role, content in recent_turns:
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": query or "Continue the discussion."})

    try:
        from app.services.llm_service import get_llm_service

        answer = get_llm_service().chat_completion(messages, temperature=0.2) or ""
        log_llm_interaction(messages, answer)
    except Exception as exc:
        logger.error("Discuss completion failed: %s", exc)
        answer = f"I encountered an issue during the discussion: {exc}"

    return _ask_response(answer, tool_event=tool_result.tool_event_name if tool_result else "")


def generate_ask_summary(payload: Dict[str, Any]) -> str:
    history = payload.get("conversation_history") or payload.get("messages") or []
    lines: List[str] = []
    if isinstance(history, list):
        for turn in history:
            if not isinstance(turn, dict):
                continue
            user = turn.get("user") or (turn.get("content") if turn.get("role") == "user" else "")
            assistant = turn.get("assistant") or (turn.get("content") if turn.get("role") == "assistant" else "")
            if user:
                lines.append(f"User: {user}")
            if assistant:
                lines.append(f"Assistant: {assistant}")
    if not lines:
        goal = payload.get("goal") or ""
        if goal:
            lines.append(f"User: {goal}")
    selected = payload.get("selected_tables") or payload.get("selected_objects") or []
    if selected:
        lines.append("Selected objects: " + ", ".join(str(item) for item in selected))
    transcript = "\n".join(lines) or "No discussion yet."
    prompt = f"""Summarize this data discussion for a code-generation handoff.

Focus on what the user wants to analyze or accomplish, not on listing tables.
Keep it under 150 words in markdown with:
## Primary Request
## Data Sources (only if mentioned)
## Additional Requirements

Discussion:
{transcript}
"""
    try:
        from app.services.llm_service import get_llm_service

        return get_llm_service().chat(prompt) or transcript
    except Exception as exc:
        logger.error("Ask summary failed: %s", exc)
        return f"## Primary Request\n{transcript}"


def _select_tool(query: str, tools: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    from app.services.llm_service import get_llm_service
    import litellm

    llm = get_llm_service()
    system = build_tool_selection_system_prompt(tools)
    payload = ToolFunctionInvoker.build_function_tools_payload(tools)
    try:
        response = litellm.completion(
            model=getattr(llm, "model", None),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": query}],
            tools=payload,
            tool_choice="auto",
            max_tokens=1024,
            temperature=0.2,
            base_url=getattr(llm, "base_url", None),
            api_key=getattr(llm, "api_key", None),
            timeout=30,
        )
        log_llm_interaction({"discuss_tool_selection": True, "query": query}, str(response))
        return ToolFunctionInvoker.parse_tool_call(response)
    except Exception as exc:
        logger.info("Discuss tool selection skipped: %s", exc)
        return "", {}


def _ask_response(explanation: str, tool_event: str = "") -> GenerateSQLResponse:
    return GenerateSQLResponse(
        sql="",
        explanation=explanation,
        query_type=ASK_QUERY_TYPE,
        tool_event=tool_event or None,
    )
