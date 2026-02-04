"""
Tests for turn-type classification integration into planning_conversation.

This tests the full integration of turn-type detection and handling logic
within the planning_conversation flow.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from app.services.generation_service import planning_conversation


class TestPlanningTurnClassification:
    """Test suite for turn-type classification integration."""
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    @patch('app.services.generation_service._detect_turn_type_fast')
    def test_uses_fast_detection_when_available(self, mock_fast, mock_search, mock_vector, mock_llm):
        """Uses fast pattern matching when it returns a confident result."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = 'OK'
        mock_llm.return_value = mock_llm_instance
        
        # Fast detection returns a confident result
        mock_fast.return_value = {
            "turn_type": "confirmation",
            "confidence": 0.95,
            "reasoning": "User said yes",
            "topic_similarity": 1.0
        }
        
        context = {
            "goal": "Show sales",
            "selected_tables": [],
            "conversation_history": []
        }
        
        response = planning_conversation("yes", planning_context=context)
        
        # Verify fast detection was called
        mock_fast.assert_called_once()
        
        # Verify LLM chat was still called for response generation
        assert mock_llm_instance.chat.called
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    @patch('app.services.generation_service._detect_turn_type_fast')
    @patch('app.services.generation_service._classify_turn_type_llm')
    def test_falls_back_to_llm_classification(self, mock_llm_classify, mock_fast, mock_search, mock_vector, mock_llm):
        """Falls back to LLM classification when fast detection returns None."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = '{"goal_clear": true, "goal_statement": "Test", "critical_ambiguities": [], "ready_for_search": false, "required_questions": [], "requirements_extracted": []}'
        mock_llm.return_value = mock_llm_instance
        
        # Fast detection returns None (ambiguous)
        mock_fast.return_value = None
        
        # LLM classification returns result
        mock_llm_classify.return_value = {
            "turn_type": "refinement",
            "confidence": 0.8,
            "reasoning": "Adding detail",
            "topic_similarity": 0.7,
            "changed_requirements": [],
            "new_requirements": ["filter"]
        }
        
        context = {
            "goal": "Show sales",
            "selected_tables": [],
            "conversation_history": []
        }
        
        response = planning_conversation("add filter", planning_context=context)
        
        # Verify fallback was used
        mock_fast.assert_called_once()
        mock_llm_classify.assert_called_once()
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    @patch('app.services.generation_service._detect_turn_type_fast')
    def test_pivot_triggers_confirmation_prompt(self, mock_fast, mock_search, mock_vector, mock_llm):
        """Pivot detection triggers a confirmation prompt before switching."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = "Confirmation prompt"
        mock_llm.return_value = mock_llm_instance
        
        mock_fast.return_value = {
            "turn_type": "pivot",
            "confidence": 0.85,
            "reasoning": "Switching topics",
            "topic_similarity": 0.2
        }
        
        context = {
            "goal": "Show sales",
            "selected_tables": [],
            "conversation_history": [],
            "goal_history": []
        }
        
        response = planning_conversation("Show employee count instead", planning_context=context)
        
        # Parse returned context
        returned_context = json.loads(response.context_text)
        
        # Should set pending_pivot flag
        assert "pending_pivot" in returned_context
        assert returned_context["pending_pivot"]["new_goal"] == "Show employee count instead"
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    @patch('app.services.generation_service._detect_turn_type_fast')
    def test_confirmation_completes_pivot(self, mock_fast, mock_search, mock_vector, mock_llm):
        """Confirmation after pivot prompt completes the topic switch."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = '{"goal_clear": true, "goal_statement": "Employee count", "critical_ambiguities": [], "ready_for_search": true, "required_questions": [], "requirements_extracted": []}'
        mock_llm.return_value = mock_llm_instance
        mock_search.return_value = MagicMock(objects=[])
        
        mock_fast.return_value = {
            "turn_type": "confirmation",
            "confidence": 0.95,
            "reasoning": "User confirmed",
            "topic_similarity": 1.0
        }
        
        context = {
            "goal": "Show sales",
            "selected_tables": [],
            "conversation_history": [],
            "goal_history": [],
            "pending_pivot": {
                "new_goal": "Show employee count",
                "previous_goal": "Show sales"
            }
        }
        
        response = planning_conversation("yes", planning_context=context)
        
        returned_context = json.loads(response.context_text)
        
        # Should clear pending_pivot
        assert "pending_pivot" not in returned_context or returned_context.get("pending_pivot") is None
        
        # Should update goal_history
        assert "Show sales" in returned_context["goal_history"]
        
        # Should update goal
        assert returned_context["goal"] == "Employee count"
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    @patch('app.services.generation_service._detect_turn_type_fast')
    def test_correction_updates_adjustments(self, mock_fast, mock_search, mock_vector, mock_llm):
        """Correction turn-type adds entry to adjustments list."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = '{"goal_clear": true, "goal_statement": "Show 2023 sales", "critical_ambiguities": [], "ready_for_search": false, "required_questions": [], "requirements_extracted": [{"type": "time_period", "value": "2023"}]}'
        mock_llm.return_value = mock_llm_instance
        
        mock_fast.return_value = {
            "turn_type": "correction",
            "confidence": 0.85,
            "reasoning": "Correcting year",
            "topic_similarity": 0.8
        }
        
        context = {
            "goal": "Show 2022 sales",
            "selected_tables": [],
            "conversation_history": [],
            "adjustments": []
        }
        
        response = planning_conversation("No, I meant 2023", planning_context=context)
        
        returned_context = json.loads(response.context_text)
        
        # Should add correction to adjustments
        assert len(returned_context["adjustments"]) > 0
        assert "correction" in returned_context["adjustments"][0]["type"]
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    @patch('app.services.generation_service._detect_turn_type_fast')
    def test_refinement_updates_goal_history(self, mock_fast, mock_search, mock_vector, mock_llm):
        """Refinement turn-type updates goal_history with previous goal."""
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = '{"goal_clear": true, "goal_statement": "Show sales by region", "critical_ambiguities": [], "ready_for_search": false, "required_questions": [], "requirements_extracted": [{"type": "grouping", "value": "region"}]}'
        mock_llm.return_value = mock_llm_instance
        
        mock_fast.return_value = {
            "turn_type": "refinement",
            "confidence": 0.80,
            "reasoning": "Adding grouping",
            "topic_similarity": 0.85
        }
        
        context = {
            "goal": "Show sales",
            "selected_tables": [],
            "conversation_history": [],
            "goal_history": [],
            "adjustments": []
        }
        
        response = planning_conversation("break it down by region", planning_context=context)
        
        returned_context = json.loads(response.context_text)
        
        # Should add previous goal to history
        assert "Show sales" in returned_context["goal_history"]
        
        # Should add refinement to adjustments
        assert len(returned_context["adjustments"]) > 0
        assert "refinement" in returned_context["adjustments"][0]["type"]
