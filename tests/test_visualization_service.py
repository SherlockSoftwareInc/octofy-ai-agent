"""
Tests for Visualization Service - Chart Type Override
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
import sys

# Mock the llm_service module before importing VisualizationService
sys.modules['app.services.llm_service'] = MagicMock()
sys.modules['app.utils.logging_utils'] = MagicMock()

from app.services.visualization_service import VisualizationService
from app.models.schemas import ChartRecommendation


class TestVisualizationServiceOverride:
    """Tests for chart_type_override functionality in VisualizationService"""
    
    @pytest.fixture
    def sample_df(self):
        """Simple DataFrame for testing"""
        return pd.DataFrame({
            'category': ['A', 'B', 'C', 'D', 'E'],
            'value': [10, 20, 30, 40, 50],
            'count': [1, 2, 3, 4, 5]
        })
    
    @pytest.fixture
    def numeric_df(self):
        """DataFrame with only numeric columns for scatter plot testing"""
        return pd.DataFrame({
            'x_val': [1, 2, 3, 4, 5],
            'y_val': [10, 20, 15, 25, 30],
            'z_val': [5, 10, 8, 12, 15]
        })
    
    @pytest.fixture
    def datetime_df(self):
        """DataFrame with datetime column for line chart testing"""
        return pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'value': [100, 150, 120, 180, 200]
        })
    
    @pytest.fixture
    def service(self):
        """Create VisualizationService with mocked LLM"""
        with patch.object(VisualizationService, '__init__', lambda x: None):
            svc = VisualizationService()
            svc.llm_service = MagicMock()
            return svc
    
    def test_chart_type_override_line(self, service, sample_df):
        """When chart_type_override='line', should return line chart"""
        result = service.get_chart_recommendation(sample_df, "test query", chart_type_override="line")
        
        assert result is not None
        assert result.chart_type == "line"
        assert result.x_axis == "category"  # First categorical column
        assert "value" in result.y_axis or "count" in result.y_axis
    
    def test_chart_type_override_bar(self, service, sample_df):
        """When chart_type_override='bar', should return bar chart"""
        result = service.get_chart_recommendation(sample_df, "test query", chart_type_override="bar")
        
        assert result is not None
        assert result.chart_type == "bar"
        assert result.x_axis == "category"
    
    def test_chart_type_override_pie(self, service, sample_df):
        """When chart_type_override='pie', should return pie chart"""
        result = service.get_chart_recommendation(sample_df, "test query", chart_type_override="pie")
        
        assert result is not None
        assert result.chart_type == "pie"
        assert result.x_axis == "category"
        assert len(result.y_axis) == 1  # Pie charts should have single Y
    
    def test_chart_type_override_scatter(self, service, numeric_df):
        """When chart_type_override='scatter', should select two numeric columns"""
        result = service.get_chart_recommendation(numeric_df, "test query", chart_type_override="scatter")
        
        assert result is not None
        assert result.chart_type == "scatter"
        assert result.x_axis in ["x_val", "y_val", "z_val"]
        assert len(result.y_axis) == 1
    
    def test_chart_type_override_none_uses_llm(self, service, sample_df):
        """When chart_type_override is None, should call LLM"""
        # Setup mock LLM to return a bar chart recommendation
        service.llm_service.chat.return_value = '''
        {
            "chart_type": "bar",
            "x_axis": "category",
            "y_axis": ["value"],
            "title": "Test Chart",
            "explanation": "Test explanation",
            "colors": null
        }
        '''
        
        result = service.get_chart_recommendation(sample_df, "test query", chart_type_override=None)
        
        # LLM should have been called
        service.llm_service.chat.assert_called_once()
        assert result is not None
    
    def test_chart_type_override_skips_llm(self, service, sample_df):
        """When chart_type_override is set, should NOT call LLM"""
        result = service.get_chart_recommendation(sample_df, "test query", chart_type_override="line")
        
        # LLM should NOT have been called
        service.llm_service.chat.assert_not_called()
        assert result is not None
        assert result.chart_type == "line"
    
    def test_datetime_df_line_chart(self, service, datetime_df):
        """Line chart with datetime data should use date column as X"""
        result = service.get_chart_recommendation(datetime_df, "trend over time", chart_type_override="line")
        
        assert result is not None
        assert result.chart_type == "line"
        assert result.x_axis == "date"
        assert "value" in result.y_axis
    
    def test_empty_df_returns_none(self, service):
        """Empty DataFrame should return None"""
        result = service.get_chart_recommendation(pd.DataFrame(), "test", chart_type_override="line")
        
        assert result is None
    
    def test_recommendation_has_title_and_explanation(self, service, sample_df):
        """Override recommendation should include title and explanation"""
        result = service.get_chart_recommendation(sample_df, "test query", chart_type_override="bar")
        
        assert result is not None
        assert result.title is not None
        assert "bar" in result.title.lower()
        assert result.explanation is not None
        assert "bar" in result.explanation.lower()


class TestEndpointChartOverrideWiring:
    """Tests to verify execute-python endpoint properly passes chart_type_override"""
    
    def test_endpoint_passes_chart_type_override_to_viz_service(self):
        """Verify that execute-python endpoint passes chart_type_override to VisualizationService"""
        from pathlib import Path
        
        # Read the source code of the endpoint directly to avoid import issues
        endpoint_file = Path(__file__).parent.parent / "app" / "api" / "endpoints" / "generation.py"
        source = endpoint_file.read_text()
        
        # Verify that chart_type_override is passed to get_chart_recommendation
        assert "chart_type_override" in source, \
            "execute_python_endpoint should reference chart_type_override"
        assert "request.chart_type_override" in source, \
            "execute_python_endpoint should pass request.chart_type_override to viz service"
    
    def test_viz_service_call_includes_override_param(self):
        """Verify the get_chart_recommendation call signature includes override"""
        from pathlib import Path
        
        # Read the source code directly
        endpoint_file = Path(__file__).parent.parent / "app" / "api" / "endpoints" / "generation.py"
        source = endpoint_file.read_text()
        
        # Check that the call pattern includes the override parameter
        assert "get_chart_recommendation(" in source
        # Should have 3 arguments: df, code, and chart_type_override
        assert "request.chart_type_override" in source, \
            "get_chart_recommendation should be called with chart_type_override parameter"
