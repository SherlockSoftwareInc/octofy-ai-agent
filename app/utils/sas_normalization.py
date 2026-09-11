"""SAS code extraction, SQL wrapping, and structural hashing."""

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
_FENCE_SAS = re.compile(r"```(?:sas|sasbase)\s*([\s\S]*?)```", re.IGNORECASE)
_FENCE_ANY = re.compile(r"```[a-zA-Z0-9_-]*\s*([\s\S]*?)```")
_WHITESPACE = re.compile(r"\s+")
_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
_STAR_COMMENT = re.compile(r"(?m)^\s*\*.*?;")
_CONNECTION_OPEN = re.compile(r"(?is)CONNECTION\s+TO\s+\w+\s*\(")
_EXECUTE_OPEN = re.compile(r"(?is)EXECUTE\s*\(")


def looks_like_sas(text: str) -> bool:
    if not text or not text.strip():
        return False
    stripped = text.strip()
    upper = stripped.upper()
    if upper.startswith(("PROC ", "DATA ", "LIBNAME ", "%MACRO", "%LET ")):
        return True
    markers = (
        "PROC SQL",
        "PROC PRINT",
        "PROC MEANS",
        "PROC FREQ",
        "PROC SGPLOT",
        "LIBNAME ",
        "QUIT;",
        "CONNECTION TO ",
        "DISCONNECT FROM",
    )
    return any(marker in upper for marker in markers)


def cleanup_sas_code(code: str) -> str:
    """Strip markdown fences and a leading SAS interpreter line."""
    if not code:
        return code

    code = code.strip()
    code = re.sub(r"^```(?:sas|sasbase)\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"^```\s*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)

    lines = code.strip().split("\n")
    cleaned_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() in ("sas", "sasbase"):
            continue
        if i == 0 and re.match(r"^[$%>]\s*sas", stripped, re.IGNORECASE):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def extract_sas_body(text: str) -> str:
    if not text:
        return ""
    match = _FENCE_SAS.search(text)
    if match:
        return cleanup_sas_code(match.group(1))
    match = _FENCE_ANY.search(text)
    if match:
        inner = match.group(1).strip()
        if looks_like_sas(inner) or not _SQL_START.match(inner):
            return cleanup_sas_code(inner)
    return cleanup_sas_code(text)


def wrap_sql_as_sas(sql: str) -> str:
    """Wrap a validated SQL statement in a PROC SQL pass-through script."""
    from app.utils.sql_normalization import qualify_unqualified_objects

    body = (sql or "").strip()
    if not body:
        return ""
    if looks_like_sas(body):
        return qualify_sql_in_sas(cleanup_sas_code(body))
    body = qualify_unqualified_objects(body)
    indented = "\n".join(f"        {line}" if line else "" for line in body.splitlines())
    return (
        "/* Retrieves data using the matched SQL query, then prints the result. */\n"
        "PROC SQL;\n"
        "    CONNECT TO ODBC AS dbcon\n"
        '        (NOPROMPT="Driver={SQL Server};Server=your_server_name;'
        'Database=your_database_name;Trusted_Connection=Yes;");\n'
        "    CREATE TABLE work.result AS\n"
        "    SELECT * FROM CONNECTION TO dbcon (\n"
        f"{indented}\n"
        "    );\n"
        "    DISCONNECT FROM dbcon;\n"
        "QUIT;\n"
        "\n"
        "PROC PRINT DATA=work.result;\n"
        "RUN;\n"
    )


def materialize_sas_code(sql_or_code: str) -> str:
    return wrap_sql_as_sas(sql_or_code)


def _looks_like_sql_fragment(text: str) -> bool:
    if not text:
        return False
    return bool(_SQL_START.search(text) or _SQL_OBJECT.search(text))


def _extract_balanced_paren(code: str, open_end: int) -> Optional[str]:
    depth = 1
    i = open_end
    in_str = None
    while i < len(code) and depth > 0:
        ch = code[i]
        if in_str:
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return code[open_end : i - 1]


def extract_sql_from_sas(code: str) -> List[str]:
    """Return SQL strings from CONNECTION TO / EXECUTE pass-through, plus SQL-shaped literals."""
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

    for opener in (_CONNECTION_OPEN, _EXECUTE_OPEN):
        for match in opener.finditer(code or ""):
            _add(_extract_balanced_paren(code, match.end()))

    if sqls:
        return sqls

    for match in re.finditer(r'"(?:\\.|[^"\\])*"', code or ""):
        inner = match.group(0)[1:-1]
        _add(inner)
    for match in re.finditer(r"'(?:\\.|[^'\\])*'", code or ""):
        inner = match.group(0)[1:-1]
        _add(inner)
    return sqls


def _blank_sas_comments_and_strings(code: str) -> str:
    stripped = _BLOCK_COMMENT.sub(" ", code or "")
    stripped = _STAR_COMMENT.sub(" ", stripped)
    chars = list(stripped)
    i = 0
    n = len(chars)
    while i < n:
        ch = chars[i]
        if ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < n:
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


def syntax_check_sas(code: str) -> tuple[bool, str]:
    if not (code or "").strip():
        return False, "Empty SAS code"
    stripped = _blank_sas_comments_and_strings(code)
    if stripped.count("/*") != stripped.count("*/"):
        return False, "SAS syntax error: unmatched comment"
    pairs = {"(": ")", "[": "]"}
    stack: List[str] = []
    for ch in stripped:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack[-1] != ch:
                return False, f"SAS syntax error: unmatched '{ch}'"
            stack.pop()
    if stack:
        return False, f"SAS syntax error: unclosed '{stack[-1]}'"
    return True, ""


def qualify_sql_in_sas(code: str, known_objects=None, default_schema: str = "dbo") -> str:
    """Schema-qualify bare table names inside embedded SQL pass-through."""
    if not code:
        return code
    from app.utils.sql_normalization import qualify_unqualified_objects

    result = code
    for sql in extract_sql_from_sas(code):
        qualified = qualify_unqualified_objects(sql, known_objects, default_schema)
        if qualified != sql:
            result = result.replace(sql, qualified)
    return result


def structural_sas_hash(code: str) -> str:
    text = extract_sas_body(code)
    text = _BLOCK_COMMENT.sub(" ", text)
    text = _STAR_COMMENT.sub(" ", text)
    sqls = extract_sql_from_sas(text)
    if sqls:
        from app.utils.sql_normalization import normalize_for_hash

        text = "\n".join(normalize_for_hash(s) for s in sqls)
    else:
        text = _WHITESPACE.sub(" ", text).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
