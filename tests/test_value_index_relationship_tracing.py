"""Tests for value index + relationship tracing integration in discovery_service."""
import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import TableSchema, RankedTable
from app.services.relationship_graph import RelationshipGraph


# -- Fixtures --

def _schema(schema: str, table: str, desc: str = "") -> TableSchema:
    return TableSchema(schema_name=schema, table_name=table, description=desc, columns=[])


# Simulate a small Northwind-like graph
_TEST_SCHEMAS = [
    _schema("dbo", "Categories", "| 1 | `CategoryID` | Primary key |"),
    _schema("dbo", "Products", "| 4 | `CategoryID` | Reference: Categories.CategoryID |"),
    _schema("dbo", "Order Details", "| 2 | `ProductID` | Reference: [dbo].[Products].[ProductID] |"),
    _schema("dbo", "Orders", "| 1 | `OrderID` | Primary key |"),
    _schema("dbo", "Suppliers", "| 1 | `SupplierID` | Primary key |"),
]

_TEST_GRAPH = RelationshipGraph(_TEST_SCHEMAS)


def _mock_value_result(schema: str, table: str) -> dict:
    """Create a mock value_index search result."""
    return {
        "entity": {
            "schema_name": schema,
            "table_name": table,
            "column_name": "CategoryName",
            "value": "Beverages"
        }
    }


# -- Tests --

class TestPerformValueIndexSearchWithRelationships:
    """Test that perform_value_index_search includes related tables."""

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_adds_related_tables_for_lookup_hit(self, mock_vs, mock_graph):
        """When value index matches Categories, Products and Order Details should be added."""
        from app.services.discovery_service import perform_value_index_search

        # Mock value search returns Categories
        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store

        # Mock relationship graph
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        # Should contain Categories (direct match) + Products + Order Details (traced)
        table_names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Categories") in table_names, "Direct match should be present"
        assert ("dbo", "Products") in table_names, "1-hop related table should be present"
        assert ("dbo", "Order Details") in table_names, "2-hop related table should be present"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_related_tables_have_relationship_traced_marker(self, mock_vs, mock_graph):
        """Related tables should have 'relationship_traced' in matched_by."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        direct = [t for t in result if t.table_name == "Categories"]
        traced = [t for t in result if t.table_name != "Categories"]

        assert all("value_index" in t.matched_by for t in direct)
        assert all("relationship_traced" in t.matched_by for t in traced)

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_related_tables_score_equals_direct(self, mock_vs, mock_graph):
        """Related tables should receive score=8 (same as direct value index match)."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        for t in result:
            assert t.score == 8, f"{t.table_name} should have score=8, got {t.score}"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_max_related_tables_cap(self, mock_vs, mock_graph):
        """Should not add more than MAX_RELATED_TABLES_PER_HIT related tables per hit."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        # Direct hit = 1, related <= 3 (cap)
        assert len(result) <= 1 + 3, f"Should not exceed cap: got {len(result)} tables"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_no_duplicates(self, mock_vs, mock_graph):
        """If two value hits resolve to the same table, no duplicates in result."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [
            _mock_value_result("dbo", "Categories"),
            _mock_value_result("dbo", "Categories"),  # duplicate
        ]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages Condiments")

        keys = [(t.schema_name.lower(), t.table_name.lower()) for t in result]
        assert len(keys) == len(set(keys)), f"Duplicate tables found: {keys}"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_no_value_hits_returns_empty(self, mock_vs, mock_graph):
        """If value index returns nothing, result should be empty."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = []
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("unknown query")
        assert result == []

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_graceful_on_graph_error(self, mock_vs, mock_graph):
        """If relationship graph fails, direct matches are still returned."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.side_effect = Exception("Milvus down")

        result = perform_value_index_search("Beverages sales")

        # Should still have the direct match
        assert len(result) == 1
        assert result[0].table_name == "Categories"


class TestRerankCandidatesWithTracedTables:
    """Test that rerank_candidates properly scores relationship_traced tables."""

    def test_traced_tables_get_value_index_weight(self):
        """Tables with matched_by=['relationship_traced'] should get value_index weight (8)."""
        from app.services.discovery_service import rerank_candidates

        value_tables = [
            RankedTable(schema_name="dbo", table_name="Categories", score=8, matched_by=["value_index"]),
            RankedTable(schema_name="dbo", table_name="Products", score=8, matched_by=["relationship_traced"]),
        ]

        result = rerank_candidates([], value_tables, [])

        products = [t for t in result if t.table_name == "Products"][0]
        assert products.score == 8, f"Traced table should get score 8, got {products.score}"
        assert "relationship_traced" in products.matched_by or "value_index" in products.matched_by
