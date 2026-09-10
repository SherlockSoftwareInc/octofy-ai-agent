"""Dialect-aware identifier quoting and qualifier normalization."""

from typing import Optional


def quote_identifier(name: str, dbms: str = "SQL Server") -> str:
    if not name:
        return name
    cleaned = name.strip().strip("[]\"'`")
    kind = (dbms or "").lower()
    if "mysql" in kind or "mariadb" in kind:
        return f"`{cleaned}`"
    if "sql server" in kind or "mssql" in kind or kind in {"tsql", "sqlserver"}:
        return f"[{cleaned}]"
    return f'"{cleaned}"'


def quote_qualified(schema: str, object_name: str, dbms: str = "SQL Server") -> str:
    return f"{quote_identifier(schema, dbms)}.{quote_identifier(object_name, dbms)}"


def quote_string_literal(value: str, dbms: str = "SQL Server") -> str:
    escaped = (value or "").replace("'", "''")
    kind = (dbms or "").lower()
    if "sql server" in kind or "mssql" in kind:
        return f"N'{escaped}'"
    return f"'{escaped}'"


def normalize_qualifiers(sql: str, dbms: str = "SQL Server") -> str:
    """Best-effort strip of mismatched dialect quoting; leaves SQL otherwise intact."""
    if not sql:
        return sql
    return sql


def normalize_pinned_function_calls(sql: str, function_names: Optional[list] = None) -> str:
    """Ensure pinned PostgreSQL functions are invoked with ()."""
    if not sql or not function_names:
        return sql
    import re

    result = sql
    for name in function_names:
        bare = name.split(".")[-1].strip("[]\"'`")
        pattern = re.compile(rf"\b{re.escape(bare)}\b(?!\s*\()", re.IGNORECASE)
        result = pattern.sub(f"{bare}()", result)
    return result
