"""
Tests for planning context serialization helper.

This tests the _serialize_planning_context() function which converts
planning context dictionaries (with sets) to JSON-safe strings.
"""

import pytest
import json
from app.services.generation_service import _serialize_planning_context


class TestSerializePlanningContext:
    """Test suite for planning context serialization."""
    
    def test_converts_sets_to_lists(self):
        """Converts set fields to lists for JSON serialization."""
        context = {
            "goal": "Show sales",
            "rejected_tables": {"dbo.Sales", "dbo.Orders"},
            "confirmed_tables": {"dbo.Products"},
            "last_auto_checked": {"dbo.Customers"}
        }
        
        result = _serialize_planning_context(context)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["goal"] == "Show sales"
        
        # Sets should be converted to lists
        assert isinstance(parsed["rejected_tables"], list)
        assert isinstance(parsed["confirmed_tables"], list)
        assert isinstance(parsed["last_auto_checked"], list)
        
        # Check content (order doesn't matter for sets->lists)
        assert set(parsed["rejected_tables"]) == {"dbo.Sales", "dbo.Orders"}
        assert set(parsed["confirmed_tables"]) == {"dbo.Products"}
        assert set(parsed["last_auto_checked"]) == {"dbo.Customers"}
    
    def test_preserves_non_set_fields(self):
        """Preserves fields that aren't sets."""
        context = {
            "goal": "Analysis",
            "selected_tables": ["table1", "table2"],  # Already a list
            "turn_count": 5,
            "conversation_history": [{"user": "hello"}],
            "requirements": {"type": "filter"}
        }
        
        result = _serialize_planning_context(context)
        parsed = json.loads(result)
        
        assert parsed["goal"] == "Analysis"
        assert parsed["selected_tables"] == ["table1", "table2"]
        assert parsed["turn_count"] == 5
        assert parsed["conversation_history"] == [{"user": "hello"}]
        assert parsed["requirements"] == {"type": "filter"}
    
    def test_handles_empty_sets(self):
        """Handles empty sets correctly."""
        context = {
            "rejected_tables": set(),
            "confirmed_tables": set()
        }
        
        result = _serialize_planning_context(context)
        parsed = json.loads(result)
        
        assert parsed["rejected_tables"] == []
        assert parsed["confirmed_tables"] == []
    
    def test_handles_nested_structures(self):
        """Handles nested dictionaries and lists."""
        context = {
            "goal": "Test",
            "rejected_tables": {"table1"},
            "conversation_history": [
                {"user": "query", "intent": {"ready": True}}
            ],
            "requirements": [
                {"type": "filter", "values": ["a", "b"]}
            ]
        }
        
        result = _serialize_planning_context(context)
        parsed = json.loads(result)
        
        assert parsed["conversation_history"][0]["intent"]["ready"] is True
        assert parsed["requirements"][0]["values"] == ["a", "b"]
        assert set(parsed["rejected_tables"]) == {"table1"}
    
    def test_handles_context_without_set_fields(self):
        """Works with contexts that don't have set fields."""
        context = {
            "goal": "Simple goal",
            "turn_count": 1
        }
        
        result = _serialize_planning_context(context)
        parsed = json.loads(result)
        
        assert parsed["goal"] == "Simple goal"
        assert parsed["turn_count"] == 1
    
    def test_returns_valid_json_string(self):
        """Returns a valid JSON string."""
        context = {
            "goal": "Test",
            "rejected_tables": {"table1", "table2"}
        }
        
        result = _serialize_planning_context(context)
        
        # Should be a string
        assert isinstance(result, str)
        
        # Should be valid JSON (no exception)
        json.loads(result)
    
    def test_handles_all_tracked_set_fields(self):
        """Handles all three set fields used in planning context."""
        context = {
            "rejected_tables": {"t1"},
            "confirmed_tables": {"t2"},
            "last_auto_checked": {"t3"}
        }
        
        result = _serialize_planning_context(context)
        parsed = json.loads(result)
        
        assert "t1" in parsed["rejected_tables"]
        assert "t2" in parsed["confirmed_tables"]
        assert "t3" in parsed["last_auto_checked"]
    
    def test_handles_special_characters_in_table_names(self):
        """Handles special characters in set values."""
        context = {
            "rejected_tables": {"[dbo].[Sales]", "schema.table_name"},
            "goal": "Test with special chars"
        }
        
        result = _serialize_planning_context(context)
        parsed = json.loads(result)
        
        assert "[dbo].[Sales]" in parsed["rejected_tables"]
        assert "schema.table_name" in parsed["rejected_tables"]
