"""
Tests for Chart Intent Detection Service
"""

import pytest
from app.services.chart_intent_service import detect_chart_intent, extract_data_query, ChartIntent
from app.models.schemas import GenerateSQLRequest, ExecutePythonRequest


class TestChartIntentDetection:
    """Tests for detect_chart_intent function"""
    
    def test_detect_line_chart_intent(self):
        result = detect_chart_intent("show me the results as a line chart")
        assert result is not None
        assert result.chart_type == "line"
        assert result.is_chart_only_request == True
    
    def test_detect_column_chart_intent(self):
        result = detect_chart_intent("can you make that a column chart instead")
        assert result is not None
        assert result.chart_type == "column"
    
    def test_detect_pie_chart_intent(self):
        result = detect_chart_intent("display this as a pie chart")
        assert result is not None
        assert result.chart_type == "pie"
    
    def test_detect_scatter_plot_intent(self):
        result = detect_chart_intent("I'd like to see a scatter plot")
        assert result is not None
        assert result.chart_type == "scatter"
    
    def test_no_chart_intent_for_data_query(self):
        result = detect_chart_intent("show me sales by region")
        assert result is None
    
    def test_combined_data_and_chart_request(self):
        result = detect_chart_intent("show monthly revenue as a line chart")
        assert result is not None
        assert result.chart_type == "line"
        assert result.is_chart_only_request == False
    
    def test_case_insensitive_detection(self):
        result = detect_chart_intent("SHOW ME A LINE CHART")
        assert result is not None
        assert result.chart_type == "line"
    
    def test_line_graph_variant(self):
        result = detect_chart_intent("display as a line graph")
        assert result is not None
        assert result.chart_type == "line"
    
    def test_column_graph_variant(self):
        result = detect_chart_intent("show it as a column graph")
        assert result is not None
        assert result.chart_type == "column"
    
    def test_bar_graph_maps_to_column(self):
        result = detect_chart_intent("make it a bar chart")
        assert result is not None
        assert result.chart_type == "column"
    
    def test_doughnut_chart_maps_to_pie(self):
        result = detect_chart_intent("show as doughnut chart")
        assert result is not None
        assert result.chart_type == "pie"
    
    def test_xy_plot_maps_to_scatter(self):
        result = detect_chart_intent("create an xy plot")
        assert result is not None
        assert result.chart_type == "scatter"
    
    def test_switch_to_pattern(self):
        result = detect_chart_intent("switch to column chart")
        assert result is not None
        assert result.chart_type == "column"
        assert result.is_chart_only_request == True
    
    def test_change_to_pattern(self):
        result = detect_chart_intent("change it to a pie chart")
        assert result is not None
        assert result.chart_type == "pie"
        assert result.is_chart_only_request == True
    
    def test_convert_to_pattern(self):
        result = detect_chart_intent("convert to line chart")
        assert result is not None
        assert result.chart_type == "line"
        assert result.is_chart_only_request == True
    
    def test_original_query_preserved(self):
        query = "show me the results as a line chart"
        result = detect_chart_intent(query)
        assert result is not None
        assert result.original_query == query


class TestExtractDataQuery:
    """Tests for extract_data_query function"""
    
    def test_extract_removes_chart_type(self):
        query = "show monthly revenue as a line chart"
        intent = detect_chart_intent(query)
        result = extract_data_query(query, intent)
        assert "line chart" not in result.lower()
        assert "revenue" in result.lower()
    
    def test_extract_returns_original_for_chart_only(self):
        query = "show it as a column chart"
        intent = detect_chart_intent(query)
        # For chart-only requests, the original query is returned
        result = extract_data_query(query, intent)
        assert result == query
    
    def test_extract_handles_none_intent(self):
        query = "show me sales by region"
        result = extract_data_query(query, None)
        assert result == query


class TestSchemaChartIntent:
    """Tests for chart_type_override in API schemas"""
    
    def test_generate_sql_request_has_chart_type_override(self):
        request = GenerateSQLRequest(
            query="show me sales",
            chart_type_override="line"
        )
        assert request.chart_type_override == "line"
    
    def test_generate_sql_request_chart_override_default_none(self):
        request = GenerateSQLRequest(query="show me sales")
        assert request.chart_type_override is None
    
    def test_execute_python_request_has_chart_type_override(self):
        request = ExecutePythonRequest(
            code="print('hello')",
            chart_type_override="column"
        )
        assert request.chart_type_override == "column"
    
    def test_execute_python_request_chart_override_default_none(self):
        request = ExecutePythonRequest(code="print('hello')")
        assert request.chart_type_override is None
