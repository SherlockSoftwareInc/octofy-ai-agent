"""Ask/plan queryMode must use the Discuss pipeline, not SQL generation."""

from unittest.mock import patch

from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse
from app.services.generation_service import generate_sql_for_request


def _collect(mode: str):
    request = GenerateSQLRequest(query="what do these columns mean?", queryMode=mode, source_id="src")
    return list(generate_sql_for_request(request))


@patch("app.services.discuss_service.discuss_conversation")
def test_ask_mode_uses_discuss(mock_discuss):
    mock_discuss.return_value = GenerateSQLResponse(sql="", explanation="chat", query_type="ask")
    events = _collect("ask")
    mock_discuss.assert_called_once()
    payloads = [item["payload"] for item in events if isinstance(item, dict) and item.get("type") == "result"]
    assert payloads[0].query_type == "ask"
    assert payloads[0].sql == ""


@patch("app.services.discuss_service.discuss_conversation")
def test_plan_alias_uses_discuss(mock_discuss):
    mock_discuss.return_value = GenerateSQLResponse(sql="", explanation="chat", query_type="ask")
    _collect("plan")
    mock_discuss.assert_called_once()
