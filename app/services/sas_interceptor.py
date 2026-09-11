"""Safety gate for generated SAS. Dangerous OS/network ops are blocked."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
_STAR_COMMENT = re.compile(r"(?m)^\s*\*.*?;")
_STRING_DOUBLE = re.compile(r'"(?:\\.|[^"\\])*"')
_STRING_SINGLE = re.compile(r"'(?:\\.|[^'\\])*'")

DANGEROUS = re.compile(
    r"(?is)\b("
    r"X\s*['\"]|"
    r"CALL\s+SYSTEM|"
    r"SYSTASK|"
    r"%SYSEXEC|"
    r"FILENAME\s+\w+\s+PIPE|"
    r"\bDDE\b"
    r")"
)
WRITE_FILE = re.compile(r"(?is)\bPROC\s+EXPORT\b")


class SASInterceptor:
    def check(self, code: str, user_requested_write: bool = False) -> Tuple[bool, Optional[str]]:
        stripped = self._strip(code or "")
        if not stripped.strip():
            return False, "Empty SAS code"
        if DANGEROUS.search(stripped) and not user_requested_write:
            return False, "Dangerous SAS operation blocked by safety policy"
        if WRITE_FILE.search(stripped) and not user_requested_write:
            return False, "Filesystem write blocked unless explicitly requested"
        return True, None

    def _strip(self, code: str) -> str:
        text = _BLOCK_COMMENT.sub(" ", code)
        text = _STAR_COMMENT.sub(" ", text)
        text = _STRING_DOUBLE.sub('""', text)
        text = _STRING_SINGLE.sub("''", text)
        return text
