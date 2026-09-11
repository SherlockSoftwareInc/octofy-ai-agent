"""R code extraction, SQL wrapping, and structural hashing."""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Tuple

_SQL_START = re.compile(
    r"^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|MERGE)\b",
    re.IGNORECASE,
)
_SQL_OBJECT = re.compile(
    r"(?is)\b(from|join|into|update)\s+(?:\[[^\]]+\]|[A-Za-z_][\w]*)"
)
_FENCE_R = re.compile(r"```(?:r|rscript)\s*([\s\S]*?)```", re.IGNORECASE)
_FENCE_ANY = re.compile(r"```[a-zA-Z0-9_-]*\s*([\s\S]*?)```")
_WHITESPACE = re.compile(r"\s+")
_R_COMMENT = re.compile(r"#.*?$", re.MULTILINE)
_RAW_OPENERS = {"(": ")", "[": "]", "{": "}"}


def looks_like_r(text: str) -> bool:
    if not text or not text.strip():
        return False
    stripped = text.strip()
    if stripped.startswith(("library(", "require(", "source(")):
        return True
    markers = (
        "library(DBI)",
        "library(dplyr)",
        "library(odbc)",
        "library(ggplot2)",
        "dbConnect(",
        "dbGetQuery(",
        "dbReadTable(",
        "dbDisconnect(",
        "%>%",
        "<- ",
    )
    return any(marker in stripped for marker in markers)


def cleanup_r_code(code: str) -> str:
    """Strip markdown fences and a leading `R`/`rscript` interpreter line."""
    if not code:
        return code

    code = code.strip()
    code = re.sub(r"^```(?:r|rscript)\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"^```\s*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)

    lines = code.strip().split("\n")
    cleaned_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() in ("r", "rscript"):
            continue
        if i == 0:
            if re.match(r"^r(script)?\s+", stripped, re.IGNORECASE):
                continue
            if re.match(r"^[$%>]\s*r(script)?", stripped, re.IGNORECASE):
                continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def extract_r_body(text: str) -> str:
    if not text:
        return ""
    match = _FENCE_R.search(text)
    if match:
        return cleanup_r_code(match.group(1))
    match = _FENCE_ANY.search(text)
    if match:
        inner = match.group(1).strip()
        if looks_like_r(inner) or not _SQL_START.match(inner):
            return cleanup_r_code(inner)
    return cleanup_r_code(text)


def wrap_sql_as_r(sql: str) -> str:
    """Wrap a validated SQL statement in a DBI/odbc tidyverse script."""
    from app.utils.sql_normalization import qualify_unqualified_objects

    body = (sql or "").strip()
    if not body:
        return ""
    if looks_like_r(body):
        return qualify_sql_in_r(cleanup_r_code(body))
    body = qualify_unqualified_objects(body)
    indented = "\n".join(f"    {line}" if line else "" for line in body.splitlines())
    return (
        "# Retrieves data using the matched SQL query, then prints a data frame.\n"
        "library(DBI)\n"
        "library(odbc)\n"
        "library(dplyr)\n"
        "\n"
        "# Replace server and database names as needed. Use Windows authentication.\n"
        "con <- dbConnect(\n"
        "  odbc::odbc(),\n"
        '  Driver = "SQL Server",\n'
        '  Server = "your_server_name",\n'
        '  Database = "your_database_name",\n'
        '  Trusted_Connection = "Yes"\n'
        ")\n"
        "tryCatch({\n"
        "  result <- dbGetQuery(con, r\"(\n"
        f"{indented}\n"
        "  )\")\n"
        "  print(result)\n"
        "}, finally = {\n"
        "  dbDisconnect(con)\n"
        "})\n"
    )


def materialize_r_code(sql_or_code: str) -> str:
    return wrap_sql_as_r(sql_or_code)


def _looks_like_sql_fragment(text: str) -> bool:
    if not text:
        return False
    return bool(_SQL_START.search(text) or _SQL_OBJECT.search(text))


def _scan_r_strings(code: str) -> List[str]:
    """Return decoded string literal contents, including R raw strings."""
    values: List[str] = []
    i = 0
    n = len(code or "")
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if ch in "rR" and nxt == '"':
            j = i + 2
            opener = code[j] if j < n and code[j] in _RAW_OPENERS else ""
            closer = _RAW_OPENERS.get(opener, '"')
            if opener:
                j += 1
            start = j
            found = False
            while j < n:
                if opener:
                    if code[j] == closer and j + 1 < n and code[j + 1] == '"':
                        values.append(code[start:j])
                        i = j + 2
                        found = True
                        break
                elif code[j] == '"':
                    values.append(code[start:j])
                    i = j + 1
                    found = True
                    break
                j += 1
            if found:
                continue
            break
        if ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < n:
                if code[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if code[j] == quote:
                    inner = code[i + 1 : j]
                    values.append(inner.replace(r"\"", '"').replace(r"\'", "'"))
                    i = j + 1
                    break
                j += 1
            else:
                break
            continue
        i += 1
    return values


def _blank_r_strings(code: str) -> str:
    """Replace string literals with empty quotes so delimiter checks ignore SQL."""
    if not code:
        return code
    chars = list(code)
    i = 0
    n = len(code)
    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""
        if ch in "rR" and nxt == '"':
            j = i + 2
            opener = chars[j] if j < n and chars[j] in _RAW_OPENERS else ""
            closer = _RAW_OPENERS.get(opener, '"')
            if opener:
                j += 1
            while j < n:
                if opener:
                    if chars[j] == closer and j + 1 < n and chars[j + 1] == '"':
                        for k in range(i, j + 2):
                            chars[k] = '"' if k in (i, j + 1) else " "
                        i = j + 2
                        break
                elif chars[j] == '"':
                    for k in range(i, j + 1):
                        chars[k] = '"' if k in (i, j) else " "
                    i = j + 1
                    break
                j += 1
            else:
                break
            continue
        if ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < n:
                if chars[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if chars[j] == quote:
                    for k in range(i + 1, j):
                        chars[k] = " "
                    i = j + 1
                    break
                j += 1
            else:
                break
            continue
        i += 1
    return "".join(chars)


def _extract_call_string_args(code: str) -> List[str]:
    sqls: List[str] = []
    seen = set()

    def _add(value: Optional[str]) -> None:
        text = (value or "").strip()
        if not text or not _looks_like_sql_fragment(text):
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        sqls.append(text)

    for value in _scan_r_strings(code or ""):
        _add(value)
    return sqls


def extract_sql_from_r(code: str) -> List[str]:
    """Return SQL strings passed to DBI/RODBC query helpers, plus SQL-shaped literals."""
    return _extract_call_string_args(code)


def _delimiter_balance(code: str) -> Tuple[bool, str]:
    stripped = _R_COMMENT.sub(" ", code or "")
    stripped = _blank_r_strings(stripped)
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: List[str] = []
    for ch in stripped:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack[-1] != ch:
                return False, f"R syntax error: unmatched '{ch}'"
            stack.pop()
    if stack:
        return False, f"R syntax error: unclosed '{stack[-1]}'"
    return True, ""


def syntax_check_r(code: str) -> tuple[bool, str]:
    if not (code or "").strip():
        return False, "Empty R code"
    return _delimiter_balance(code)


def qualify_sql_in_r(code: str, known_objects=None, default_schema: str = "dbo") -> str:
    """Schema-qualify bare table names inside embedded SQL strings."""
    if not code:
        return code
    from app.utils.sql_normalization import qualify_unqualified_objects

    result = code
    for sql in extract_sql_from_r(code):
        qualified = qualify_unqualified_objects(sql, known_objects, default_schema)
        if qualified != sql:
            result = result.replace(sql, qualified)
    return result


def structural_r_hash(code: str) -> str:
    text = extract_r_body(code)
    text = _R_COMMENT.sub(" ", text)
    sqls = extract_sql_from_r(text)
    if sqls:
        from app.utils.sql_normalization import normalize_for_hash

        text = "\n".join(normalize_for_hash(s) for s in sqls)
    else:
        text = _WHITESPACE.sub(" ", text).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
