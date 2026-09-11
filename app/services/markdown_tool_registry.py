"""Per-data-source markdown tool registry (tools/*.md with YAML front matter)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_REGISTRY_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return ""
    if text[0] in {"[", "{"}:
        try:
            import json

            return json.loads(text)
        except Exception:
            pass
    if "," in text and not text.startswith(("http://", "https://")):
        return [part.strip() for part in text.split(",") if part.strip()]
    lowered = text.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    return text.strip("'\"")


def _parse_front_matter(block: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    current_key: Optional[str] = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key:
            existing = parsed.get(current_key)
            if not isinstance(existing, list):
                parsed[current_key] = [] if existing in (None, "") else [existing]
            parsed[current_key].append(stripped[2:].strip().strip("'\""))
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        current_key = key.strip()
        parsed[current_key] = _parse_scalar(value)
    return parsed


def parse_tool_markdown(text: str, stem: str, path: Optional[str] = None) -> Dict[str, Any]:
    match = _FRONT_MATTER_RE.match(text or "")
    body = text or ""
    meta: Dict[str, Any] = {}
    if match:
        meta = _parse_front_matter(match.group(1))
        body = match.group(2) or ""

    hints = meta.get("hints") or meta.get("trigger") or meta.get("keywords") or []
    if isinstance(hints, str):
        hints = [part.strip() for part in hints.split(",") if part.strip()]

    name = str(meta.get("name") or stem).strip()
    return {
        "name": name,
        "description": str(meta.get("description") or "").strip(),
        "protocol": str(meta.get("protocol") or "").strip().lower(),
        "hints": [str(h).strip() for h in hints if str(h).strip()],
        "instructions": body.strip(),
        "server_url": str(meta.get("server_url") or meta.get("endpoint") or "").strip(),
        "mcp_tool": str(meta.get("mcp_tool") or meta.get("tool") or name).strip(),
        "model": str(meta.get("model") or "").strip(),
        "parameters": meta.get("parameters") if isinstance(meta.get("parameters"), dict) else {},
        "path": path or "",
        "raw": text,
    }


class MarkdownToolRegistryService:
    def get_all_tools(self, folder: Path | str) -> List[Dict[str, Any]]:
        root = Path(folder)
        tools_dir = root / "tools" if root.name != "tools" else root
        if not tools_dir.is_dir():
            return []

        cache_key = str(tools_dir.resolve())
        newest = max((p.stat().st_mtime for p in tools_dir.glob("*.md")), default=0.0)
        cached = _REGISTRY_CACHE.get(cache_key)
        if cached and cached[0] == newest:
            return list(cached[1])

        tools: List[Dict[str, Any]] = []
        for path in sorted(tools_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            tools.append(parse_tool_markdown(text, path.stem, str(path)))
        _REGISTRY_CACHE[cache_key] = (newest, tools)
        return list(tools)
