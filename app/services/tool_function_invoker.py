"""MCP (Streamable HTTP) + sub-agent tool execution with argument sanitization."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolFunctionInvoker:
    def __init__(self, source_id: str, skills_root: Optional[Path] = None):
        self.source_id = source_id
        self.skills_root = skills_root
        self.tools: List[Dict[str, Any]] = []
        if skills_root:
            self._load_markdown_tools(skills_root)

    def _load_markdown_tools(self, root: Path) -> None:
        tools_dir = root / "tools"
        if not tools_dir.exists():
            return
        for path in tools_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.tools.append({"name": path.stem, "path": str(path), "raw": text})

    def sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        for key, value in (args or {}).items():
            if key.lower() in {"schema", "table", "column", "sql"} and isinstance(value, str):
                cleaned[key] = value.replace(";", "").strip()
            else:
                cleaned[key] = value
        return cleaned

    def invoke(self, name: str, arguments: Dict[str, Any]) -> str:
        args = self.sanitize_args(arguments)
        logger.info("Tool invoke source_id=%s name=%s", self.source_id, name)
        return json.dumps({"tool": name, "arguments": args, "result": None})
