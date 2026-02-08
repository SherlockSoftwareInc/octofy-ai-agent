"""
Tests for query intent classification and system catalog prompt building.
"""

from unittest.mock import MagicMock
from app.services.system_query_service import classify_query_intent
from app.services.system_query_service import build_system_catalog_prompt


class TestClassifyQueryIntent:
    """Test suite for LLM-based classify_query_intent function"""

    def _make_llm(self, response_text: str) -> MagicMock:
        """Create a mock LLM service that returns the given text."""
        llm = MagicMock()
        llm.chat_completion.return_value = response_text
        return llm

    # --- system_metadata cases ---

    def test_list_tables(self):
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("list all tables in the database", llm) == "system_metadata"

    def test_show_columns(self):
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("show columns for the Orders table", llm) == "system_metadata"

    def test_sql_version(self):
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("what SQL Server version are we running?", llm) == "system_metadata"

    def test_how_many_tables_have_column(self):
        """The query that originally broke the regex approach"""
        llm = self._make_llm("system_metadata")
        assert classify_query_intent("How many tables have EmployeeID column", llm) == "system_metadata"

    # --- data_query cases ---

    def test_business_sales(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent("show me total sales by region", llm) == "data_query"

    def test_business_customers(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent("how many customers ordered last month?", llm) == "data_query"

    # --- off_topic cases ---

    def test_off_topic_greeting(self):
        llm = self._make_llm("off_topic")
        assert classify_query_intent("What a nice day!", llm) == "off_topic"

    def test_off_topic_general_knowledge(self):
        llm = self._make_llm("off_topic")
        assert classify_query_intent("What is the capital of France?", llm) == "off_topic"

    # --- Robustness: LLM returns unexpected text ---

    def test_strips_whitespace(self):
        llm = self._make_llm("  system_metadata  \n")
        assert classify_query_intent("list tables", llm) == "system_metadata"

    def test_defaults_to_data_query_on_garbage(self):
        """If LLM returns something unrecognized, default to data_query (safest)"""
        llm = self._make_llm("I think this is about tables")
        assert classify_query_intent("list tables", llm) == "data_query"

    def test_empty_query_returns_off_topic(self):
        """Empty or blank queries should be classified as off_topic without calling LLM"""
        llm = self._make_llm("data_query")
        assert classify_query_intent("", llm) == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_none_query_returns_off_topic(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent(None, llm) == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_whitespace_only_query_returns_off_topic(self):
        """Whitespace-only queries should be classified as off_topic without calling LLM"""
        llm = self._make_llm("data_query")
        assert classify_query_intent("   ", llm) == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_llm_returns_none_defaults_to_data_query(self):
        """If LLM returns None instead of a string, default to data_query"""
        llm = MagicMock()
        llm.chat_completion.return_value = None
        assert classify_query_intent("list all tables", llm) == "data_query"

    def test_llm_exception_defaults_to_data_query(self):
        """If LLM call fails, default to data_query to avoid blocking the user"""
        llm = MagicMock()
        llm.chat_completion.side_effect = Exception("API error")
        assert classify_query_intent("list all tables", llm) == "data_query"

    # --- Verify prompt structure ---

    def test_sends_system_and_user_message(self):
        llm = self._make_llm("data_query")
        classify_query_intent("show me sales", llm)
        llm.chat_completion.assert_called_once()
        messages = llm.chat_completion.call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "show me sales" in messages[1]["content"]

    def test_system_prompt_mentions_three_categories(self):
        llm = self._make_llm("data_query")
        classify_query_intent("test query", llm)
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        assert "data_query" in system_content
        assert "system_metadata" in system_content
        assert "off_topic" in system_content


class TestBuildSystemCatalogPrompt:
    """Test suite for build_system_catalog_prompt function (unchanged)"""

    def test_returns_string(self):
        result = build_system_catalog_prompt("list all tables")
        assert isinstance(result, str)

    def test_includes_user_query(self):
        query = "show columns for the Orders table"
        result = build_system_catalog_prompt(query)
        assert query in result

    def test_includes_sys_tables_reference(self):
        result = build_system_catalog_prompt("list tables")
        assert "sys.tables" in result

    def test_includes_sys_columns_reference(self):
        result = build_system_catalog_prompt("list columns")
        assert "sys.columns" in result

    def test_includes_information_schema_reference(self):
        result = build_system_catalog_prompt("list tables")
        assert "INFORMATION_SCHEMA" in result

    def test_includes_version_reference(self):
        result = build_system_catalog_prompt("what version")
        assert "@@VERSION" in result or "SERVERPROPERTY" in result

    def test_includes_tsql_rules(self):
        result = build_system_catalog_prompt("list tables")
        assert "T-SQL" in result

    def test_includes_no_business_data_rule(self):
        result = build_system_catalog_prompt("list tables")
        assert "business" in result.lower() or "user data" in result.lower()

    def test_with_database_info(self):
        result = build_system_catalog_prompt("list tables", database_info="Database: SalesDB")
        assert "SalesDB" in result
