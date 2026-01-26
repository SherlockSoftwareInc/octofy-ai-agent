import sys
import os
import logging

# Add app to path
sys.path.append(os.getcwd())

from unittest.mock import MagicMock, patch
from app.models.schemas import GenerateSQLRequest, TableSchema

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_rerank_logic():
    print("Testing Re-rank Logic...")
    from app.services.generation_service import rerank_and_select_tables
    
    few_shot = ["dbo.Orders", "dbo.OrderDetails"]
    value_match = ["[dbo].[Orders]", "Products"]
    schema_match = ["dbo.Orders", "dbo.Customers", "dbo.Shippers"]
    
    # Expected scores: 
    # Orders: 2 (few_shot) + 3 (value) + 1 (schema) = 6
    # OrderDetails: 2
    # Products: 3
    # Customers: 1
    # Shippers: 1
    
    result = rerank_and_select_tables(few_shot, value_match, schema_match)
    print(f"Result: {result}")
    
    # Orders should be first
    assert "dbo.Orders" in result[0] or "[dbo].[Orders]" in result[0]
    # Products should be second (score 3)
    # OrderDetails third (score 2)
    print("Re-rank Logic Passed!")

def test_discovery_flow_patched():
    print("\nTesting Discovery Flow (Patched Global)...")
    from app.services import generation_service
    
    # Create mocks
    mock_vs = MagicMock()
    mock_llm = MagicMock()
    
    # Setup behaviors matching the implementation calls
    mock_vs.search_fewshots.return_value = [{"sql_query": "SELECT * FROM Orders", "question": "test"}]
    mock_llm.extract_tables_from_sql.return_value = ["dbo.Orders"]
    mock_vs.search_values.return_value = [{"schema_name": "dbo", "table_name": "Customers"}]
    mock_vs.search_schemas.return_value = [MagicMock(schema_name="dbo", table_name="Products")]
    
    # Mocks for hydration - USE REAL TableSchema objects
    schema_orders = TableSchema(schema_name="dbo", table_name="Orders", description="desc")
    schema_customers = TableSchema(schema_name="dbo", table_name="Customers", description="desc")
    schema_products = TableSchema(schema_name="dbo", table_name="Products", description="desc")
    
    # Note: get_all_schemas is expected to return TableSchema objects
    mock_vs.get_all_schemas.return_value = [schema_orders, schema_customers, schema_products]

    # Replace globals
    original_vs = generation_service.vector_store
    generation_service.vector_store = mock_vs
    
    # Mock calls inside the function
    with patch('app.services.generation_service.get_llm_service', return_value=mock_llm), \
         patch('app.services.generation_service.validate_sql_with_db', return_value=(True, "", [])):
        
        mock_llm.generate_sql_with_context.return_value = "SELECT * FROM dbo.Orders"
        mock_llm.validate_schema_references.return_value = "SCHEMA_COMPLETE: YES"
        
        # Run
        req = GenerateSQLRequest(query="Show me orders")
        result = generation_service.generate_sql_for_request(req)
        
        # Verification
        print("Calls made:")
        print(f"FewShot: {mock_vs.search_fewshots.called}")
        print(f"Extract: {mock_llm.extract_tables_from_sql.called}")
        print(f"Value: {mock_vs.search_values.called}")
        print(f"Schema: {mock_vs.search_schemas.called}")
        print(f"Hydration (get_all): {mock_vs.get_all_schemas.called}")
        
        # Check result
        print(f"Result explanation starts with: {result.explanation[:50]}")
        
    # Restore
    generation_service.vector_store = original_vs

if __name__ == "__main__":
    try:
        from app.services import generation_service
        test_rerank_logic()
        test_discovery_flow_patched()
        print("\nALL TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
