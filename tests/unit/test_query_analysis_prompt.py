"""Phase-1 query-analysis prompt: row limits are cardinality, columns are never inferred."""

from app.core.orchestrator.discovery_engine import DiscoveryEngine


class RecordingLlm:
    def __init__(self):
        self.messages = []

    def complete_json(self, messages, **kwargs):
        self.messages.append(messages)
        return {
            "keywords": ["product"],
            "complexity": "simple",
            "entities": ["product"],
            "date_ranges": [],
            "filter_values": [],
            "extracted_columns": [],
        }


def _analysis_system_prompt() -> str:
    llm = RecordingLlm()
    DiscoveryEngine(None, llm).analyze_query("find top 20 selling products", None)
    assert llm.messages
    return llm.messages[0][0]["content"]


def test_analysis_prompt_calls_row_limits_cardinality_not_predicates():
    prompt = _analysis_system_prompt()
    assert "cardinality limit, not a filter value" in prompt
    for phrasing in ('"top 10"', '"first 5"', '"bottom 3"', '"last 20"'):
        assert phrasing in prompt


def test_analysis_prompt_forbids_inferring_extracted_columns():
    prompt = _analysis_system_prompt()
    assert "leave the array empty" in prompt
    assert "top selling products" in prompt
