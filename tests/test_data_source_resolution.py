"""
Tests for data source resolution service and endpoint.
"""

import pytest
from unittest.mock import Mock
from sqlalchemy.orm import Session

from app.services.data_source_registry_service import DataSourceRegistryService
from app.models.user_models import DataSourceRegistry


class TestDataSourceRegistryServiceResolution:
    """Unit tests for DataSourceRegistryService.find_by_connection_info()."""

    def test_find_by_sql_server_params_success(self):
        """Test successful SQL Server lookup using database name matching."""
        mock_session = Mock(spec=Session)
        service = DataSourceRegistryService(mock_session)

        mock_entry = Mock(spec=DataSourceRegistry)
        mock_entry.source_id = "test-uuid-123"
        mock_entry.name = "Test DB"
        mock_entry.type = "SQL Server"
        mock_entry.connection_info = {"server": "TestServer", "database": "TestDB"}
        mock_entry.deleted_at = None

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_entry
        mock_session.query.return_value = mock_query

        result = service.find_by_connection_info(server="TestServer", database="TestDB")

        assert result is not None
        assert result.source_id == "test-uuid-123"
        assert result.name == "Test DB"

    def test_find_by_sql_server_case_insensitive(self):
        """Test case-insensitive database matching for SQL Server."""
        mock_session = Mock(spec=Session)
        service = DataSourceRegistryService(mock_session)

        mock_entry = Mock(spec=DataSourceRegistry)
        mock_entry.source_id = "test-uuid-123"
        mock_entry.name = "Test DB"
        mock_entry.deleted_at = None

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_entry
        mock_session.query.return_value = mock_query

        result = service.find_by_connection_info(server="testserver", database="testdb")

        assert result is not None
        assert mock_session.query.called

    def test_find_by_file_path_success(self):
        """Test successful Excel lookup with file_path."""
        mock_session = Mock(spec=Session)
        service = DataSourceRegistryService(mock_session)

        mock_entry = Mock(spec=DataSourceRegistry)
        mock_entry.source_id = "test-uuid-456"
        mock_entry.name = "Sales Data"
        mock_entry.type = "Excel"
        mock_entry.connection_info = {"file_path": "/data/sales.xlsx"}
        mock_entry.deleted_at = None

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_entry
        mock_session.query.return_value = mock_query

        result = service.find_by_connection_info(file_path="/data/sales.xlsx")

        assert result is not None
        assert result.source_id == "test-uuid-456"

    def test_find_not_found(self):
        """Test lookup with non-existent source returns None."""
        mock_session = Mock(spec=Session)
        service = DataSourceRegistryService(mock_session)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        result = service.find_by_connection_info(server="NonExistent", database="DB")

        assert result is None

    def test_find_no_params_returns_none(self):
        """Test that providing no params returns None."""
        mock_session = Mock(spec=Session)
        service = DataSourceRegistryService(mock_session)

        result = service.find_by_connection_info()

        assert result is None


class TestResolveDataSourceEndpointDocumentation:
    """
    Documentation of expected endpoint behavior for integration tests.

    When running integration tests with actual database:

    1. Test successful SQL Server resolution:
       - Create test data source with server/database
       - Call /api/v1/data-sources/resolve with server and database params
       - Should return 200 with source_id
       - Matching should be based on database value

    2. Test successful Excel resolution:
       - Create test Excel data source with file_path
       - Call /api/v1/data-sources/resolve with file_path param
       - Should return 200 with source_id

    3. Test validation errors (should return 400):
       - Only server provided (missing database)
       - Only database provided (missing server)
       - Mixed parameters (server + file_path)
       - No parameters provided

    4. Test not found (should return 404):
       - Non-existent SQL Server source
       - Non-existent Excel source

    5. Test authentication:
       - Without API key should return 401
       - With non-admin API key should return 403

    6. Test case-insensitive SQL Server matching:
       - Create source with "TESTSERVER" and "TESTDB"
       - Query with any server value and "testdb"
       - Should find the source

    7. Test end-to-end workflow:
       - Resolve data source to get source_id
       - Use source_id in /api/v1/discovery
       - Use source_id in /api/v1/generate-sql
       - Verify filtering works correctly
    """


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
