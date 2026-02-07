"""
Tests for system query intent detection and prompt building.
"""

import pytest
from app.services.system_query_service import detect_system_query_intent


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
