from app.services.query_interceptor import QueryInterceptor


def test_blocks_drop():
    ok, reason = QueryInterceptor().check("DROP TABLE dbo.Customers")
    assert ok is False
    assert "Dangerous" in reason


def test_allows_select():
    ok, reason = QueryInterceptor().check("SELECT 1")
    assert ok is True


def test_temp_table_write_allowed():
    ok, _ = QueryInterceptor().check("CREATE TABLE #tmp (id int)")
    assert ok is True


def test_write_blocked_without_explicit_request():
    ok, reason = QueryInterceptor().check("DELETE FROM dbo.Customers")
    assert ok is False
    assert "Write" in reason


def test_write_allowed_when_requested():
    ok, _ = QueryInterceptor().check("DELETE FROM dbo.Customers", user_requested_write=True)
    assert ok is True
