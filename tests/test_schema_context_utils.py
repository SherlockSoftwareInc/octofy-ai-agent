"""
Tests for the shared schema context utilities.
"""
import pytest
from unittest.mock import MagicMock
from app.services.schema_context_utils import (
    build_schema_text,
    build_sufficiency_schema_text,
    prioritize_base_tables,
    generate_schema_id,
    has_datetime_columns,
    get_derivation_guidance,
    get_temporal_guidance,
    _is_view,
    _looks_like_fk,
    _extract_base_name,
)


def _make_schema(table_name, schema_name="dbo", columns=None, description="", table_type="TABLE"):
    """Helper to create mock schema objects."""
    mock = MagicMock()
    mock.table_name = table_name
    mock.schema_name = schema_name
    mock.description = description
    mock.table_type = table_type
    if columns:
        mock.columns = [_make_column(n, t, d) for n, t, d in columns]
    else:
        mock.columns = []
    return mock


def _make_column(name, data_type="nvarchar", description=""):
    mock = MagicMock()
    mock.name = name
    mock.data_type = data_type
    mock.description = description
    return mock


class TestBuildSchemaText:
    def test_basic_table(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", "PK"), ("Total", "decimal", "Order total")])]
        result = build_schema_text(schemas)
        assert "[TABLE]" in result
        assert "Orders" in result
        assert "OrderID" in result
    
    def test_view_annotation(self):
        schemas = [_make_schema("Orders_1997", table_type="VIEW", columns=[("OrderID", "int", "")])]
        result = build_schema_text(schemas)
        assert "[VIEW]" in result
    
    def test_fk_marker(self):
        schemas = [_make_schema("Orders", columns=[("CustomerID", "int", "FK to Customers")])]
        result = build_schema_text(schemas)
        assert "[FK]" in result
    
    def test_table_override_uses_description(self):
        schemas = [_make_schema("Orders", description="Custom description")]
        result = build_schema_text(schemas, use_table_override=True)
        assert result == "Custom description"
    
    def test_no_columns(self):
        schemas = [_make_schema("Orders")]
        result = build_schema_text(schemas)
        assert "(No columns defined)" in result


class TestBuildSufficiencySchemaText:
    def test_compact_format(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", ""), ("Total", "decimal", "")])]
        result = build_sufficiency_schema_text(schemas)
        assert "[TABLE]" in result
        assert "OrderID (int)" in result
    
    def test_falls_back_to_description(self):
        schemas = [_make_schema("Orders", description="Markdown description")]
        result = build_sufficiency_schema_text(schemas)
        assert "Markdown description" in result


class TestPrioritizeBaseTables:
    def test_filters_year_view(self):
        schemas = [
            _make_schema("Orders", columns=[("OrderDate", "datetime", "")]),
            _make_schema("Orders_1997", table_type="VIEW", columns=[("OrderDate", "datetime", "")]),
        ]
        result = prioritize_base_tables(schemas)
        assert len(result) == 1
        assert result[0].table_name == "Orders"
    
    def test_keeps_unrelated_view(self):
        schemas = [
            _make_schema("Orders", columns=[("OrderID", "int", "")]),
            _make_schema("CustomerSummary", table_type="VIEW", columns=[("Name", "nvarchar", "")]),
        ]
        result = prioritize_base_tables(schemas)
        assert len(result) == 2
    
    def test_no_views_returns_all(self):
        schemas = [
            _make_schema("Orders"),
            _make_schema("Customers"),
        ]
        result = prioritize_base_tables(schemas)
        assert len(result) == 2


class TestGenerateSchemaId:
    def test_deterministic(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", "")])]
        id1 = generate_schema_id(schemas)
        id2 = generate_schema_id(schemas)
        assert id1 == id2
    
    def test_different_schemas_different_ids(self):
        s1 = [_make_schema("Orders", columns=[("OrderID", "int", "")])]
        s2 = [_make_schema("Customers", columns=[("CustomerID", "int", "")])]
        assert generate_schema_id(s1) != generate_schema_id(s2)


class TestHasDatetimeColumns:
    def test_has_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderDate", "datetime", "")])]
        assert has_datetime_columns(schemas) is True
    
    def test_has_date(self):
        schemas = [_make_schema("Orders", columns=[("OrderDate", "date", "")])]
        assert has_datetime_columns(schemas) is True
    
    def test_no_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", ""), ("Name", "nvarchar", "")])]
        assert has_datetime_columns(schemas) is False
    
    def test_empty_schemas(self):
        assert has_datetime_columns([]) is False


class TestGetDerivationGuidance:
    def test_sql_guidance(self):
        result = get_derivation_guidance("sql")
        assert "COUNT(*)" in result
        assert "CASE WHEN" in result
    
    def test_python_guidance(self):
        result = get_derivation_guidance("python")
        assert "pandas" in result
        assert "df.groupby" in result
    
    def test_r_guidance(self):
        result = get_derivation_guidance("r")
        assert "dplyr" in result
        assert "summarise" in result
    
    def test_sas_guidance(self):
        result = get_derivation_guidance("sas")
        assert "PROC SQL" in result
        assert "DATA step" in result


class TestGetTemporalGuidance:
    def test_has_guidance_when_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderDate", "datetime", "")])]
        result = get_temporal_guidance(schemas)
        assert "TEMPORAL" in result
    
    def test_empty_when_no_datetime(self):
        schemas = [_make_schema("Orders", columns=[("OrderID", "int", "")])]
        result = get_temporal_guidance(schemas)
        assert result == ""


class TestPrivateHelpers:
    def test_is_view_by_type(self):
        assert _is_view("VIEW", "Orders") is True
        assert _is_view("TABLE", "Orders") is False
    
    def test_is_view_by_name(self):
        assert _is_view(None, "Orders_vw") is True
        assert _is_view(None, "OrdersView") is True
        assert _is_view(None, "Orders") is False
    
    def test_looks_like_fk(self):
        assert _looks_like_fk("CustomerID") is True
        assert _looks_like_fk("OrderID") is True
        assert _looks_like_fk("ID") is False  # Just "ID" alone is not an FK
        assert _looks_like_fk("Name") is False
    
    def test_extract_base_name(self):
        assert _extract_base_name("Orders_1997") == "Orders"
        assert _extract_base_name("Customers_vw") == "Customers"
        assert _extract_base_name("ProductsView") == "Products"
        assert _extract_base_name("Orders") is None
