from app.services.r_interceptor import RInterceptor
from app.utils.r_normalization import (
    extract_r_body,
    extract_sql_from_r,
    looks_like_r,
    syntax_check_r,
    wrap_sql_as_r,
)


def test_extract_r_from_fence():
    raw = "```r\nlibrary(DBI)\nresult <- data.frame()\n```"
    code = extract_r_body(raw)
    assert "library(DBI)" in code
    assert "```" not in code


def test_syntax_check():
    ok, err = syntax_check_r("library(DBI)\nresult <- 1\n")
    assert ok
    ok, err = syntax_check_r("library(DBI)\nresult <- (1\n")
    assert not ok
    assert "syntax" in err.lower()


def test_r_interceptor_blocks_system():
    interceptor = RInterceptor()
    ok, reason = interceptor.check('system("rm -rf /")')
    assert not ok
    ok, reason = interceptor.check(
        "library(DBI)\nlibrary(odbc)\ncon <- dbConnect(odbc::odbc(), Driver = \"SQL Server\")\n"
    )
    assert ok


def test_wrap_does_not_double_wrap_r():
    original = "library(DBI)\nresult <- data.frame()\n"
    wrapped = wrap_sql_as_r(original)
    assert wrapped.strip() == original.strip()
    assert looks_like_r(original)


def test_extract_sql_from_dbgetquery():
    code = 'result <- dbGetQuery(con, "SELECT COUNT(*) FROM dbo.Customers")'
    sqls = extract_sql_from_r(code)
    assert sqls
    assert "SELECT COUNT(*)" in sqls[0]
    assert "dbo.Customers" in sqls[0]


def test_empty_r_syntax_fails():
    ok, err = syntax_check_r("   ")
    assert not ok
    assert "empty" in err.lower()
