import pytest
from unittest.mock import MagicMock, patch
from app.services.generation_service import generate_sql_for_request, validate_sql_columns
from app.models.schemas import GenerateSQLRequest, DiscoveryContext, TableSchema, ColumnInfo

# Mock helper classes
class MockLLMService:
    def __init__(self):
        self.generate_sql_with_context = MagicMock()
        self._build_system_prompt = MagicMock(return_value="System Prompt")
        self.model = "gpt-4"
        self.client = MagicMock()

@pytest.fixture
def mock_llm_service():
    with patch("app.services.generation_service.llm_service") as mock:
        yield mock

@pytest.fixture
def sample_context():
    return DiscoveryContext(
        relevant_tables=[
            TableSchema(
                schema_name="dbo",
                table_name="Customers",
                columns=[
                    ColumnInfo(name="CustomerID", data_type="nchar"),
                    ColumnInfo(name="CompanyName", data_type="nvarchar")
                ],
                description="Customers table"
            )
        ],
        similar_queries=[]
    )

def test_retry_logic_success(mock_llm_service, sample_context):
    # Setup
    request = GenerateSQLRequest(query="Find customers", context=sample_context)
    
    # Mock return values for generate_sql_with_context
    # 1. Invalid SQL (wrong column)
    # 2. Valid SQL
    mock_llm_service.generate_sql_with_context.side_effect = [
        "SELECT dbo.Customers.WrongColumn FROM dbo.Customers",
        "SELECT dbo.Customers.CompanyName FROM dbo.Customers"
    ]
    
    # Mock validate_sql_columns to behavior correctly with our inputs
    # But since we are testing generation_service which imports validate_sql_columns,
    # we rely on the actual validation logic if we don't mock it.
    # The actual validation logic should correctly identify WrongColumn as invalid and CompanyName as valid.
    
    # Configure mock to return string for system prompt
    mock_llm_service._build_system_prompt.return_value = "System Prompt"

    # Execute
    response = generate_sql_for_request(request)
    
    # Verify
    assert response.sql == "SELECT dbo.Customers.CompanyName FROM dbo.Customers"
    assert "WrongColumn" not in response.sql
    assert mock_llm_service.generate_sql_with_context.call_count == 2
    
    # Verify feedback was passed in the second call
    context_arg = mock_llm_service.generate_sql_with_context.call_args_list[1][0][1]
    assert "Attempt 1 failed validation" in context_arg
    assert "WrongColumn" in context_arg

def test_retry_logic_max_retries_exceeded(mock_llm_service, sample_context):
    # Setup
    request = GenerateSQLRequest(query="Find customers", context=sample_context)
    
    # Mock always returning invalid SQL
    mock_llm_service.generate_sql_with_context.return_value = "SELECT dbo.Customers.WrongColumn FROM dbo.Customers"
    
    # Configure mock to return string for system prompt
    mock_llm_service._build_system_prompt.return_value = "System Prompt"

    # Execute
    response = generate_sql_for_request(request)
    
    # Verify
    assert response.sql == ""
    assert "Failed to generate valid SQL after 5 attempts" in response.explanation
    assert mock_llm_service.generate_sql_with_context.call_count == 5
