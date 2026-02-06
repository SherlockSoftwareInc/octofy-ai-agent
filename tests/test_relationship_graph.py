"""Tests for FK relationship graph built from schema descriptions."""
import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import TableSchema
from app.services.relationship_graph import RelationshipGraph


def _make_schema(schema: str, table: str, description: str) -> TableSchema:
    return TableSchema(
        schema_name=schema,
        table_name=table,
        description=description,
        columns=[]
    )


SCHEMAS = [
    _make_schema("dbo", "Categories", (
        "# **Table:** `[dbo].[Categories]`\n"
        "> Product categories.\n"
        "| 1 | `CategoryID` | Primary key |\n"
        "| 2 | `CategoryName` | Name |\n"
    )),
    _make_schema("dbo", "Products", (
        "# **Table:** `[dbo].[Products]`\n"
        "> Products for sale.\n"
        "| 3 | `SupplierID` | Reference: [dbo].[Suppliers].[SupplierID] |\n"
        "| 4 | `CategoryID` | Reference: Categories.CategoryID |\n"
    )),
    _make_schema("dbo", "Order Details", (
        "# **Table:** `[dbo].[Order Details]`\n"
        "> Line items.\n"
        "| 1 | `OrderID` | Reference: [dbo].[Orders].[OrderID] |\n"
        "| 2 | `ProductID` | Reference: [dbo].[Products].[ProductID] |\n"
    )),
    _make_schema("dbo", "Orders", (
        "# **Table:** `[dbo].[Orders]`\n"
        "> Customer orders.\n"
        "| 3 | `CustomerID` | Reference: [dbo].[Customers].[CustomerID] |\n"
    )),
    _make_schema("dbo", "Suppliers", (
        "# **Table:** `[dbo].[Suppliers]`\n"
        "> Supplier info.\n"
        "| 1 | `SupplierID` | Primary key |\n"
    )),
    _make_schema("dbo", "Customers", (
        "# **Table:** `[dbo].[Customers]`\n"
        "> Customer info.\n"
        "| 1 | `CustomerID` | Primary key |\n"
    )),
]


class TestParseReferences:
    def test_bracket_format(self):
        graph = RelationshipGraph(SCHEMAS)
        refs = graph._parse_references(SCHEMAS[2].description)  # Order Details
        assert ("dbo", "orders") in refs
        assert ("dbo", "products") in refs

    def test_dot_format(self):
        graph = RelationshipGraph(SCHEMAS)
        refs = graph._parse_references(SCHEMAS[1].description)  # Products
        assert ("dbo", "categories") in refs
        assert ("dbo", "suppliers") in refs

    def test_no_references(self):
        graph = RelationshipGraph(SCHEMAS)
        refs = graph._parse_references(SCHEMAS[0].description)  # Categories
        assert refs == set()


class TestReferencingTables:
    def test_categories_referenced_by_products(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Categories")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Products") in names

    def test_products_referenced_by_order_details(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Products")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Order Details") in names

    def test_standalone_table_has_referencers(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Customers")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Orders") in names

    def test_unreferenced_table(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Order Details")
        assert result == []


class TestReferencedTables:
    def test_products_references_categories_and_suppliers(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referenced_tables("dbo", "Products")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Categories") in names
        assert ("dbo", "Suppliers") in names

    def test_categories_references_nothing(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referenced_tables("dbo", "Categories")
        assert result == []


class TestTraceRelated:
    def test_1_hop_from_categories(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=1, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Products") in names
        assert ("dbo", "Order Details") not in names

    def test_2_hop_from_categories(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Products") in names
        assert ("dbo", "Order Details") in names

    def test_max_tables_cap(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=1)
        assert len(result) <= 1

    def test_does_not_include_self(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Categories") not in names

    def test_nonexistent_table(self):
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "NonExistent", max_hops=2, max_tables=10)
        assert result == []

    def test_does_not_traverse_through_unindexed_tables(self):
        """If A -> B (unindexed) -> C (indexed), C should NOT be found from A."""
        schemas = [
            _make_schema("dbo", "TableA", "| 1 | `BID` | Reference: [dbo].[TableB].[ID] |"),
            # TableB is NOT in schemas (unindexed) but referenced by A
            # TableB itself references TableC
            _make_schema("dbo", "TableC", "| 1 | `ID` | Primary key |"),
        ]
        graph = RelationshipGraph(schemas)
        result = graph.trace_related_tables("dbo", "TableA", max_hops=3, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        # TableC should NOT appear because TableB is unindexed (phantom node)
        assert ("dbo", "TableC") not in names


class TestSingleton:
    """Test get_relationship_graph singleton and invalidation."""

    @patch("app.services.vector_store.get_vector_store")
    def test_lazy_init(self, mock_get_vs):
        """Singleton initializes lazily from vector store."""
        import app.services.relationship_graph as rg

        # Clear any existing instance
        rg._graph_instance = None

        mock_store = MagicMock()
        mock_store.get_all_schemas.return_value = SCHEMAS
        mock_get_vs.return_value = mock_store

        graph = rg.get_relationship_graph()
        assert graph is not None
        mock_store.get_all_schemas.assert_called_once()

        # Second call should return cached instance (no second call to get_all_schemas)
        graph2 = rg.get_relationship_graph()
        assert graph2 is graph
        mock_store.get_all_schemas.assert_called_once()

        # Cleanup
        rg._graph_instance = None

    @patch("app.services.vector_store.get_vector_store")
    def test_force_rebuild(self, mock_get_vs):
        """force_rebuild=True triggers a fresh build."""
        import app.services.relationship_graph as rg

        rg._graph_instance = None

        mock_store = MagicMock()
        mock_store.get_all_schemas.return_value = SCHEMAS
        mock_get_vs.return_value = mock_store

        graph1 = rg.get_relationship_graph()
        graph2 = rg.get_relationship_graph(force_rebuild=True)
        assert graph2 is not graph1
        assert mock_store.get_all_schemas.call_count == 2

        # Cleanup
        rg._graph_instance = None

    def test_invalidate(self):
        """invalidate_relationship_graph clears the cached instance."""
        import app.services.relationship_graph as rg

        # Set a dummy instance
        rg._graph_instance = RelationshipGraph(SCHEMAS)
        assert rg._graph_instance is not None

        rg.invalidate_relationship_graph()
        assert rg._graph_instance is None
