"""SQL normalization for structural hashing and fence stripping."""

import hashlib
import re

from app.utils.regexes import strip_markdown_fences

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"--.*?$", re.MULTILINE)
_STRING_LITERAL = re.compile(r"(N?'(?:''|[^'])*')", re.IGNORECASE)
_ALIAS = re.compile(r"\b(AS)\s+[A-Za-z_][\w]*", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_SQL_IDENT = r"(?:\[[^\]]+\]|[A-Za-z_][\w]*)"
_FROM_JOIN_OBJECT = re.compile(
    rf"(?is)\b(?:from|join)\s+({_SQL_IDENT}(?:\s*\.\s*{_SQL_IDENT})*)"
)
_OBJECT_CLAUSE = re.compile(
    rf"(?is)\b(from|join|into|update)\s+({_SQL_IDENT}(?:\s*\.\s*{_SQL_IDENT})*)"
)
_SKIP_SCHEMAS = {"sys", "information_schema"}


def strip_reasoning_header(sql: str) -> str:
    if not sql:
        return ""
    text = sql.strip()
    if text.startswith("/*"):
        end = text.find("*/")
        if end != -1:
            text = text[end + 2 :].strip()
    return text


def extract_sql_body(text: str) -> str:
    fenced = strip_markdown_fences(text)
    return strip_reasoning_header(fenced)


def normalize_for_hash(sql: str) -> str:
    text = extract_sql_body(sql)
    text = _COMMENT_BLOCK.sub(" ", text)
    text = _COMMENT_LINE.sub(" ", text)
    text = _STRING_LITERAL.sub("?", text)
    text = _ALIAS.sub(r"\1 _", text)
    text = _WHITESPACE.sub(" ", text).strip().lower()
    return text


def structural_sql_hash(sql: str) -> str:
    normalized = normalize_for_hash(sql)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_sql_object_refs(sql: str) -> list:
    """Return schema.object names from FROM/JOIN, including bracketed names with spaces."""
    refs = []
    seen = set()
    for match in _FROM_JOIN_OBJECT.finditer(sql or ""):
        parts = [p.strip().strip("[]") for p in re.split(r"\s*\.\s*", match.group(1)) if p.strip()]
        if not parts:
            continue
        qualified = ".".join(parts[-2:]) if len(parts) >= 2 else parts[0]
        key = qualified.lower()
        if key in seen:
            continue
        seen.add(key)
        refs.append(qualified)
    return refs


def qualify_unqualified_objects(sql: str, known_objects=None, default_schema: str = "dbo") -> str:
    """Prefix bare FROM/JOIN/INTO/UPDATE names with schema (dbo.Categories)."""
    if not sql:
        return sql
    name_to_schema = {}
    for item in known_objects or []:
        if isinstance(item, str):
            parts = [p.strip().strip("[]") for p in item.split(".") if p.strip()]
            if len(parts) >= 2:
                name_to_schema[parts[-1].lower()] = parts[-2]
            continue
        schema = getattr(item, "schema_name", None) or (item[0] if isinstance(item, (list, tuple)) and item else None)
        name = getattr(item, "object_name", None) or (item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else None)
        if name:
            name_to_schema[str(name).lower()] = str(schema or default_schema)

    def repl(match: re.Match) -> str:
        keyword, ident = match.group(1), match.group(2)
        parts = [p.strip().strip("[]") for p in re.split(r"\s*\.\s*", ident) if p.strip()]
        if not parts:
            return match.group(0)
        if len(parts) >= 2:
            return match.group(0)
        bare = parts[0]
        if bare.startswith("#") or bare.lower() in _SKIP_SCHEMAS:
            return match.group(0)
        rest = sql[match.end():]
        if keyword.lower() == "from" and re.match(r"\s+import\b", rest):
            return match.group(0)
        schema = name_to_schema.get(bare.lower(), default_schema)
        orig_ident = ident.strip()
        if orig_ident.startswith("[") and orig_ident.endswith("]"):
            qualified_name = f"{schema}.{orig_ident}"
        elif re.search(r"[^\w]", bare):
            qualified_name = f"{schema}.[{bare}]"
        else:
            qualified_name = f"{schema}.{bare}"
        return f"{keyword} {qualified_name}"

    return _OBJECT_CLAUSE.sub(repl, sql)
