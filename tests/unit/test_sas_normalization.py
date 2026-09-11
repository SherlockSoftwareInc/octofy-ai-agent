from app.services.sas_interceptor import SASInterceptor
from app.utils.sas_normalization import (
    extract_sas_body,
    extract_sql_from_sas,
    looks_like_sas,
    syntax_check_sas,
    wrap_sql_as_sas,
)


def test_extract_sas_from_fence():
    raw = "```sas\nPROC SQL;\nQUIT;\n```"
    code = extract_sas_body(raw)
    assert "PROC SQL" in code
    assert "```" not in code


def test_syntax_check():
    ok, err = syntax_check_sas("PROC SQL;\nQUIT;\n")
    assert ok
    ok, err = syntax_check_sas("PROC SQL;\nSELECT (1\n")
    assert not ok
    assert "syntax" in err.lower()


def test_sas_interceptor_blocks_x_command():
    interceptor = SASInterceptor()
    ok, reason = interceptor.check("X 'rm -rf /';")
    assert not ok
    ok, reason = interceptor.check("PROC SQL;\nQUIT;\n")
    assert ok


def test_wrap_does_not_double_wrap_sas():
    original = "PROC SQL;\nQUIT;\n"
    wrapped = wrap_sql_as_sas(original)
    assert wrapped.strip() == original.strip()
    assert looks_like_sas(original)


def test_extract_sql_from_connection_to():
    code = (
        "PROC SQL;\n"
        "    CREATE TABLE work.result AS\n"
        "    SELECT * FROM CONNECTION TO dbcon (\n"
        "        SELECT COUNT(*) FROM dbo.Customers\n"
        "    );\n"
        "QUIT;\n"
    )
    sqls = extract_sql_from_sas(code)
    assert sqls
    assert "SELECT COUNT(*)" in sqls[0]
    assert "dbo.Customers" in sqls[0]


def test_empty_sas_syntax_fails():
    ok, err = syntax_check_sas("   ")
    assert not ok
    assert "empty" in err.lower()
