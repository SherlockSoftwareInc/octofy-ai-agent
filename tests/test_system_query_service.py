"""
Tests for query intent classification and system catalog prompt building.
"""

from unittest.mock import MagicMock
from app.services.system_query_service import classify_query_intent
from app.services.system_query_service import build_system_catalog_prompt
from app.services.system_query_service import _build_classification_prompt


class TestClassifyQueryIntent:
    """Test suite for LLM-based classify_query_intent function"""

    def _make_llm(self, response_text: str) -> MagicMock:
        """Create a mock LLM service that returns the given text."""
        llm = MagicMock()
        llm.chat_completion.return_value = response_text
        return llm

    # --- system_metadata cases ---

    def test_list_tables(self):
        llm = self._make_llm('{"intent":"system_metadata","related_sources":[]}')
        assert classify_query_intent("list all tables in the database", llm)["intent"] == "system_metadata"

    def test_show_columns(self):
        llm = self._make_llm('{"intent":"system_metadata","related_sources":[]}')
        assert classify_query_intent("show columns for the Orders table", llm)["intent"] == "system_metadata"

    def test_sql_version(self):
        llm = self._make_llm('{"intent":"system_metadata","related_sources":[]}')
        assert classify_query_intent("what SQL Server version are we running?", llm)["intent"] == "system_metadata"

    def test_how_many_tables_have_column(self):
        """The query that originally broke the regex approach"""
        llm = self._make_llm('{"intent":"system_metadata","related_sources":[]}')
        assert classify_query_intent("How many tables have EmployeeID column", llm)["intent"] == "system_metadata"

    # --- data_query cases ---

    def test_business_sales(self):
        llm = self._make_llm('{"intent":"data_query","related_sources":["SalesDB"]}')
        assert classify_query_intent("show me total sales by region", llm)["intent"] == "data_query"

    def test_business_customers(self):
        llm = self._make_llm('{"intent":"data_query","related_sources":["SalesDB"]}')
        assert classify_query_intent("how many customers ordered last month?", llm)["intent"] == "data_query"

    # --- off_topic cases ---

    def test_off_topic_greeting(self):
        llm = self._make_llm('{"intent":"off_topic","related_sources":[]}')
        assert classify_query_intent("What a nice day!", llm)["intent"] == "off_topic"

    def test_off_topic_general_knowledge(self):
        llm = self._make_llm('{"intent":"off_topic","related_sources":[]}')
        assert classify_query_intent("What is the capital of France?", llm)["intent"] == "off_topic"

    # --- Robustness: LLM returns unexpected text ---

    def test_strips_whitespace(self):
        llm = self._make_llm("  system_metadata  \n")
        assert classify_query_intent("list tables", llm)["intent"] == "system_metadata"

    def test_defaults_to_data_query_on_garbage(self):
        """If LLM returns something unrecognized, default to data_query (safest)"""
        llm = self._make_llm("I think this is about tables")
        assert classify_query_intent("list tables", llm)["intent"] == "data_query"

    def test_empty_query_returns_off_topic(self):
        """Empty or blank queries should be classified as off_topic without calling LLM"""
        llm = self._make_llm("data_query")
        assert classify_query_intent("", llm)["intent"] == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_none_query_returns_off_topic(self):
        llm = self._make_llm("data_query")
        assert classify_query_intent(None, llm)["intent"] == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_whitespace_only_query_returns_off_topic(self):
        """Whitespace-only queries should be classified as off_topic without calling LLM"""
        llm = self._make_llm("data_query")
        assert classify_query_intent("   ", llm)["intent"] == "off_topic"
        llm.chat_completion.assert_not_called()

    def test_llm_returns_none_defaults_to_data_query(self):
        """If LLM returns None instead of a string, default to data_query"""
        llm = MagicMock()
        llm.chat_completion.return_value = None
        assert classify_query_intent("list all tables", llm)["intent"] == "data_query"

    def test_llm_exception_defaults_to_data_query(self):
        """If LLM call fails, default to data_query to avoid blocking the user"""
        llm = MagicMock()
        llm.chat_completion.side_effect = Exception("API error")
        assert classify_query_intent("list all tables", llm)["intent"] == "data_query"

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

    # --- Database context integration ---

    def test_db_context_included_in_prompt(self):
        """When db context is provided, the prompt should mention the database name and keywords"""
        llm = self._make_llm("data_query")
        classify_query_intent(
            "show me patient records", llm,
            db_name="Northwind Database",
            db_description="Sales database for imported and exported specialty foods",
            db_keywords=["sales", "customers", "orders", "products"],
        )
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        assert "Northwind Database" in system_content
        assert "specialty foods" in system_content
        assert "sales" in system_content
        assert "customers" in system_content

    def test_no_db_context_still_works(self):
        """Without db context, the prompt should still contain the base categories"""
        llm = self._make_llm("data_query")
        classify_query_intent("show me sales", llm)
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        # Should NOT contain db context template markers
        assert "This database is:" not in system_content
        assert "It contains data about:" not in system_content
        # Should still contain the base classification categories
        assert "data_query" in system_content

    def test_db_context_with_empty_keywords(self):
        """When keywords list is empty, should use 'various topics' fallback"""
        llm = self._make_llm("data_query")
        classify_query_intent(
            "show me sales", llm,
            db_name="TestDB",
            db_description="A test database",
            db_keywords=[],
        )
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        assert "various topics" in system_content

    def test_db_context_without_name_is_ignored(self):
        """If db_name is None but description is provided, context should be skipped"""
        llm = self._make_llm("data_query")
        classify_query_intent(
            "show me sales", llm,
            db_name=None,
            db_description="A test database",
            db_keywords=["sales"],
        )
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        assert "This database is:" not in system_content

    def test_db_context_without_description_is_ignored(self):
        """If db_description is None but name is provided, context should be skipped"""
        llm = self._make_llm("data_query")
        classify_query_intent(
            "show me sales", llm,
            db_name="TestDB",
            db_description=None,
            db_keywords=["sales"],
        )
        messages = llm.chat_completion.call_args[0][0]
        system_content = messages[0]["content"]
        assert "This database is:" not in system_content

    def test_related_sources_parsing(self):
        llm = self._make_llm('{"intent":"data_query","related_sources":["SalesDB","Unknown"]}')
        result = classify_query_intent(
            "show me sales", llm,
            data_sources=[
                {"name": "SalesDB", "description": "Sales data", "keywords": ["sales"]},
                {"name": "HRDB", "description": "HR data", "keywords": ["employees"]},
            ],
        )
        assert result["intent"] == "data_query"
        assert result["related_sources"] == ["SalesDB"]


class TestBuildClassificationPrompt:
    """Test suite for _build_classification_prompt helper"""

    def test_base_prompt_without_context(self):
        """Without db context, returns base prompt + reply instruction"""
        prompt = _build_classification_prompt()
        assert "data_query" in prompt
        assert "system_metadata" in prompt
        assert "off_topic" in prompt
        assert "Reply with a compact JSON object" in prompt
        assert "This database is:" not in prompt

    def test_with_full_context(self):
        """With full db context, includes database name, description, and keywords"""
        prompt = _build_classification_prompt(
            db_name="Northwind Database",
            db_description="Sales database for specialty foods",
            db_keywords=["sales", "customers", "orders"],
        )
        assert "Northwind Database" in prompt
        assert "specialty foods" in prompt
        assert "sales, customers, orders" in prompt
        assert "does NOT relate to these topics" in prompt

    def test_empty_keywords_fallback(self):
        """Empty keywords list produces 'various topics' fallback"""
        prompt = _build_classification_prompt(
            db_name="TestDB",
            db_description="Test database",
            db_keywords=[],
        )
        assert "various topics" in prompt

    def test_none_keywords_fallback(self):
        """None keywords produces 'various topics' fallback"""
        prompt = _build_classification_prompt(
            db_name="TestDB",
            db_description="Test database",
            db_keywords=None,
        )
        assert "various topics" in prompt

    def test_missing_name_skips_context(self):
        """Without db_name, db context block is not included"""
        prompt = _build_classification_prompt(
            db_name=None,
            db_description="Test database",
            db_keywords=["sales"],
        )
        assert "This database is:" not in prompt

    def test_missing_description_skips_context(self):
        """Without db_description, db context block is not included"""
        prompt = _build_classification_prompt(
            db_name="TestDB",
            db_description=None,
            db_keywords=["sales"],
        )
        assert "This database is:" not in prompt

    def test_always_ends_with_reply_instruction(self):
        """Prompt always ends with the reply instruction regardless of context"""
        prompt_no_ctx = _build_classification_prompt()
        prompt_with_ctx = _build_classification_prompt(
            db_name="DB", db_description="Desc", db_keywords=["k"]
        )
        assert prompt_no_ctx.rstrip().endswith("Do NOT include any other text.")
        assert prompt_with_ctx.rstrip().endswith("Do NOT include any other text.")

    def test_multi_source_context_in_prompt(self):
        prompt = _build_classification_prompt(
            data_sources=[
                {"name": "SalesDB", "description": "Sales data", "keywords": ["sales", "orders"]},
                {"name": "HRDB", "description": "HR data", "keywords": ["employees"]},
            ]
        )
        assert "Available data sources" in prompt
        assert "SalesDB" in prompt
        assert "HRDB" in prompt


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
