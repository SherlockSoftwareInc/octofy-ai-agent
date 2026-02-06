"""Tests for relationship tracing in generation_service's dual-prong path."""
import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import TableSchema
from app.services.relationship_graph import RelationshipGraph


def _schema(schema: str, table: str, desc: str = "") -> TableSchema:
    return TableSchema(schema_name=schema, table_name=table, description=desc, columns=[])


_TEST_SCHEMAS = [
    _schema("dbo", "Categories", "| 1 | `CategoryID` | Primary key |"),
    _schema("dbo", "Products", "| 4 | `CategoryID` | Reference: Categories.CategoryID |"),
    _schema("dbo", "Order Details", "| 2 | `ProductID` | Reference: [dbo].[Products].[ProductID] |"),
]

_TEST_GRAPH = RelationshipGraph(_TEST_SCHEMAS)


class TestExpandValueTablesWithRelationships:
    """Test the expand_value_tables_with_relationships helper."""

    @patch("app.services.generation_service.get_relationship_graph")
    def test_expands_lookup_tables(self, mock_graph):
        """Starting from Categories, should discover Products and Order Details."""
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        input_tables = ["dbo.Categories"]
        result = expand_value_tables_with_relationships(input_tables)

        assert "dbo.Categories" in result
        # Should find Products (1 hop) and Order Details (2 hops)
        result_lower = [t.lower() for t in result]
        assert any("products" in t for t in result_lower)
        assert any("order details" in t for t in result_lower)

    @patch("app.services.generation_service.get_relationship_graph")
    def test_deduplicates(self, mock_graph):
        """Duplicate input tables should produce no duplicates in output."""
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        input_tables = ["dbo.Categories", "dbo.Categories"]
        result = expand_value_tables_with_relationships(input_tables)

        normalized = [t.lower().replace('[', '').replace(']', '') for t in result]
        assert len(normalized) == len(set(normalized))

    @patch("app.services.generation_service.get_relationship_graph")
    def test_empty_input(self, mock_graph):
        """Empty input should return empty list."""
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        result = expand_value_tables_with_relationships([])
        assert result == []

    @patch("app.services.generation_service.get_relationship_graph")
    def test_graceful_on_graph_error(self, mock_graph):
        """If graph fails to load, original tables should be returned unchanged."""
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.side_effect = Exception("Milvus down")

        input_tables = ["dbo.Categories"]
        result = expand_value_tables_with_relationships(input_tables)
        # Should return original tables without crashing
        assert result == ["dbo.Categories"]

    @patch("app.services.generation_service.get_relationship_graph")
    def test_handles_bracket_format(self, mock_graph):
        """Should handle [schema].[table] input format."""
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        input_tables = ["[dbo].[Categories]"]
        result = expand_value_tables_with_relationships(input_tables)

        # Original format preserved, plus expanded tables
        assert "[dbo].[Categories]" in result
        result_lower = [t.lower() for t in result]
        assert any("products" in t for t in result_lower)

    @patch("app.services.generation_service.get_relationship_graph")
    def test_handles_bare_table_name(self, mock_graph):
        """Should handle bare table names without schema prefix."""
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        input_tables = ["Categories"]
        result = expand_value_tables_with_relationships(input_tables)

        # Bare name preserved, plus expanded tables
        assert "Categories" in result
        result_lower = [t.lower() for t in result]
        assert any("products" in t for t in result_lower)
