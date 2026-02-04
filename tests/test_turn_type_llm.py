"""
Tests for LLM-based turn-type classification fallback.

This tests the _classify_turn_type_llm() function which uses an LLM to classify
conversation turn types when fast pattern matching is insufficient.
"""

import pytest
from unittest.mock import Mock, patch
from app.services.generation_service import _classify_turn_type_llm


class TestClassifyTurnTypeLLM:
    """Test suite for LLM-based turn-type classification."""
    
    @patch('app.services.generation_service.get_llm_service')
    def test_successful_classification_refinement(self, mock_get_llm):
        """LLM successfully classifies a refinement turn."""
        # Setup
        mock_llm = Mock()
        mock_llm.chat.return_value = """```json
{
    "turn_type": "refinement",
    "confidence": 0.85,
    "reasoning": "User is adding filters to existing goal",
    "topic_similarity": 0.8,
    "changed_requirements": [],
    "new_requirements": ["filter by region"]
}
```"""
        mock_get_llm.return_value = mock_llm
        
        query = "also show only North America"
        planning_context = {
            "goal": "Show sales by region",
            "conversation_history": [
                {"user": "Show sales by region", "assistant": "What time period?"}
            ]
        }
        
        # Execute
        result = _classify_turn_type_llm(query, planning_context)
        
        # Assert
        assert result is not None
        assert result["turn_type"] == "refinement"
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "User is adding filters to existing goal"
        assert result["topic_similarity"] == 0.8
        assert result["new_requirements"] == ["filter by region"]
        
        # Verify LLM was called with temperature=0.3
        mock_llm.chat.assert_called_once()
        call_args = mock_llm.chat.call_args
        assert call_args[1]["temperature"] == 0.3
    
    @patch('app.services.generation_service.get_llm_service')
    def test_successful_classification_pivot(self, mock_get_llm):
        """LLM successfully classifies a pivot turn."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """{
    "turn_type": "pivot",
    "confidence": 0.9,
    "reasoning": "User switched from sales to employees",
    "topic_similarity": 0.1,
    "changed_requirements": [],
    "new_requirements": []
}"""
        mock_get_llm.return_value = mock_llm
        
        query = "Actually, show me employee headcount instead"
        planning_context = {
            "goal": "Show sales by region",
            "conversation_history": []
        }
        
        result = _classify_turn_type_llm(query, planning_context)
        
        assert result["turn_type"] == "pivot"
        assert result["confidence"] == 0.9
        assert result["topic_similarity"] == 0.1
    
    @patch('app.services.generation_service.get_llm_service')
    def test_successful_classification_correction(self, mock_get_llm):
        """LLM successfully classifies a correction turn."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """
{
    "turn_type": "correction",
    "confidence": 0.88,
    "reasoning": "User is correcting the region filter",
    "topic_similarity": 0.7,
    "changed_requirements": ["region"],
    "new_requirements": []
}
"""
        mock_get_llm.return_value = mock_llm
        
        query = "No, I meant Europe, not North America"
        planning_context = {
            "goal": "Show sales by region",
            "conversation_history": [
                {"user": "Show sales by region", "assistant": "Which region?"},
                {"user": "North America", "assistant": "Understood"}
            ]
        }
        
        result = _classify_turn_type_llm(query, planning_context)
        
        assert result["turn_type"] == "correction"
        assert result["changed_requirements"] == ["region"]
    
    @patch('app.services.generation_service.get_llm_service')
    def test_handles_markdown_code_blocks(self, mock_get_llm):
        """Properly strips markdown code blocks from LLM response."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """```json
{
    "turn_type": "refinement",
    "confidence": 0.8,
    "reasoning": "Adding detail",
    "topic_similarity": 0.75,
    "changed_requirements": [],
    "new_requirements": []
}
```"""
        mock_get_llm.return_value = mock_llm
        
        result = _classify_turn_type_llm("add filter", {"goal": "sales"})
        
        assert result["turn_type"] == "refinement"
    
    @patch('app.services.generation_service.get_llm_service')
    def test_handles_invalid_json_response(self, mock_get_llm):
        """Falls back to REFINEMENT when LLM returns invalid JSON."""
        mock_llm = Mock()
        mock_llm.chat.return_value = "This is not JSON at all!"
        mock_get_llm.return_value = mock_llm
        
        result = _classify_turn_type_llm("some query", {"goal": "goal"})
        
        # Should return fallback refinement result
        assert result["turn_type"] == "refinement"
        assert result["confidence"] == 0.5
        assert "error" in result["reasoning"].lower() or "fallback" in result["reasoning"].lower()
    
    @patch('app.services.generation_service.get_llm_service')
    def test_handles_missing_required_fields(self, mock_get_llm):
        """Falls back to REFINEMENT when required fields are missing."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """{"confidence": 0.9}"""  # Missing turn_type
        mock_get_llm.return_value = mock_llm
        
        result = _classify_turn_type_llm("query", {"goal": "goal"})
        
        assert result["turn_type"] == "refinement"
        assert result["confidence"] == 0.5
    
    @patch('app.services.generation_service.get_llm_service')
    def test_handles_llm_service_exception(self, mock_get_llm):
        """Falls back to REFINEMENT when LLM service raises exception."""
        mock_llm = Mock()
        mock_llm.chat.side_effect = Exception("API timeout")
        mock_get_llm.return_value = mock_llm
        
        result = _classify_turn_type_llm("query", {"goal": "goal"})
        
        assert result["turn_type"] == "refinement"
        assert result["confidence"] == 0.5
    
    @patch('app.services.generation_service.get_llm_service')
    def test_includes_conversation_history_in_prompt(self, mock_get_llm):
        """Verifies conversation history is included in LLM prompt."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """{"turn_type": "refinement", "confidence": 0.8, "reasoning": "test", "topic_similarity": 0.7, "changed_requirements": [], "new_requirements": []}"""
        mock_get_llm.return_value = mock_llm
        
        planning_context = {
            "goal": "Show sales",
            "conversation_history": [
                {"user": "Show sales", "assistant": "Which region?"},
                {"user": "North America", "assistant": "Got it"}
            ]
        }
        
        _classify_turn_type_llm("add time filter", planning_context)
        
        # Check that the prompt includes conversation history
        call_args = mock_llm.chat.call_args
        prompt = call_args[0][0]
        assert "conversation_history" in prompt.lower() or "Show sales" in prompt
    
    @patch('app.services.generation_service.get_llm_service')
    def test_validates_turn_type_enum_values(self, mock_get_llm):
        """Falls back when LLM returns invalid turn_type value."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """{"turn_type": "invalid_type", "confidence": 0.9, "reasoning": "test", "topic_similarity": 0.7, "changed_requirements": [], "new_requirements": []}"""
        mock_get_llm.return_value = mock_llm
        
        result = _classify_turn_type_llm("query", {"goal": "goal"})
        
        # Should fallback since "invalid_type" is not in TurnType enum
        assert result["turn_type"] == "refinement"
        assert result["confidence"] == 0.5
    
    @patch('app.services.generation_service.get_llm_service')
    def test_validates_confidence_bounds(self, mock_get_llm):
        """Falls back when confidence is outside [0,1] range."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """{"turn_type": "refinement", "confidence": 1.5, "reasoning": "test", "topic_similarity": 0.7, "changed_requirements": [], "new_requirements": []}"""
        mock_get_llm.return_value = mock_llm
        
        result = _classify_turn_type_llm("query", {"goal": "goal"})
        
        # Should fallback due to invalid confidence
        assert result["turn_type"] == "refinement"
        assert result["confidence"] == 0.5
