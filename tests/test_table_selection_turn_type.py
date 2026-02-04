"""
Tests for table selection handling in planning mode.

When users select tables from the UI without entering text, the system should:
1. Detect this as a valid TABLE_SELECTION turn type
2. Update the planning context with selected tables
3. Track confirmed and rejected tables
4. Provide appropriate conversational feedback
5. Continue the planning conversation smoothly
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.generation_service import planning_conversation
from app.models.schemas import TurnType


class TestTableSelectionTurnType:
    """Test suite for table selection without text input"""
    
    def test_empty_query_with_table_selection_detected_as_table_selection(self):
        """When query is empty but tables are selected, should be TABLE_SELECTION turn type"""
        planning_context = {
            "goal": "Analyze sales trends",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 1,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",  # Empty query
                planning_context=planning_context,
                user_selected_tables=["dbo.Sales", "dbo.Products"]
            )
            
            # Should return a response
            assert result is not None
            assert result.query_type == "plan"
            
            # Should have updated context with selected tables
            import json
            updated_context = json.loads(result.context_text)
            assert "Sales" in str(updated_context["selected_tables"])
            assert "Products" in str(updated_context["selected_tables"])
    
    def test_whitespace_query_with_table_selection_treated_as_empty(self):
        """Query with only whitespace should be treated same as empty query"""
        planning_context = {
            "goal": "Revenue analysis",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 0,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="   \t  \n  ",  # Only whitespace
                planning_context=planning_context,
                user_selected_tables=["dbo.Revenue"]
            )
            
            assert result.query_type == "plan"
            import json
            updated_context = json.loads(result.context_text)
            assert "Revenue" in str(updated_context["selected_tables"])
    
    def test_table_selection_tracks_newly_added_tables(self):
        """Should track tables in confirmed_tables when added"""
        planning_context = {
            "goal": "Customer analysis",
            "selected_tables": ["dbo.Customers"],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 1,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=["dbo.Customers", "dbo.Orders", "dbo.Products"]
            )
            
            import json
            updated_context = json.loads(result.context_text)
            
            # Orders and Products are newly added
            confirmed = set(updated_context.get("confirmed_tables", []))
            assert "dbo.Orders" in confirmed
            assert "dbo.Products" in confirmed
            assert "dbo.Customers" not in confirmed  # Was already selected
    
    def test_table_selection_tracks_newly_removed_tables(self):
        """Should track tables in rejected_tables when removed"""
        planning_context = {
            "goal": "Sales analysis",
            "selected_tables": ["dbo.Sales", "dbo.Products", "dbo.Customers"],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 2,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=["dbo.Sales"]  # Removed Products and Customers
            )
            
            import json
            updated_context = json.loads(result.context_text)
            
            rejected = set(updated_context.get("rejected_tables", []))
            assert "dbo.Products" in rejected
            assert "dbo.Customers" in rejected
            assert "dbo.Sales" not in rejected
    
    def test_table_selection_provides_helpful_response_for_single_table(self):
        """When user selects one table, should provide encouraging feedback"""
        planning_context = {
            "goal": "",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 0,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=["dbo.Customers"]
            )
            
            # Should provide helpful feedback mentioning the table
            assert "Customers" in result.explanation
            assert result.explanation != ""  # Not empty
    
    def test_table_selection_provides_helpful_response_for_multiple_tables(self):
        """When user selects multiple tables, should acknowledge the count"""
        planning_context = {
            "goal": "Cross-sell analysis",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 1,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=["dbo.Sales", "dbo.Products", "dbo.Customers"]
            )
            
            # Should mention the count
            assert "3" in result.explanation or "three" in result.explanation.lower()
    
    def test_table_selection_warns_when_all_tables_deselected(self):
        """When user deselects all tables, should provide guidance"""
        planning_context = {
            "goal": "Revenue analysis",
            "selected_tables": ["dbo.Revenue", "dbo.Sales"],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 2,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=[]  # Deselected all
            )
            
            # Should warn about empty selection
            assert "deselected" in result.explanation.lower() or "no" in result.explanation.lower()
    
    def test_table_selection_updates_conversation_history(self):
        """Should add entries to conversation history for table selection"""
        planning_context = {
            "goal": "Product analysis",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [
                {"role": "user", "content": "I want to analyze products", "turn": 0},
                {"role": "assistant", "content": "Great! Let me suggest some tables.", "turn": 0}
            ],
            "turn_count": 1,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=["dbo.Products"]
            )
            
            import json
            updated_context = json.loads(result.context_text)
            
            # Should have added 2 entries (user action + assistant response)
            assert len(updated_context["conversation_history"]) == 4  # 2 original + 2 new
            assert updated_context["turn_count"] == 2  # Incremented
    
    def test_table_selection_generates_synthetic_query_for_additions(self):
        """Should generate descriptive synthetic query when tables are added"""
        planning_context = {
            "goal": "Sales insights",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 0,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        with patch('app.services.generation_service.get_llm_service'), \
             patch('app.services.generation_service.get_vector_store'):
            
            result = planning_conversation(
                query="",
                planning_context=planning_context,
                user_selected_tables=["dbo.Sales"]
            )
            
            import json
            updated_context = json.loads(result.context_text)
            
            # Synthetic query should mention selection
            last_user_message = [msg for msg in updated_context["conversation_history"] if msg["role"] == "user"][-1]
            assert "selected" in last_user_message["content"].lower() or "Sales" in last_user_message["content"]


class TestTableSelectionEdgeCases:
    """Edge cases for table selection handling"""
    
    def test_none_user_selected_tables_doesnt_crash(self):
        """Should handle None gracefully"""
        planning_context = {
            "goal": "Test",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 0,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        mock_llm = Mock()
        mock_llm.chat = Mock(return_value='{"goal_clear": true, "goal_statement": "Test", "critical_ambiguities": [], "ready_for_search": true, "required_questions": [], "requirements_extracted": []}')
        
        with patch('app.services.generation_service.get_llm_service', return_value=mock_llm), \
             patch('app.services.generation_service.get_vector_store'):
            
            # Should not crash with None
            result = planning_conversation(
                query="show me sales data",
                planning_context=planning_context,
                user_selected_tables=None
            )
            
            assert result is not None
    
    def test_empty_list_user_selected_tables_with_text_query_works_normally(self):
        """Empty list with actual query text should process as normal refinement"""
        planning_context = {
            "goal": "Sales analysis",
            "selected_tables": ["dbo.Sales"],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 1,
            "goal_history": [],
            "rejected_tables": set(),
            "confirmed_tables": set(),
            "adjustments": [],
            "last_auto_checked": set()
        }
        
        mock_llm = Mock()
        mock_llm.chat = Mock(return_value='{"goal_clear": true, "goal_statement": "Monthly revenue trends", "critical_ambiguities": [], "ready_for_search": true, "required_questions": [], "requirements_extracted": []}')
        
        with patch('app.services.generation_service.get_llm_service', return_value=mock_llm), \
             patch('app.services.generation_service.get_vector_store'), \
             patch('app.services.generation_service._detect_turn_type_fast', return_value=None), \
             patch('app.services.generation_service._classify_turn_type_llm', return_value={
                 "turn_type": "refinement",
                 "confidence": 0.85,
                 "topic_similarity": 0.9,
                 "reasoning": "User is refining goal"
             }):
            
            result = planning_conversation(
                query="Show me monthly revenue trends",
                planning_context=planning_context,
                user_selected_tables=[]  # Empty but with text query
            )
            
            # Should process normally (not as TABLE_SELECTION)
            assert result is not None
            assert mock_llm.chat.called  # LLM should be called for intent analysis


class TestTurnTypeEnumUpdate:
    """Test that TurnType enum includes TABLE_SELECTION"""
    
    def test_turn_type_enum_has_table_selection(self):
        """TurnType enum should include TABLE_SELECTION value"""
        assert hasattr(TurnType, "TABLE_SELECTION")
        assert TurnType.TABLE_SELECTION.value == "table_selection"
    
    def test_turn_type_table_selection_is_valid_enum_member(self):
        """TABLE_SELECTION should be a valid enum member"""
        all_turn_types = [t.value for t in TurnType]
        assert "table_selection" in all_turn_types
