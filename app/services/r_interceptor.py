"""Safety gate for generated R. Dangerous OS/network/eval ops are blocked."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_STRING_DOUBLE = re.compile(r'"(?:\\.|[^"\\])*"')
_STRING_SINGLE = re.compile(r"'(?:\\.|[^'\\])*'")
_RAW_STRING = re.compile(r'(?i)[rR]"(?:\[|\(|\{)?[\s\S]*?(?:\]|\)|\})?"')
_COMMENTS = re.compile(r"#.*?$", re.MULTILINE)

DANGEROUS = re.compile(
    r"\b("
    r"system\s*\(|system2\s*\(|shell\s*\(|"
    r"unlink\s*\(|file\.remove\s*\(|file\.rename\s*\(|"
    r"Sys\.chmod|Sys\.setFileTime|"
    r"download\.file\s*\(|install\.packages\s*\(|"
    r"eval\s*\(\s*parse\s*\(|parse\s*\(\s*text\s*="
    r")",
    re.IGNORECASE,
)
WRITE_FILE = re.compile(
    r"\b(write\.(csv|table|dta|xlsx)|saveRDS|save\s*\(|ggsave)\s*\(",
    re.IGNORECASE,
)


class RInterceptor:
    def check(self, code: str, user_requested_write: bool = False) -> Tuple[bool, Optional[str]]:
        stripped = self._strip(code or "")
        if not stripped.strip():
            return False, "Empty R code"
        if DANGEROUS.search(stripped) and not user_requested_write:
            return False, "Dangerous R operation blocked by safety policy"
        if WRITE_FILE.search(stripped) and not user_requested_write:
            return False, "Filesystem write blocked unless explicitly requested"
        return True, None

    def _strip(self, code: str) -> str:
        text = _RAW_STRING.sub('""', code)
        text = _STRING_DOUBLE.sub('""', text)
        text = _STRING_SINGLE.sub("''", text)
        text = _COMMENTS.sub(" ", text)
        return text
