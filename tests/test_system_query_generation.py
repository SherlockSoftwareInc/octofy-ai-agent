"""
Tests for 3-way intent classification integration in generate_sql_for_request.

Uses mocks to avoid requiring real database/LLM connections.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus


def _make_skills_mock():
    """Create a standard mock for skills_service."""
    mock_skills_instance = MagicMock()
    mock_skills_instance.load_primary_data_source.return_value = MagicMock(
        name="TestDB", description="Test database", keywords=[]
    )
    return mock_skills_instance


class TestIntentClassificationRouting:
    """Test that 3-way classification routes queries correctly"""

    @patch("app.services.generation_service.classify_query_intent", return_value="system_metadata")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_metadata_skips_discovery(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """system_metadata queries bypass discovery and use catalog prompt"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT name FROM sys.tables"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (True, "", [])

        request = GenerateSQLRequest(query="list all tables in the database")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert isinstance(payload, GenerateSQLResponse)
        assert payload.discovery_branch == "system_catalog"
        assert payload.sql == "SELECT name FROM sys.tables"

    @patch("app.services.generation_service.classify_query_intent", return_value="system_metadata")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_metadata_with_retry(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """System metadata queries should retry once on validation failure"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.side_effect = [
            "SELECT name FROM sys.nonexistent",
            "SELECT name FROM sys.tables",
        ]
        mock_llm_factory.return_value = mock_llm

        mock_validate.side_effect = [
            (False, "Invalid object name 'sys.nonexistent'", ["sys.nonexistent"]),
            (True, "", []),
        ]

        request = GenerateSQLRequest(query="list all tables")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert payload.sql == "SELECT name FROM sys.tables"
        assert mock_llm.generate_sql_with_context.call_count == 2

    @patch("app.services.generation_service.classify_query_intent", return_value="system_metadata")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_metadata_max_retry_exhausted(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """After 2 failed attempts, should return error explanation"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT bad FROM sys.bad"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (False, "Invalid object name 'sys.bad'", ["sys.bad"])

        request = GenerateSQLRequest(query="list all tables")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert payload.sql == ""
        assert "failed" in payload.explanation.lower() or "error" in payload.explanation.lower()

    @patch("app.services.generation_service.classify_query_intent", return_value="off_topic")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_off_topic_returns_general_response(self, mock_skills, mock_vs, mock_llm_factory, mock_classify):
        """off_topic queries should return a general (non-SQL) response"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = "That sounds lovely! How can I help you with the database?"
        mock_llm_factory.return_value = mock_llm

        request = GenerateSQLRequest(query="What a nice day!")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert isinstance(payload, GenerateSQLResponse)
        assert payload.query_type == "general"
        assert payload.sql == ""

    @patch("app.services.generation_service.classify_query_intent", return_value="data_query")
    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_data_query_continues_to_discovery(self, mock_skills, mock_vs, mock_llm_factory, mock_validate, mock_classify):
        """data_query should proceed past classification into discovery (Stage 2+)"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills.return_value = _make_skills_mock()

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        request = GenerateSQLRequest(query="show me total sales by region")

        # We just need to verify it gets past classification.
        # It will fail later in discovery (no real vector store), but that's fine —
        # we only care that it did NOT take the system_metadata or off_topic branch.
        results = []
        try:
            for item in generate_sql_for_request(request):
                results.append(item)
        except Exception:
            pass  # Expected — discovery pipeline needs real services

        # Verify classification was called and we got past it
        mock_classify.assert_called_once()

        # Should have yielded status messages about analysis (not system metadata or off-topic)
        statuses = [r for r in results if isinstance(r, AgentStatus)]
        status_messages = [s.message for s in statuses]
        # Should NOT contain system metadata messages
        assert not any("System metadata" in m for m in status_messages)
        assert not any("off-topic" in m.lower() for m in status_messages)

    def test_forceGeneral_still_skips_classification(self):
        """When forceGeneral is set, should skip LLM classification entirely"""
        from app.services.generation_service import generate_sql_for_request

        with patch("app.services.generation_service.get_llm_service") as mock_llm_factory, \
             patch("app.services.generation_service.get_vector_store"), \
             patch("app.services.skills_service.get_skills_service") as mock_skills, \
             patch("app.services.generation_service.classify_query_intent") as mock_classify:

            mock_skills.return_value = _make_skills_mock()

            mock_llm = MagicMock()
            mock_llm.chat_completion.return_value = "General answer here"
            mock_llm_factory.return_value = mock_llm

            request = GenerateSQLRequest(query="What is a LEFT JOIN?", forceGeneral=True)
            results = list(generate_sql_for_request(request))

            # classify_query_intent should NOT have been called
            mock_classify.assert_not_called()

            result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
            assert len(result_items) == 1
            payload = result_items[0]["payload"]
            assert payload.query_type == "general"
