"""
Tests for system query branch integration in generate_sql_for_request.

Uses mocks to avoid requiring real database/LLM connections.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, AgentStatus


class TestSystemQueryBranch:
    """Test that system queries take the fast path through generate_sql_for_request"""

    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_query_skips_discovery(self, mock_skills, mock_vs, mock_llm_factory, mock_validate):
        """System queries should NOT call perform_discovery or lookup_values_for_query"""
        from app.services.generation_service import generate_sql_for_request

        # Setup mocks
        mock_skills_instance = MagicMock()
        mock_skills_instance.load_primary_data_source.return_value = MagicMock(
            name="TestDB", description="Test", keywords=[]
        )
        mock_skills.return_value = mock_skills_instance

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT name FROM sys.tables"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (True, "", [])

        request = GenerateSQLRequest(query="list all tables in the database")

        # Consume the generator
        results = list(generate_sql_for_request(request))

        # Should have status messages and a result
        statuses = [r for r in results if isinstance(r, AgentStatus)]
        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]

        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert isinstance(payload, GenerateSQLResponse)
        assert payload.discovery_branch == "system_catalog"
        assert payload.sql == "SELECT name FROM sys.tables"

    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_query_with_retry(self, mock_skills, mock_vs, mock_llm_factory, mock_validate):
        """System queries should retry once on validation failure"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills_instance = MagicMock()
        mock_skills_instance.load_primary_data_source.return_value = MagicMock(
            name="TestDB", description="Test", keywords=[]
        )
        mock_skills.return_value = mock_skills_instance

        mock_llm = MagicMock()
        # First call returns bad SQL, second returns good SQL
        mock_llm.generate_sql_with_context.side_effect = [
            "SELECT name FROM sys.nonexistent",
            "SELECT name FROM sys.tables",
        ]
        mock_llm_factory.return_value = mock_llm

        # First validation fails, second succeeds
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
        # LLM should have been called exactly 2 times
        assert mock_llm.generate_sql_with_context.call_count == 2

    @patch("app.services.generation_service.validate_sql_with_db")
    @patch("app.services.generation_service.get_llm_service")
    @patch("app.services.generation_service.get_vector_store")
    @patch("app.services.skills_service.get_skills_service")
    def test_system_query_max_retry_exhausted(self, mock_skills, mock_vs, mock_llm_factory, mock_validate):
        """After 2 failed attempts, should return error"""
        from app.services.generation_service import generate_sql_for_request

        mock_skills_instance = MagicMock()
        mock_skills_instance.load_primary_data_source.return_value = MagicMock(
            name="TestDB", description="Test", keywords=[]
        )
        mock_skills.return_value = mock_skills_instance

        mock_llm = MagicMock()
        mock_llm.generate_sql_with_context.return_value = "SELECT bad FROM sys.bad"
        mock_llm_factory.return_value = mock_llm

        mock_validate.return_value = (False, "Invalid object name 'sys.bad'", ["sys.bad"])

        request = GenerateSQLRequest(query="list all tables")
        results = list(generate_sql_for_request(request))

        result_items = [r for r in results if isinstance(r, dict) and r.get("type") == "result"]
        assert len(result_items) == 1
        payload = result_items[0]["payload"]
        assert payload.sql == ""  # Failed — no SQL
        assert "failed" in payload.explanation.lower() or "error" in payload.explanation.lower()

    def test_business_query_does_not_trigger_system_branch(self):
        """Ensure business queries are NOT routed to the system branch"""
        from app.services.system_query_service import detect_system_query_intent

        assert detect_system_query_intent("show me total sales by region") is False
        assert detect_system_query_intent("how many customers ordered last month?") is False
