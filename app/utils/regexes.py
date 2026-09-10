"""Regex helpers used by routing, extraction, and sentinel parsing."""

import re
from typing import List, Optional, Tuple

SQL_STATEMENT_START = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|SET\s+NOCOUNT|SET\s+TRANSACTION|SET\s+ANSI|WITH\s+\w+)",
    re.IGNORECASE,
)

CLAUSE_PAIR = re.compile(
    r"(select\b[\s\S]{0,400}\bfrom\b)|(insert\s+into\b)|(update\b[\s\S]{0,200}\bset\b)|(delete\s+from\b)|(merge\s+into\b)",
    re.IGNORECASE,
)

INLINE_SQL_BLOCK = re.compile(r"```(?:sql|tsql)?\s*([\s\S]*?)```", re.IGNORECASE)

FENCE_SQL = re.compile(r"```(?:sql|tsql|smq)?\s*([\s\S]*?)```", re.IGNORECASE)

OBJECT_NAME = re.compile(
    r"(?:\[(?P<schema1>[^\]]+)\]|(?P<schema2>\w+))\.(?:\[(?P<object1>[^\]]+)\]|(?P<object2>\w+))"
)

BARE_OBJECT = re.compile(r"\b(?:from|join|into|update|table)\s+\[?([A-Za-z_][\w]*)\]?", re.IGNORECASE)

SENTINEL_TABLE = re.compile(r"TABLE_VALIDATION_ERROR[:\s]+([^\n;]+)", re.IGNORECASE)
SENTINEL_COLUMN = re.compile(r"COLUMN_VALIDATION_ERROR[:\s]+([^\n;]+)", re.IGNORECASE)

COMPLEX_KEYWORDS = (
    "join",
    "group by",
    "having",
    "union",
    "except",
    "intersect",
    "compare",
    "versus",
    " vs ",
)

STRONG_DB_WORDS = (
    "select",
    "insert",
    "update",
    "delete",
    "merge",
    "from",
    "where",
    "table",
    "view",
    "database",
    "query",
    "sql",
)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def word_count(text: str) -> int:
    collapsed = collapse_whitespace(text)
    if not collapsed:
        return 0
    return len(collapsed.split())


def extract_inline_sql(text: str) -> Optional[str]:
    if not text:
        return None
    match = INLINE_SQL_BLOCK.search(text)
    if match:
        return match.group(1).strip()
    return None


def strip_markdown_fences(text: str) -> str:
    if not text:
        return ""
    match = FENCE_SQL.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_validation_sentinels(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (table_error, column_error) extracted from LLM/validator output."""
    table = None
    column = None
    if not text:
        return table, column
    tm = SENTINEL_TABLE.search(text)
    if tm:
        table = tm.group(1).strip()
    cm = SENTINEL_COLUMN.search(text)
    if cm:
        column = cm.group(1).strip()
    return table, column


def extract_qualified_object_names(text: str, limit: int = 5) -> List[str]:
    if not text:
        return []
    names: List[str] = []
    seen = set()
    for match in OBJECT_NAME.finditer(text):
        schema = match.group("schema1") or match.group("schema2")
        obj = match.group("object1") or match.group("object2")
        qualified = f"{schema}.{obj}"
        key = qualified.lower()
        if key not in seen:
            seen.add(key)
            names.append(qualified)
        if len(names) >= limit:
            return names
    return names


def complexity_tier(text: str) -> str:
    lowered = f" {(text or '').lower()} "
    hits = sum(1 for kw in COMPLEX_KEYWORDS if kw in lowered)
    if hits >= 2:
        return "complex"
    if hits == 1:
        return "moderate"
    return "simple"
