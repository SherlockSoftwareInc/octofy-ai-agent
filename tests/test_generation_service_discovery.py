import pytest
import re
from unittest.mock import MagicMock, patch
from app.services.generation_service import generate_sql_for_request
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
