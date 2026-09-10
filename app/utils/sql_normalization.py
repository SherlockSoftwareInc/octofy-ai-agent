"""SQL normalization for structural hashing and fence stripping."""

import hashlib
import re

from app.utils.regexes import strip_markdown_fences

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"--.*?$", re.MULTILINE)
_STRING_LITERAL = re.compile(r"(N?'(?:''|[^'])*')", re.IGNORECASE)
_ALIAS = re.compile(r"\b(AS)\s+[A-Za-z_][\w]*", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


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
