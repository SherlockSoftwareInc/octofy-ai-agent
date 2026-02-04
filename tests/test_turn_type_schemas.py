"""
Tests for turn-type classification data structures.

This module tests the TurnType enum and IntentData Pydantic model
that support turn-type classification in planning mode.
"""

import pytest
from pydantic import ValidationError
from app.models.schemas import TurnType, IntentData


class TestTurnTypeEnum:
    """Test cases for TurnType enum"""
    
    def test_turn_type_enum_values(self):
        """Test that all expected enum values are defined"""
        assert TurnType.REFINEMENT == "refinement"
        assert TurnType.CORRECTION == "correction"
        assert TurnType.PIVOT == "pivot"
        assert TurnType.CONFIRMATION == "confirmation"
        assert TurnType.CLARIFICATION == "clarification"
    
    def test_turn_type_enum_membership(self):
        """Test enum membership checks"""
        assert "refinement" in [t.value for t in TurnType]
        assert "correction" in [t.value for t in TurnType]
        assert "pivot" in [t.value for t in TurnType]
        assert "confirmation" in [t.value for t in TurnType]
        assert "clarification" in [t.value for t in TurnType]
        assert "invalid_type" not in [t.value for t in TurnType]


class TestIntentDataModel:
    """Test cases for IntentData Pydantic model"""
    
    def test_minimal_valid_intent_data(self):
        """Test creating IntentData with minimal required fields"""
        intent = IntentData(
            goal_clear=True,
            goal_statement="Analyze sales data",
            ready_for_search=True,
            turn_type=TurnType.REFINEMENT,
            topic_similarity=0.8,
            confidence_in_classification=0.9
        )
        
        assert intent.goal_clear is True
        assert intent.goal_statement == "Analyze sales data"
        assert intent.ready_for_search is True
        assert intent.turn_type == TurnType.REFINEMENT
        assert intent.topic_similarity == 0.8
        assert intent.confidence_in_classification == 0.9
        
        # Check default values
        assert intent.critical_ambiguities == []
        assert intent.required_questions == []
        assert intent.requirements_extracted == []
        assert intent.reasoning == ""
        assert intent.changed_requirements == []
        assert intent.new_requirements == []
        assert intent.removed_requirements == []
        assert intent.needs_pivot_confirmation is False
    
    def test_full_intent_data_with_all_fields(self):
        """Test creating IntentData with all fields populated"""
        intent = IntentData(
            # Existing fields
            goal_clear=False,
            goal_statement="Sales analysis with filters",
            critical_ambiguities=["Which region?", "What time period?"],
            ready_for_search=False,
            required_questions=[
                {"question": "Which region?", "reason": "Multiple regions available"},
                {"question": "What time period?", "reason": "Unclear scope"}
            ],
            requirements_extracted=[
                {"type": "metric", "value": "sales revenue"},
                {"type": "filter", "value": "North America"}
            ],
            # New turn-type fields
            turn_type=TurnType.CORRECTION,
            topic_similarity=0.6,
            confidence_in_classification=0.85,
            reasoning="User is correcting the region filter",
            changed_requirements=["region: Europe -> North America"],
            new_requirements=["time_period: Q1 2024"],
            removed_requirements=["product_category filter"],
            needs_pivot_confirmation=False
        )
        
        assert intent.goal_clear is False
        assert intent.goal_statement == "Sales analysis with filters"
        assert len(intent.critical_ambiguities) == 2
        assert len(intent.required_questions) == 2
        assert len(intent.requirements_extracted) == 2
        assert intent.turn_type == TurnType.CORRECTION
        assert intent.topic_similarity == 0.6
        assert intent.confidence_in_classification == 0.85
        assert intent.reasoning == "User is correcting the region filter"
        assert len(intent.changed_requirements) == 1
        assert len(intent.new_requirements) == 1
        assert len(intent.removed_requirements) == 1
        assert intent.needs_pivot_confirmation is False
    
    def test_topic_similarity_range_validation(self):
        """Test that topic_similarity must be between 0.0 and 1.0"""
        # Valid values at boundaries
        intent_min = IntentData(
            goal_clear=True,
            goal_statement="Test",
            ready_for_search=True,
            turn_type=TurnType.REFINEMENT,
            topic_similarity=0.0,
            confidence_in_classification=1.0
        )
        assert intent_min.topic_similarity == 0.0
        
        intent_max = IntentData(
            goal_clear=True,
            goal_statement="Test",
            ready_for_search=True,
            turn_type=TurnType.REFINEMENT,
            topic_similarity=1.0,
            confidence_in_classification=1.0
        )
        assert intent_max.topic_similarity == 1.0
        
        # Invalid: below 0.0
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_clear=True,
                goal_statement="Test",
                ready_for_search=True,
                turn_type=TurnType.REFINEMENT,
                topic_similarity=-0.1,
                confidence_in_classification=1.0
            )
        assert "topic_similarity" in str(exc_info.value)
        
        # Invalid: above 1.0
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_clear=True,
                goal_statement="Test",
                ready_for_search=True,
                turn_type=TurnType.REFINEMENT,
                topic_similarity=1.5,
                confidence_in_classification=1.0
            )
        assert "topic_similarity" in str(exc_info.value)
    
    def test_confidence_range_validation(self):
        """Test that confidence_in_classification must be between 0.0 and 1.0"""
        # Valid values at boundaries
        intent_min = IntentData(
            goal_clear=True,
            goal_statement="Test",
            ready_for_search=True,
            turn_type=TurnType.REFINEMENT,
            topic_similarity=0.5,
            confidence_in_classification=0.0
        )
        assert intent_min.confidence_in_classification == 0.0
        
        intent_max = IntentData(
            goal_clear=True,
            goal_statement="Test",
            ready_for_search=True,
            turn_type=TurnType.REFINEMENT,
            topic_similarity=0.5,
            confidence_in_classification=1.0
        )
        assert intent_max.confidence_in_classification == 1.0
        
        # Invalid: below 0.0
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_clear=True,
                goal_statement="Test",
                ready_for_search=True,
                turn_type=TurnType.REFINEMENT,
                topic_similarity=0.5,
                confidence_in_classification=-0.1
            )
        assert "confidence_in_classification" in str(exc_info.value)
        
        # Invalid: above 1.0
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_clear=True,
                goal_statement="Test",
                ready_for_search=True,
                turn_type=TurnType.REFINEMENT,
                topic_similarity=0.5,
                confidence_in_classification=1.1
            )
        assert "confidence_in_classification" in str(exc_info.value)
    
    def test_backward_compatibility_with_existing_fields(self):
        """Test that existing fields work as expected (backward compatibility)"""
        # This mimics the current dictionary-based usage in generation_service.py
        intent = IntentData(
            goal_clear=True,
            goal_statement="Analyze quarterly sales",
            critical_ambiguities=["Which quarter?"],
            ready_for_search=False,
            required_questions=[{"question": "Which quarter?", "reason": "Ambiguous time period"}],
            requirements_extracted=[{"type": "metric", "value": "quarterly_sales"}],
            # New required fields
            turn_type=TurnType.CLARIFICATION,
            topic_similarity=1.0,
            confidence_in_classification=0.95
        )
        
        # Verify existing field behavior
        assert intent.goal_clear is True
        assert intent.goal_statement == "Analyze quarterly sales"
        assert intent.critical_ambiguities == ["Which quarter?"]
        assert intent.ready_for_search is False
        assert len(intent.required_questions) == 1
        assert intent.required_questions[0]["question"] == "Which quarter?"
        assert len(intent.requirements_extracted) == 1
        assert intent.requirements_extracted[0]["type"] == "metric"
    
    def test_turn_type_string_coercion(self):
        """Test that turn_type accepts string values and coerces to enum"""
        intent = IntentData(
            goal_clear=True,
            goal_statement="Test",
            ready_for_search=True,
            turn_type="pivot",  # String value
            topic_similarity=0.5,
            confidence_in_classification=0.9
        )
        
        assert intent.turn_type == TurnType.PIVOT
        assert isinstance(intent.turn_type, TurnType)
    
    def test_invalid_turn_type_raises_error(self):
        """Test that invalid turn_type values raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_clear=True,
                goal_statement="Test",
                ready_for_search=True,
                turn_type="invalid_type",
                topic_similarity=0.5,
                confidence_in_classification=0.9
            )
        assert "turn_type" in str(exc_info.value)
    
    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raise ValidationError"""
        # Missing goal_clear
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_statement="Test",
                ready_for_search=True,
                turn_type=TurnType.REFINEMENT,
                topic_similarity=0.5,
                confidence_in_classification=0.9
            )
        assert "goal_clear" in str(exc_info.value)
        
        # Missing turn_type
        with pytest.raises(ValidationError) as exc_info:
            IntentData(
                goal_clear=True,
                goal_statement="Test",
                ready_for_search=True,
                topic_similarity=0.5,
                confidence_in_classification=0.9
            )
        assert "turn_type" in str(exc_info.value)
    
    def test_pivot_confirmation_flag(self):
        """Test needs_pivot_confirmation flag behavior"""
        # Test pivot with confirmation needed
        intent_pivot = IntentData(
            goal_clear=True,
            goal_statement="Inventory analysis",
            ready_for_search=False,
            turn_type=TurnType.PIVOT,
            topic_similarity=0.1,  # Low similarity indicates topic change
            confidence_in_classification=0.92,
            needs_pivot_confirmation=True
        )
        
        assert intent_pivot.turn_type == TurnType.PIVOT
        assert intent_pivot.needs_pivot_confirmation is True
        assert intent_pivot.topic_similarity == 0.1
        
        # Test non-pivot without confirmation
        intent_refinement = IntentData(
            goal_clear=True,
            goal_statement="Sales analysis for Q1",
            ready_for_search=True,
            turn_type=TurnType.REFINEMENT,
            topic_similarity=0.95,
            confidence_in_classification=0.88,
            needs_pivot_confirmation=False
        )
        
        assert intent_refinement.turn_type == TurnType.REFINEMENT
        assert intent_refinement.needs_pivot_confirmation is False
        assert intent_refinement.topic_similarity == 0.95
