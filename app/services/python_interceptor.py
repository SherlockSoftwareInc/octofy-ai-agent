"""Safety gate for generated Python. Dangerous OS/network/eval ops are blocked."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_TRIPLE_DOUBLE = re.compile(r'""".*?"""', re.DOTALL)
_TRIPLE_SINGLE = re.compile(r"'''.*?'''", re.DOTALL)
_SINGLE_STRING = re.compile(r"'(?:\\.|[^'\\])*'")
_DOUBLE_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
_COMMENTS = re.compile(r"#.*?$", re.MULTILINE)

DANGEROUS = re.compile(
    r"\b("
    r"os\.system|os\.popen|os\.remove|os\.unlink|os\.rmdir|os\.removedirs|"
    r"subprocess\.|shutil\.|socket\.|ctypes\.|multiprocessing\.|"
    r"pickle\.|requests\.|urllib\.request|"
    r"eval\s*\(|exec\s*\(|compile\s*\(|__import__\s*\("
    r")",
    re.IGNORECASE,
)
WRITE_OPEN = re.compile(
    r"""\bopen\s*\([^)]*(?:mode\s*=\s*)?['"][wax]""",
    re.IGNORECASE,
)


class PythonInterceptor:
    def check(self, code: str, user_requested_write: bool = False) -> Tuple[bool, Optional[str]]:
        stripped = self._strip(code or "")
        if not stripped.strip():
            return False, "Empty Python code"
        if DANGEROUS.search(stripped) and not user_requested_write:
            return False, "Dangerous Python operation blocked by safety policy"
        if WRITE_OPEN.search(code or "") and not user_requested_write:
            return False, "Filesystem write blocked unless explicitly requested"
        if "sqlalchemy.create_engine(" in stripped and "DB_CONNECTION_STRING" not in (code or ""):
            return False, "create_engine must use the injected DB_CONNECTION_STRING"
        return True, None

    def _strip(self, code: str) -> str:
        text = _TRIPLE_DOUBLE.sub("''", code)
        text = _TRIPLE_SINGLE.sub("''", text)
        text = _SINGLE_STRING.sub("''", text)
        text = _DOUBLE_STRING.sub("''", text)
        text = _COMMENTS.sub(" ", text)
        return text
