"""MCP / sub-agent tool execution, hint matching, and native tool-call parsing."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.utils.logging_utils import log_llm_interaction

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "at", "by",
    "is", "are", "was", "were", "be", "what", "which", "who", "how", "do",
    "does", "did", "please", "me", "my", "your", "this", "that", "with",
}

_HINT_ALIASES = {
    "code": ("code", "codes"),
    "codes": ("code", "codes"),
    "icd": ("icd", "icd-10", "icd10"),
    "icd-10": ("icd", "icd-10", "icd10"),
    "icd10": ("icd", "icd-10", "icd10"),
}


def _tokenize(text: str) -> List[str]:
    return [tok for tok in re.findall(r"[a-z0-9][a-z0-9\-]*", (text or "").lower()) if tok]


class ToolFunctionInvoker:
    def __init__(self, source_id: str = "", skills_root: Optional[Path] = None):
        self.source_id = source_id
        self.skills_root = skills_root
        self.tools: List[Dict[str, Any]] = []
        if skills_root:
            self._load_markdown_tools(skills_root)

    def _load_markdown_tools(self, root: Path) -> None:
        from app.services.markdown_tool_registry import MarkdownToolRegistryService

        self.tools = MarkdownToolRegistryService().get_all_tools(root)

    @staticmethod
    def matches_tool_hint(query: str, tools: List[Dict[str, Any]]) -> bool:
        tokens = [tok for tok in _tokenize(query) if tok not in _STOPWORDS]
        if not tokens:
            return False
        expanded = set(tokens)
        for tok in tokens:
            expanded.update(_HINT_ALIASES.get(tok, ()))
        for tool in tools or []:
            haystack = " ".join(
                [
                    str(tool.get("name") or ""),
                    str(tool.get("description") or ""),
                    str(tool.get("instructions") or ""),
                    " ".join(str(h) for h in (tool.get("hints") or [])),
                ]
            ).lower()
            if any(token in haystack for token in expanded):
                return True
        return False

    @staticmethod
    def build_function_tools_payload(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for tool in tools or []:
            parameters = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Lookup text or identifier"},
                },
            }
            payload.append({
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description") or tool.get("instructions") or "",
                    "parameters": parameters,
                },
            })
        return payload

    @staticmethod
    def build_responses_tools_payload(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for tool in tools or []:
            parameters = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            }
            payload.append({
                "type": "function",
                "name": tool.get("name"),
                "description": tool.get("description") or "",
                "parameters": parameters,
            })
        return payload

    @staticmethod
    def build_responses_input(system_prompt: str, query: str) -> List[Dict[str, Any]]:
        return [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": query}]},
        ]

    @staticmethod
    def sanitize_mcp_tool_arguments(tool: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        allowed = set((tool.get("parameters") or {}).get("properties", {}).keys()) if isinstance(tool.get("parameters"), dict) else set()
        cleaned: Dict[str, Any] = {}
        for key, value in (args or {}).items():
            if allowed and key not in allowed and key != "query":
                continue
            if key.lower() in {"schema", "table", "column", "sql"} and isinstance(value, str):
                cleaned[key] = value.replace(";", "").strip()
            else:
                cleaned[key] = value
        return cleaned

    def sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.sanitize_mcp_tool_arguments({}, args)

    @staticmethod
    def parse_tool_call(response: Any) -> Tuple[str, Dict[str, Any]]:
        message = _first_message(response)
        tool_calls = getattr(message, "tool_calls", None) if message is not None else None
        if tool_calls is None and isinstance(message, dict):
            tool_calls = message.get("tool_calls")
        if not tool_calls:
            return "", {}
        first = tool_calls[0]
        function = getattr(first, "function", None) or (first.get("function") if isinstance(first, dict) else None)
        if function is None and isinstance(first, dict):
            name = first.get("name") or ""
            raw_args = first.get("arguments") or first.get("args") or {}
        else:
            name = getattr(function, "name", None) or (function.get("name") if isinstance(function, dict) else "") or ""
            raw_args = getattr(function, "arguments", None) or (function.get("arguments") if isinstance(function, dict) else {}) or {}
        return str(name), _coerce_args(raw_args)

    @staticmethod
    def parse_tool_call_responses(response: Any) -> Tuple[str, Dict[str, Any]]:
        output = getattr(response, "output", None)
        if output is None and isinstance(response, dict):
            output = response.get("output") or response.get("choices")
        if not output:
            return ToolFunctionInvoker.parse_tool_call(response)
        first = output[0]
        name = getattr(first, "name", None) or (first.get("name") if isinstance(first, dict) else "")
        raw_args = getattr(first, "arguments", None) or (first.get("arguments") if isinstance(first, dict) else {})
        if name:
            return str(name), _coerce_args(raw_args)
        return ToolFunctionInvoker.parse_tool_call(response)

    @staticmethod
    def try_parse_mcp_response_json(raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return ""
        if text.startswith("data:"):
            chunks = []
            for line in text.splitlines():
                if line.startswith("data:"):
                    chunks.append(line[5:].strip())
            text = "\n".join(chunks) or text
        try:
            parsed = json.loads(text)
        except Exception:
            return raw
        if isinstance(parsed, dict):
            result = parsed.get("result") or parsed.get("content") or parsed
            if isinstance(result, dict) and "content" in result:
                result = result["content"]
            if isinstance(result, list):
                parts = []
                for item in result:
                    if isinstance(item, dict):
                        parts.append(str(item.get("text") or item.get("content") or json.dumps(item)))
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        return raw

    def execute_mcp_tool_async(self, tool: Dict[str, Any], args: Dict[str, Any]) -> str:
        url = (tool.get("server_url") or "").strip()
        if not url:
            return ""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool.get("mcp_tool") or tool.get("name"), "arguments": args or {}},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
            log_llm_interaction({"tool": tool.get("name"), "mcp_request": body}, raw)
            return self.try_parse_mcp_response_json(raw)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("MCP tool call failed name=%s error=%s", tool.get("name"), exc)
            return ""

    def execute_sub_agent_async(self, tool: Dict[str, Any], args: Dict[str, Any]) -> str:
        from app.services.llm_service import get_llm_service

        query = str((args or {}).get("query") or json.dumps(args or {}, ensure_ascii=False))
        system = tool.get("instructions") or tool.get("description") or "Answer the lookup request."
        llm = get_llm_service()
        try:
            content = llm.chat_completion(
                [{"role": "system", "content": system}, {"role": "user", "content": query}],
                temperature=0.2,
            )
            log_llm_interaction({"tool": tool.get("name"), "sub_agent": True, "query": query}, content)
            return content or ""
        except Exception as exc:
            logger.warning("Sub-agent tool call failed name=%s error=%s", tool.get("name"), exc)
            return ""

    def invoke(self, name: str, arguments: Dict[str, Any]) -> str:
        tool = next((item for item in self.tools if str(item.get("name") or "").lower() == name.lower()), None)
        args = self.sanitize_mcp_tool_arguments(tool or {}, arguments)
        if tool and tool.get("protocol") == "mcp":
            return self.execute_mcp_tool_async(tool, args)
        if tool and tool.get("protocol") == "sub_agent":
            return self.execute_sub_agent_async(tool, args)
        logger.info("Tool invoke source_id=%s name=%s", self.source_id, name)
        return json.dumps({"tool": name, "arguments": args, "result": None})


def _first_message(response: Any) -> Any:
    if response is None:
        return None
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if choices:
        first = choices[0]
        return getattr(first, "message", None) or (first.get("message") if isinstance(first, dict) else first)
    return getattr(response, "message", None) or (response.get("message") if isinstance(response, dict) else None)


def _coerce_args(raw_args: Any) -> Dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str) and raw_args.strip():
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {"query": raw_args}
        except Exception:
            return {"query": raw_args}
    return {}
