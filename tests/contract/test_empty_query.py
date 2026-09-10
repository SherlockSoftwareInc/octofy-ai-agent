from app.models.schemas import GenerateSQLRequest


def test_empty_query_rejected():
    req = GenerateSQLRequest(query="   ")
    assert not (req.query or "").strip()
