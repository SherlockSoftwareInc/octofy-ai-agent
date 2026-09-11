"""Discuss/Ask prompt assembly and recent-thread helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MAX_RECENT_TURNS = 8
MAX_OLDER_LINE_CHARS = 300
MAX_SCHEMA_OBJECTS = 60
MAX_SCHEMA_COLUMNS = 16
MAX_SELECTED_COLUMNS = 24
COLUMN_NAME_RE = re.compile(r"^\s*[-*]\s+\*?\*?`?\[?([A-Za-z_][\w\s]*)\]?`?\*?\*?", re.MULTILINE)
TABLE_COLUMN_RE = re.compile(r"^\|\s*\d+\s*\|\s*`?\[?([A-Za-z_][\w\s]*)\]?`?\s*\|", re.MULTILINE)
TRAILING_PUNCT_RE = re.compile(r"[.!?,。]+$")
ROLE_PREFIX_RE = re.compile(r"^(user|assistant|ai)\s*:\s?(.*)$", re.IGNORECASE)


def _normalize_role(role: str) -> str:
    value = (role or "user").strip().lower()
    if value in {"assistant", "ai"}:
        return "assistant"
    return "user"


def _finalize_turns(
    turns: List[Tuple[str, str]],
    exclude_current: bool,
    current_query: Optional[str],
) -> List[Tuple[str, str]]:
    cleaned = [(role, content.strip()) for role, content in turns if str(content or "").strip()]
    if exclude_current and cleaned and cleaned[-1][0] == "user":
        last = cleaned[-1][1]
        incoming = (current_query or "").strip()
        if not incoming or last == incoming:
            cleaned = cleaned[:-1]
    return cleaned[-MAX_RECENT_TURNS:]


def _parse_history_json(raw: str) -> Optional[List[Tuple[str, str]]]:
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, list):
        return None
    turns: List[Tuple[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        turns.append((_normalize_role(str(item.get("role") or "user")), content))
    return turns


def parse_recent_conversation(
    query_history: Optional[str],
    exclude_current: bool = True,
    current_query: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Parse prior Ask turns as whole messages, not as individual lines.

    A markdown assistant reply contains many blank/bullet lines. Splitting those
    into fake user/assistant turns drops the real thread after MAX_RECENT_TURNS.
    """
    if not query_history:
        return []
    raw = str(query_history).strip()
    if not raw:
        return []

    json_turns = _parse_history_json(raw)
    if json_turns is not None:
        return _finalize_turns(json_turns, exclude_current, current_query)

    turns: List[Tuple[str, str]] = []
    current_role: Optional[str] = None
    current_parts: List[str] = []

    def flush() -> None:
        nonlocal current_role, current_parts
        if current_role is None:
            return
        text = "\n".join(current_parts).strip()
        if text:
            turns.append((current_role, text))
        current_role = None
        current_parts = []

    for raw_line in str(query_history).splitlines():
        match = ROLE_PREFIX_RE.match(raw_line.strip())
        if match:
            flush()
            current_role = _normalize_role(match.group(1))
            current_parts = [match.group(2)]
            continue
        if current_role is None:
            current_role = "user"
            current_parts = [raw_line]
        else:
            current_parts.append(raw_line)
    flush()
    return _finalize_turns(turns, exclude_current, current_query)


def format_recent_conversation_lines(turns: Sequence[Tuple[str, str]]) -> List[str]:
    lines: List[str] = []
    last_index = len(turns) - 1
    for index, (role, content) in enumerate(turns):
        text = " ".join(str(content or "").split())
        if index != last_index and len(text) > MAX_OLDER_LINE_CHARS:
            text = text[:MAX_OLDER_LINE_CHARS].rstrip() + "..."
        lines.append(f"{role}: {text}")
    return lines


def build_recent_conversation_section(turns: Sequence[Tuple[str, str]]) -> str:
    if not turns:
        return ""
    lines = format_recent_conversation_lines(turns)
    return (
        "## RECENT CONVERSATION\n"
        + "\n".join(lines)
        + "\nA short follow-up (yes, please, go on, elaborate) is not off-topic "
        "and must inherit the thread's intent."
    )


def is_thread_continuation(recent_context: Sequence[str] | str, message: str) -> bool:
    text = TRAILING_PUNCT_RE.sub("", (message or "").strip())
    if len(text) > 40:
        return False
    if isinstance(recent_context, str):
        haystack = recent_context
    else:
        haystack = "\n".join(recent_context)
    return "assistant:" in haystack.lower()


def build_tool_selection_system_prompt(tools: Sequence[Dict[str, Any]]) -> str:
    lines = [
        "Select at most one tool that can answer the user's lookup question.",
        "If none apply, call no tool.",
        "",
    ]
    for tool in tools:
        lines.append(f"- {tool.get('name')}: {tool.get('description') or ''}")
        if tool.get("instructions"):
            lines.append(f"  Trigger: {tool['instructions'][:400]}")
    return "\n".join(lines)


def build_discuss_persona() -> str:
    return (
        "You are the data-analysis assistant for Octofy. Discuss what the data contains, "
        "brainstorm KPIs and metrics, plan dashboards and reports, explain what can be done "
        "with this database, and give step-by-step guidance. Answer conversationally in the "
        "user's language. Markdown is allowed. Illustrative SQL is allowed. Follow through "
        "when the user agrees with a short \"yes\" instead of repeating the offer or deferring "
        "to another tool. Full runnable scripts belong in Generate SQL / R / SAS / Python."
    )


def _iter_object_index_entries(folder: Path) -> Iterable[Dict[str, Any]]:
    schemas_dir = folder / "schemas"
    if not schemas_dir.is_dir():
        return
    for index_file in sorted(schemas_dir.rglob(".object-index.json")):
        try:
            payload = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        schema_name = payload.get("schema") or index_file.parent.name
        for obj in payload.get("objects") or []:
            if not isinstance(obj, dict):
                continue
            yield {
                "schema": obj.get("schema_name") or schema_name,
                "name": obj.get("object_name") or obj.get("name") or "",
                "type": obj.get("object_type") or obj.get("type") or "",
                "description": obj.get("description") or "",
                "file_name": obj.get("file_name") or "",
                "folder": index_file.parent,
            }


def _column_names_from_markdown(path: Path, limit: int) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    names: List[str] = []
    for match in list(TABLE_COLUMN_RE.finditer(text)) + list(COLUMN_NAME_RE.finditer(text)):
        name = match.group(1).strip()
        if name.lower() in {"description", "columns", "data source", "schema", "type", "ord", "name"}:
            continue
        if name in names:
            continue
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _object_file(entry: Dict[str, Any]) -> Optional[Path]:
    folder = entry.get("folder")
    file_name = entry.get("file_name")
    if folder and file_name:
        path = Path(folder) / str(file_name)
        if path.exists():
            return path
    if folder and entry.get("schema") and entry.get("name"):
        candidate = Path(folder) / f"{entry['schema']}.{entry['name']}.md"
        if candidate.exists():
            return candidate
    return None


def build_database_schema_context(folder: Optional[Path]) -> str:
    if folder is None or not folder.exists():
        return ""
    lines: List[str] = []
    for entry in _iter_object_index_entries(folder):
        if not entry.get("name"):
            continue
        path = _object_file(entry)
        columns = _column_names_from_markdown(path, MAX_SCHEMA_COLUMNS) if path else []
        column_text = ", ".join(columns) if columns else ""
        suffix = f": {column_text}" if column_text else ""
        type_label = f" ({entry['type']})" if entry.get("type") else ""
        lines.append(f"[{entry['schema']}].[{entry['name']}]{type_label}{suffix}")
        if len(lines) >= MAX_SCHEMA_OBJECTS:
            break
    if not lines:
        return ""
    return "### DATABASE SCHEMA (current data source)\n" + "\n".join(lines)


def _normalize_object_key(raw: str) -> Tuple[str, str]:
    cleaned = (raw or "").replace("[", "").replace("]", "").strip()
    if "." in cleaned:
        schema, name = cleaned.split(".", 1)
        return schema.strip(), name.strip()
    return "", cleaned


def build_selected_objects_context(folder: Optional[Path], selected: Optional[Sequence[str]]) -> str:
    if not selected:
        return ""
    wanted = {_normalize_object_key(item) for item in selected if item}
    if not wanted:
        return ""
    entries = list(_iter_object_index_entries(folder)) if folder and folder.exists() else []
    by_key = {(str(e.get("schema") or "").lower(), str(e.get("name") or "").lower()): e for e in entries}
    lines = ["### SELECTED DATABASE OBJECTS (discussion focus)", "Prioritize these objects in your reply."]
    for schema, name in wanted:
        entry = by_key.get((schema.lower(), name.lower()))
        if entry is None and name:
            entry = next((e for key, e in by_key.items() if key[1] == name.lower()), None)
        label = f"[{schema or (entry or {}).get('schema') or 'dbo'}].[{name}]"
        description = (entry or {}).get("description") or ""
        path = _object_file(entry) if entry else None
        columns = _column_names_from_markdown(path, MAX_SELECTED_COLUMNS) if path else []
        lines.append(label)
        if description:
            lines.append(description)
        if columns:
            lines.append("Columns: " + ", ".join(columns))
    return "\n".join(lines)


def build_query_and_error_context(current_query: Optional[str], running_error: Optional[str]) -> str:
    parts: List[str] = []
    if current_query and current_query.strip():
        parts.append(f"Current query:\n{current_query.strip()}")
    if running_error and running_error.strip():
        parts.append(f"Running error:\n{running_error.strip()}")
    if not parts:
        return ""
    return "### CURRENT QUERY / ERROR CONTEXT\n" + "\n\n".join(parts)


def build_database_context_summary(folder: Optional[Path], dialect: str = "T-SQL") -> str:
    names: List[str] = []
    if folder and folder.exists():
        for entry in _iter_object_index_entries(folder):
            if entry.get("name"):
                names.append(f"[{entry.get('schema')}].[{entry.get('name')}]")
            if len(names) >= MAX_SCHEMA_OBJECTS:
                break
    object_list = ", ".join(names) if names else "(schema catalog unavailable)"
    return (
        f"Connected database dialect: {dialect}.\n"
        f"Known objects: {object_list}.\n"
        "A question that could plausibly be answered by querying this data is db_query, "
        "even if the topic seems unusual."
    )


def build_classifier_prompt(folder: Optional[Path], recent_turns: Sequence[Tuple[str, str]], dialect: str = "T-SQL") -> str:
    return (
        "You are an intent classifier for a data discussion assistant.\n"
        "Classify the user message as exactly one of: db_query, app_feature, off_topic.\n"
        "- db_query: a data question, SQL help, dashboard/KPI planning, or anything matching the connected database.\n"
        "- app_feature: a question about Octofy itself or a self-introduction request.\n"
        "- off_topic: unrelated to the database and the tool.\n"
        "Reply with compact JSON only: {\"intent\":\"db_query|app_feature|off_topic\",\"reply\":\"\"}.\n"
        "For app_feature or off_topic, put a friendly plain-text answer in reply. "
        "For db_query leave reply empty.\n\n"
        f"{build_database_context_summary(folder, dialect)}\n\n"
        f"{build_recent_conversation_section(recent_turns)}"
    )


def looks_like_sql_statement(text: str) -> bool:
    stripped = (text or "").lstrip().lower()
    return stripped.startswith(("select ", "with ", "insert ", "update ", "delete ", "merge "))


def extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}
