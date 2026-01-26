import sys
import os
import logging
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())

from app.models.schemas import GenerateSQLRequest, TableSchema
from app.services import generation_service
print(f"DEBUG: generation_service file: {generation_service.__file__}")

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_ner_discovery_flow():
    print("Testing NER Discovery Flow...")
    
    # Mock Schema
    t_categories = TableSchema(schema_name="dbo", table_name="Categories", description="desc")
    t_customers = TableSchema(schema_name="dbo", table_name="Customers", description="desc")
    t_unrelated = TableSchema(schema_name="dbo", table_name="Unrelated", description="desc")
    
    # Mock Vector Store
    mock_vs = MagicMock()
    mock_vs.get_all_schemas.return_value = [t_categories, t_customers, t_unrelated]
    mock_vs.search_fewshots.return_value = []
    mock_vs.search_schemas.return_value = []
    
    # Configure search_values to return specific results for "Seafood" and "Canada"
    def search_values_side_effect(query, top_k=5):
        if "Seafood" in query:
             return [{"schema_name": "dbo", "table_name": "Categories", "value": "Seafood"}]
        if "Canada" in query:
             return [{"schema_name": "dbo", "table_name": "Customers", "value": "Canada"}]
        return []
    
    mock_vs.search_values.side_effect = search_values_side_effect
    
    # Replace globals
    original_vs = generation_service.vector_store
    generation_service.vector_store = mock_vs
    
    # Mock LLM
    mock_llm = MagicMock()
    # NER Extraction specific return
    mock_llm.extract_filter_values.return_value = ["Seafood", "Canada"]
    mock_llm.extract_tables_from_sql.return_value = []
    mock_llm.suggest_intermediate_tables.return_value = []
    mock_llm.validate_schema_references.return_value = "SCHEMA_COMPLETE: YES"
    mock_llm.generate_sql_with_context.return_value = "SELECT * FROM dbo.Categories"
    
    with patch('app.services.generation_service.get_llm_service', return_value=mock_llm), \
         patch('app.services.generation_service.validate_sql_with_db', return_value=(True, "", [])):
        
        req = GenerateSQLRequest(query="How much seafood sold to Canada?")
        response = generation_service.generate_sql_for_request(req)
        
        # Validation
        print("\n--- Analysis ---")
        
        # Check if NER extracted values
        if mock_llm.extract_filter_values.called:
            print("SUCCESS: NER extraction called.")
        else:
            print("FAILURE: NER extraction NOT called.")

        # Check if search_values was called with specific entities
        calls = [args[0] for args, _ in mock_vs.search_values.call_args_list]
        print(f"Value Search Calls: {calls}")
        if "Seafood" in calls and "Canada" in calls:
             print("SUCCESS: Focused value search performed.")
        else:
             print("FAILURE: Focused value search NOT performed correctly.")
             
        # Check that Categories and Customers made it into the context (Implied by Weight 10)
        context_text = response.context_text or ""
        with open("context.txt", "w", encoding="utf-8") as f:
            f.write(context_text)
            
        if "dbo.Categories" in context_text and "dbo.Customers" in context_text:
             print("SUCCESS: Key tables included in context.")
        else:
             print("FAILURE: Key tables missing from context.")

    generation_service.vector_store = original_vs

if __name__ == "__main__":
    test_ner_discovery_flow()
