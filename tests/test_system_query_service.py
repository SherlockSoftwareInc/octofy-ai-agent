"""
Tests for system query intent detection and prompt building.
"""

import pytest
from app.services.system_query_service import detect_system_query_intent
from app.services.system_query_service import build_system_catalog_prompt


class TestDetectSystemQueryIntent:
    """Test suite for detect_system_query_intent function"""

    # --- Positive cases: should detect as system query ---

    def test_list_tables(self):
        assert detect_system_query_intent("list all tables in the database") is True

    def test_show_tables(self):
        assert detect_system_query_intent("show me the tables") is True

    def test_what_tables(self):
        assert detect_system_query_intent("what tables are available?") is True

    def test_list_columns(self):
        assert detect_system_query_intent("list the columns in the Orders table") is True

    def test_column_info(self):
        assert detect_system_query_intent("give me column info for Products") is True

    def test_table_structure(self):
        assert detect_system_query_intent("show me the table structure of Customers") is True

    def test_sql_version(self):
        assert detect_system_query_intent("what SQL Server version are we running?") is True

    def test_database_size(self):
        assert detect_system_query_intent("what is the database size?") is True

    def test_list_databases(self):
        assert detect_system_query_intent("list all databases on this server") is True

    def test_show_schemas(self):
        assert detect_system_query_intent("show all schemas in the database") is True

    def test_list_views(self):
        assert detect_system_query_intent("list all views") is True

    def test_show_indexes(self):
        assert detect_system_query_intent("show indexes on the Orders table") is True

    def test_table_row_counts(self):
        assert detect_system_query_intent("show row counts for all tables") is True

    def test_list_stored_procedures(self):
        assert detect_system_query_intent("list stored procedures") is True

    def test_describe_table(self):
        assert detect_system_query_intent("describe the Employees table") is True

    def test_case_insensitive(self):
        assert detect_system_query_intent("LIST ALL TABLES") is True

    # --- Negative cases: should NOT detect as system query ---

    def test_business_query_sales(self):
        assert detect_system_query_intent("show me total sales by region") is False

    def test_business_query_customers(self):
        assert detect_system_query_intent("how many customers ordered last month?") is False

    def test_business_query_join(self):
        assert detect_system_query_intent("compare revenue across product categories") is False

    def test_business_query_with_table_word(self):
        """'table' in a business context should not trigger system intent"""
        assert detect_system_query_intent("show me the sales figures from the quarterly report table") is False

    def test_general_question(self):
        assert detect_system_query_intent("what is a LEFT JOIN?") is False

    def test_empty_query(self):
        assert detect_system_query_intent("") is False


class TestBuildSystemCatalogPrompt:
    """Test suite for build_system_catalog_prompt function"""

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
        """Prompt should instruct LLM to avoid business schemas"""
        result = build_system_catalog_prompt("list tables")
        assert "business" in result.lower() or "user data" in result.lower()

    def test_with_database_info(self):
        result = build_system_catalog_prompt("list tables", database_info="Database: SalesDB")
        assert "SalesDB" in result


class TestDetectSystemQueryIntentEdgeCases:
    """Edge cases and boundary conditions for system intent detection"""

    def test_mixed_case_keywords(self):
        assert detect_system_query_intent("List All Tables") is True

    def test_extra_whitespace(self):
        assert detect_system_query_intent("  list   tables  ") is True

    def test_conversational_phrasing(self):
        assert detect_system_query_intent("can you show me what tables exist?") is True

    def test_specific_table_columns(self):
        assert detect_system_query_intent("what are the columns in dbo.Orders?") is True

    def test_version_question(self):
        assert detect_system_query_intent("what version of SQL Server is this?") is True

    def test_ambiguous_but_system(self):
        """'describe table' is a system operation even without specifying 'system'"""
        assert detect_system_query_intent("describe the Employees table") is True

    def test_business_with_table_mention(self):
        """Business queries mentioning tables should not trigger system path"""
        assert detect_system_query_intent("show me total revenue from the sales table") is False

    def test_business_aggregation(self):
        assert detect_system_query_intent("list the top 10 customers by revenue") is False

    def test_system_query_with_count_tables(self):
        """Asking how many tables exist is a system query"""
        assert detect_system_query_intent("how many tables are in the database?") is True

    def test_none_input(self):
        """Should handle None gracefully by returning False"""
        assert detect_system_query_intent(None) is False
