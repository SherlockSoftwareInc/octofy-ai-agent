"""Safety gate for generated SQL. Dangerous DML/DDL blocked unless explicitly requested."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_STRINGS = re.compile(r"(N?'(?:''|[^'])*')", re.IGNORECASE)
_BLOCK_COMMENTS = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENTS = re.compile(r"--.*?$", re.MULTILINE)

DANGEROUS = re.compile(
    r"\b(DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE\s+LOGIN|CREATE\s+USER|EXEC(?:UTE)?\s+xp_|SHUTDOWN)\b",
    re.IGNORECASE,
)
WRITE_OPS = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE)\b", re.IGNORECASE)
TEMP_OBJECT = re.compile(r"(#\w+|tempdb\.)", re.IGNORECASE)


class QueryInterceptor:
    def check(self, sql: str, user_requested_write: bool = False) -> Tuple[bool, Optional[str]]:
        stripped = self._strip(sql or "")
        if not stripped.strip():
            return False, "Empty SQL"
        if DANGEROUS.search(stripped) and not user_requested_write:
            return False, "Dangerous operation blocked by safety policy"
        if WRITE_OPS.search(stripped) and not user_requested_write:
            if TEMP_OBJECT.search(stripped):
                return True, None
            return False, "Write operation blocked unless explicitly requested"
        return True, None

    def _strip(self, sql: str) -> str:
        text = _BLOCK_COMMENTS.sub(" ", sql)
        text = _LINE_COMMENTS.sub(" ", text)
        text = _STRINGS.sub("''", text)
        return text
