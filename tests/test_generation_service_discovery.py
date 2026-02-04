import pytest
import re
from unittest.mock import MagicMock, patch
from app.services.generation_service import generate_sql_for_request, planning_conversation
from app.models.schemas import GenerateSQLRequest, DiscoveryContext, TableSchema, ColumnInfo, DiscoveryResponse
from app.services.discovery_service import perform_discovery, DiscoveryRequest

@pytest.fixture
def mock_llm_service():
    with patch("app.services.generation_service.llm_service") as mock:
        yield mock

@pytest.fixture
def mock_discovery_service():
    with patch("app.services.generation_service.perform_discovery") as mock:
        yield mock

@pytest.fixture
def initial_context():
    return DiscoveryContext(
        relevant_tables=[
            TableSchema(
                schema_name="dbo",
                table_name="Customers",
                columns=[ColumnInfo(name="CustomerID", data_type="nchar")],
                description="Customers table"
            )
        ],
        similar_queries=[]
    )

def test_retry_with_discovery(mock_llm_service, mock_discovery_service, initial_context):
    request = GenerateSQLRequest(query="Find missing products", context=initial_context)
    
    # Mock LLM to fail first with missing column, then succeed
    mock_llm_service.generate_sql_with_context.side_effect = [
        "SELECT dbo.Customers.MissingColumn FROM dbo.Customers",  # Invalid (qualified)
        "SELECT NewColumn FROM dbo.NewTable"        # Valid after discovery
    ]
    
    # Mock system prompt
    mock_llm_service._build_system_prompt.return_value = "System Prompt"

    # Mock discovery to return a new table for the missing column
    new_table = TableSchema(
        schema_name="dbo",
        table_name="NewTable",
        columns=[ColumnInfo(name="NewColumn", data_type="int")],
        description="New Table Description"
    )
    
    mock_discovery_service.return_value = DiscoveryResponse(
        query="dbo.Customers.MissingColumn",
        reasoning="Found it",
        context=DiscoveryContext(relevant_tables=[new_table], similar_queries=[])
    )
    
    # Execute
    # The validation will now catch dbo.Customers.MissingColumn because it has dots.
    
    response = generate_sql_for_request(request)
    
    # Verify
    assert response.sql == "SELECT NewColumn FROM dbo.NewTable"
    
    # Verify discovery was called for "MissingColumn"
    mock_discovery_service.assert_called()
    call_args = mock_discovery_service.call_args[0][0]
    assert call_args.query == "dbo.Customers.MissingColumn"
    
    # Verify context provided to LLM in second attempt contained the new table info
    second_call_context = mock_llm_service.generate_sql_with_context.call_args_list[1][0][1]
    assert "found some additional tables" in second_call_context
    assert "NewTable" in second_call_context

def test_retry_instruction_content(mock_llm_service, mock_discovery_service, initial_context):
    request = GenerateSQLRequest(query="Find total sales", context=initial_context)
    
    # Configure mock prompt
    mock_llm_service._build_system_prompt.return_value = "System Prompt"

    # Mock LLM invalid then valid
    mock_llm_service.generate_sql_with_context.side_effect = [
        "SELECT dbo.Customers.TotalSales FROM dbo.Customers",  # Invalid (qualified strings trigger validation)
        "SELECT SUM(Amount) FROM dbo.Orders"  # Valid
    ]
    
    # Mock validation failure then success
    # We rely on real validation which will fail for TotalSales if it's not in initial_context (it isn't)
    
    # Execute
    generate_sql_for_request(request)
    
    # Verify instruction is in the second call's context
    second_call_context = mock_llm_service.generate_sql_with_context.call_args_list[1][0][1]
    expected_instruction = "IMPORTANT: If the column you are looking for does not exist, check if you can use standard SQL functions (SUM, COUNT, AVG, MAX, MIN)"
    assert expected_instruction in second_call_context


# Task 6: Tests for context initialization with new fields
class TestPlanningContextInitialization:
    """Test planning_conversation context initialization with intent tracking fields."""
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    def test_initializes_new_fields_for_empty_context(self, mock_search, mock_vector, mock_llm):
        """Initializes new intent tracking fields when starting fresh."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = '{"goal_clear": true, "goal_statement": "Test", "critical_ambiguities": [], "ready_for_search": false, "required_questions": [], "requirements_extracted": []}'
        mock_llm.return_value = mock_llm_instance
        
        # Execute with no planning_context
        response = planning_conversation("Show sales", planning_context=None)
        
        # Parse the returned context
        import json
        context = json.loads(response.context_text)
        
        # Verify new fields are initialized
        assert "goal_history" in context
        assert "rejected_tables" in context
        assert "confirmed_tables" in context
        assert "adjustments" in context
        assert "last_auto_checked" in context
        
        # Verify they're initialized as empty lists (serialized from sets)
        assert context["goal_history"] == []
        assert context["rejected_tables"] == []
        assert context["confirmed_tables"] == []
        assert context["adjustments"] == []
        assert context["last_auto_checked"] == []
    
    @patch('app.services.generation_service.get_llm_service')
    @patch('app.services.generation_service.get_vector_store')
    @patch('app.services.generation_service.search_data_objects')
    def test_converts_lists_to_sets_for_backward_compatibility(self, mock_search, mock_vector, mock_llm):
        """Converts list fields to sets when loading existing context (backward compatibility)."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat.return_value = '{"goal_clear": true, "goal_statement": "Test", "critical_ambiguities": [], "ready_for_search": false, "required_questions": [], "requirements_extracted": []}'
        mock_llm.return_value = mock_llm_instance
        
        # Create context with lists (old format)
        existing_context = {
            "goal": "Show sales",
            "selected_tables": [],
            "suggested_tables": [],
            "requirements": [],
            "conversation_history": [],
            "turn_count": 1,
            "rejected_tables": ["table1", "table2"],  # List format (old)
            "confirmed_tables": ["table3"],  # List format (old)
            "last_auto_checked": ["table4"]  # List format (old)
        }
        
        # Execute
        response = planning_conversation("Add filter", planning_context=existing_context)
        
        # Parse returned context
        import json
        context = json.loads(response.context_text)
        
        # Verify they're still lists in JSON output (sets converted back to lists)
        assert isinstance(context["rejected_tables"], list)
        assert isinstance(context["confirmed_tables"], list)
        assert isinstance(context["last_auto_checked"], list)
        
        # Verify content is preserved
        assert set(context["rejected_tables"]) == {"table1", "table2"}
        assert set(context["confirmed_tables"]) == {"table3"}
        assert set(context["last_auto_checked"]) == {"table4"}

