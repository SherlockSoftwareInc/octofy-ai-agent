"""Python code extraction, SQL wrapping, and structural hashing."""

from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
from typing import List, Optional

_SQL_START = re.compile(
    r"^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|MERGE)\b",
    re.IGNORECASE,
)
_SQL_OBJECT = re.compile(
    r"(?is)\b(from|join|into|update)\s+(?:\[[^\]]+\]|[A-Za-z_][\w]*)"
)
_FENCE_PYTHON = re.compile(r"```(?:python|py)\s*([\s\S]*?)```", re.IGNORECASE)
_FENCE_ANY = re.compile(r"```[a-zA-Z0-9_-]*\s*([\s\S]*?)```")
_TRIPLE_SQL = re.compile(
    r"""(?:pd\.read_sql(?:_query)?\s*\(\s*)?(?:[fFrR]?'''([\s\S]*?)'''|[fFrR]?\"\"\"([\s\S]*?)\"\"\")""",
)
_WHITESPACE = re.compile(r"\s+")
_PYTHON_COMMENT = re.compile(r"#.*?$", re.MULTILINE)


def looks_like_python(text: str) -> bool:
    if not text or not text.strip():
        return False
    stripped = text.strip()
    if stripped.startswith(("import ", "from ", "def ", "class ")):
        return True
    markers = (
        "pd.read_sql",
        "final_result_df",
        "sqlalchemy.create_engine",
        "import pandas",
        "import sqlalchemy",
        "engine.raw_connection",
    )
    return any(marker in stripped for marker in markers)


def cleanup_python_code(code: str) -> str:
    """Strip markdown fences, shell prefixes, and unbalanced docstring wrappers."""
    if not code:
        return code

    code = code.strip()
    code = re.sub(r"^```python\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"^```\s*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)
    code = re.sub(r"^'''python\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\n?'''$", "", code)
    code = re.sub(r'^"""python\s*\n?', "", code, flags=re.IGNORECASE)
    code = re.sub(r'\n?"""$', "", code)

    lines = code.strip().split("\n")
    cleaned_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() in ("python", "python3"):
            continue
        if i == 0:
            if re.match(r'^python[3]?\s+(-[a-z]+\s+)?["\']?', stripped, re.IGNORECASE):
                continue
            if re.match(r"^[$%>]\s*python", stripped, re.IGNORECASE):
                continue
        cleaned_lines.append(line)
    code = "\n".join(cleaned_lines).strip()

    double_count = len(re.findall(r'"""', code))
    if double_count % 2 == 1:
        first_match = re.search(r'^"""', code)
        if first_match:
            docstring_end = re.search(
                r'^""".*?(?=\n(?:import|from|def|class|#|\w+\s*=))',
                code,
                re.DOTALL,
            )
            if docstring_end:
                code = code[docstring_end.end() :].strip()
            else:
                code = re.sub(r'^"""\s*', "", code)

    single_count = len(re.findall(r"'''", code))
    if single_count % 2 == 1:
        first_match = re.search(r"^'''", code)
        if first_match:
            docstring_end = re.search(
                r"^'''.*?(?=\n(?:import|from|def|class|#|\w+\s*=))",
                code,
                re.DOTALL,
            )
            if docstring_end:
                code = code[docstring_end.end() :].strip()
            else:
                code = re.sub(r"^'''\s*", "", code)

    return code


def extract_python_body(text: str) -> str:
    if not text:
        return ""
    match = _FENCE_PYTHON.search(text)
    if match:
        return cleanup_python_code(match.group(1))
    match = _FENCE_ANY.search(text)
    if match:
        inner = match.group(1).strip()
        if looks_like_python(inner) or not _SQL_START.match(inner):
            return cleanup_python_code(inner)
    return cleanup_python_code(text)


def wrap_sql_as_python(sql: str) -> str:
    """Wrap a validated SQL statement in the pandas/sqlalchemy execution pattern."""
    from app.utils.sql_normalization import qualify_unqualified_objects

    body = (sql or "").strip()
    if not body:
        return ""
    if looks_like_python(body):
        return qualify_sql_in_python(cleanup_python_code(body))
    body = qualify_unqualified_objects(body)
    fence = "'''" if '"""' in body else '"""'
    indented = "\n".join(f"        {line}" if line else "" for line in body.splitlines())
    return (
        "# Retrieves data using the matched SQL query, then returns a pandas DataFrame.\n"
        "import pandas as pd\n"
        "import sqlalchemy\n"
        "\n"
        "# DB_CONNECTION_STRING is injected at runtime.\n"
        "# DB_CONNECTION_STRING = ("
        '"mssql+pyodbc://@your_server_name/your_database_name'
        '?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes")\n'
        "engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)\n"
        "conn = engine.raw_connection()\n"
        "try:\n"
        "    final_result_df = pd.read_sql(\n"
        f"        {fence}\n"
        f"{indented}\n"
        f"        {fence},\n"
        "        conn,\n"
        "    )\n"
        "finally:\n"
        "    conn.close()\n"
    )


def materialize_python_code(sql_or_code: str) -> str:
    return wrap_sql_as_python(sql_or_code)


def _const_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                return None
        return "".join(parts)
    return None


def extract_sql_from_python(code: str) -> List[str]:
    """Return SQL strings passed to pandas read_sql helpers, plus SQL-shaped literals."""
    sqls: List[str] = []
    seen = set()

    def _add(value: Optional[str]) -> None:
        text = (value or "").strip()
        if not text or not (_SQL_START.search(text) or _SQL_OBJECT.search(text)):
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        sqls.append(text)

    try:
        tree = ast.parse(code or "")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ""
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
            elif isinstance(node.func, ast.Name):
                name = node.func.id
            if name not in {"read_sql", "read_sql_query"}:
                continue
            if node.args:
                _add(_const_str(node.args[0]))
            for kw in node.keywords or []:
                if kw.arg in {"sql", "sql_query"}:
                    _add(_const_str(kw.value))
        if sqls:
            return sqls
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                _add(node.value)
    except SyntaxError:
        for match in _TRIPLE_SQL.finditer(code or ""):
            _add(match.group(1) or match.group(2))
    return sqls


def syntax_check_python(code: str) -> tuple[bool, str]:
    try:
        compile(code or "", "<generated>", "exec")
        return True, ""
    except SyntaxError as exc:
        return False, f"Python syntax error: {exc.msg} (line {exc.lineno})"
    except Exception as exc:
        return False, f"Python compile error: {exc}"


_ENV_CONN_BRACKET = re.compile(
    r"""os\.environ\s*\[\s*['"]DB_CONNECTION_STRING['"]\s*\]"""
)
_ENV_CONN_GET = re.compile(
    r"""os\.environ\.get\(\s*['"]DB_CONNECTION_STRING['"]\s*(?:,\s*[^)]*)?\)"""
)
_ENV_CONN_GETENV = re.compile(
    r"""os\.getenv\(\s*['"]DB_CONNECTION_STRING['"]\s*(?:,\s*[^)]*)?\)"""
)
_CONN_ASSIGN = re.compile(r"^(\s*)DB_CONNECTION_STRING\s*=.*$", re.MULTILINE)


def bind_db_connection_string(code: str, conn_str: str) -> str:
    """Replace env-var lookups and bind the real connection string in the source."""
    if not code:
        return code
    bound = _ENV_CONN_BRACKET.sub("DB_CONNECTION_STRING", code)
    bound = _ENV_CONN_GET.sub("DB_CONNECTION_STRING", bound)
    bound = _ENV_CONN_GETENV.sub("DB_CONNECTION_STRING", bound)
    assignment = f"DB_CONNECTION_STRING = {repr(conn_str)}"
    if _CONN_ASSIGN.search(bound):
        bound = _CONN_ASSIGN.sub(lambda m: f"{m.group(1)}{assignment}", bound, count=1)
    else:
        bound = assignment + "\n" + bound
    return bound


def _looks_like_sql_fragment(text: str) -> bool:
    if not text:
        return False
    return bool(_SQL_START.search(text) or _SQL_OBJECT.search(text))


def _rebuild_string_token(token_str: str, new_value: str) -> str:
    """Rebuild a STRING token using the same prefix and quote style when possible."""
    prefix = ""
    i = 0
    while i < len(token_str) and token_str[i] in "rRuUfFbB":
        prefix += token_str[i]
        i += 1
    rest = token_str[i:]
    if rest.startswith("'''"):
        quote = "'''" if "'''" not in new_value else '"""'
        return prefix + quote + new_value + quote
    if rest.startswith('"""'):
        quote = '"""' if '"""' not in new_value else "'''"
        return prefix + quote + new_value + quote
    if rest.startswith("'"):
        if "'" in new_value:
            return prefix + '"' + new_value.replace('"', '\\"') + '"'
        return prefix + "'" + new_value + "'"
    if rest.startswith('"'):
        if '"' in new_value:
            return prefix + "'" + new_value.replace("'", "\\'") + "'"
        return prefix + '"' + new_value + '"'
    return token_str


def qualify_sql_in_python(code: str, known_objects=None, default_schema: str = "dbo") -> str:
    """Schema-qualify bare table names inside embedded SQL strings."""
    if not code:
        return code
    from app.utils.sql_normalization import qualify_unqualified_objects

    def _qualify_text(text: str) -> str:
        if not _looks_like_sql_fragment(text):
            return text
        return qualify_unqualified_objects(text, known_objects, default_schema)

    result = code
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        tokens = []

    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    for tok in tokens:
        if tok.type == tokenize.STRING:
            try:
                value = ast.literal_eval(tok.string)
            except Exception:
                continue
            if not isinstance(value, str):
                continue
            qualified = _qualify_text(value)
            if qualified == value:
                continue
            result = result.replace(tok.string, _rebuild_string_token(tok.string, qualified), 1)
        elif fstring_middle is not None and tok.type == fstring_middle:
            qualified = _qualify_text(tok.string)
            if qualified != tok.string:
                result = result.replace(tok.string, qualified, 1)

    if result != code:
        return result

    for sql in extract_sql_from_python(code):
        qualified = _qualify_text(sql)
        if qualified != sql:
            result = result.replace(sql, qualified)
    return result


def structural_python_hash(code: str) -> str:
    text = extract_python_body(code)
    text = _PYTHON_COMMENT.sub(" ", text)
    sqls = extract_sql_from_python(text)
    if sqls:
        from app.utils.sql_normalization import normalize_for_hash

        text = "\n".join(normalize_for_hash(s) for s in sqls)
    else:
        text = _WHITESPACE.sub(" ", text).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
