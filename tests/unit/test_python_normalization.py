import pytest
from app.services.python_interceptor import PythonInterceptor
from app.utils.python_normalization import (
    extract_python_body,
    looks_like_python,
    syntax_check_python,
    wrap_sql_as_python,
)


def test_extract_python_from_fence():
    raw = "```python\nimport pandas as pd\nfinal_result_df = df\n```"
    code = extract_python_body(raw)
    assert "import pandas" in code
    assert "```" not in code


def test_syntax_check():
    ok, err = syntax_check_python("import pandas as pd\n")
    assert ok
    ok, err = syntax_check_python("def (\n")
    assert not ok
    assert "syntax" in err.lower()


def test_python_interceptor_blocks_eval():
    interceptor = PythonInterceptor()
    ok, reason = interceptor.check("eval('os.system(\"rm\")')")
    assert not ok
    ok, reason = interceptor.check(
        "import pandas as pd\nimport sqlalchemy\nengine = sqlalchemy.create_engine(DB_CONNECTION_STRING)\n"
    )
    assert ok


def test_wrap_does_not_double_wrap_python():
    original = "import pandas as pd\nfinal_result_df = pd.DataFrame()\n"
    wrapped = wrap_sql_as_python(original)
    assert wrapped.strip() == original.strip()
    assert looks_like_python(original)


def test_bind_db_connection_string_replaces_environ():
    from app.utils.python_normalization import bind_db_connection_string

    code = (
        "import os\n"
        "import sqlalchemy\n"
        "DB_CONNECTION_STRING = os.environ['DB_CONNECTION_STRING']\n"
        "engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)\n"
    )
    bound = bind_db_connection_string(code, "mssql+pyodbc://real")
    assert "os.environ" not in bound
    assert "mssql+pyodbc://real" in bound
    assert "engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)" in bound


def test_bind_db_connection_string_prepends_when_missing():
    from app.utils.python_normalization import bind_db_connection_string

    code = "engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)\n"
    bound = bind_db_connection_string(code, "mssql+pyodbc://real")
    assert bound.startswith("DB_CONNECTION_STRING = 'mssql+pyodbc://real'\n") or bound.startswith(
        'DB_CONNECTION_STRING = "mssql+pyodbc://real"\n'
    )


def test_execute_python_replaces_environ_lookup():
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("pandas")
    from app.services.execution_service import execute_python_code

    code = (
        "import os\n"
        "value = os.environ['DB_CONNECTION_STRING']\n"
        "final_result_df = pd.DataFrame({'conn': [value]})\n"
    )
    result = execute_python_code(
        code,
        {"DB_CONNECTION_STRING": "mssql+pyodbc://injected"},
        enable_profiling=False,
    )
    assert result["success"] is True, result.get("error")
    frames = [r for r in result["results"] if r.get("name") == "final_result_df"]
    assert frames
    rows = frames[0]["data"]["data"]
    assert rows[0]["conn"] == "mssql+pyodbc://injected"


def test_resolve_python_connection_uses_source_engine(monkeypatch):
    from app.services.execution_service import _connection_target_label, _resolve_python_connection_string

    def fake_url(source_id=None):
        database = "Northwind" if source_id else "WrongDB"
        return (
            "mssql+pyodbc:///?odbc_connect="
            f"Driver%3DODBC+Driver+17+for+SQL+Server%3BServer%3Dlocalhost%3BDatabase%3D{database}"
        )

    monkeypatch.setattr("app.core.database.get_source_sqlalchemy_url", fake_url)
    url = _resolve_python_connection_string("9f52c0e0-2e6d-4d6a-8b74-1f5e8d2a2c3b")
    assert "Northwind" in url
    assert "WrongDB" not in url
    assert "database=Northwind" in _connection_target_label(url)


def test_qualify_unqualified_objects_adds_dbo():
    from app.utils.sql_normalization import qualify_unqualified_objects

    sql = (
        "SELECT CategoryName FROM Categories "
        "JOIN Products ON Categories.CategoryID = Products.CategoryID"
    )
    qualified = qualify_unqualified_objects(sql)
    assert "FROM dbo.Categories" in qualified
    assert "JOIN dbo.Products" in qualified
    assert qualify_unqualified_objects("SELECT * FROM dbo.Categories") == "SELECT * FROM dbo.Categories"
    assert "FROM dbo.[Order Details]" in qualify_unqualified_objects("SELECT * FROM [Order Details]")


def test_qualify_sql_in_python_read_sql():
    from app.utils.python_normalization import qualify_sql_in_python

    code = (
        "from sqlalchemy import create_engine\n"
        "engine = create_engine(DB_CONNECTION_STRING)\n"
        "conn = engine.raw_connection()\n"
        "try:\n"
        '    df = pd.read_sql("SELECT * FROM Categories", conn)\n'
        "finally:\n"
        "    conn.close()\n"
    )
    qualified = qualify_sql_in_python(code)
    assert "FROM dbo.Categories" in qualified
    assert "from sqlalchemy import create_engine" in qualified


def test_qualify_sql_in_python_triple_quote_and_comment():
    from app.utils.python_normalization import qualify_sql_in_python

    code = '''df = pd.read_sql("""
-- category list
SELECT CategoryName FROM Categories
""", conn)
'''
    qualified = qualify_sql_in_python(code)
    assert "FROM dbo.Categories" in qualified


def test_wrap_sql_as_python_qualifies_bare_tables():
    wrapped = wrap_sql_as_python("SELECT * FROM Categories")
    assert "FROM dbo.Categories" in wrapped
    assert "import sqlalchemy" in wrapped
