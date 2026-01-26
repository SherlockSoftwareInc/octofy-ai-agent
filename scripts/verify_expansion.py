import sys
import os
import logging
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())

from app.models.schemas import GenerateSQLRequest, TableSchema
from app.services import generation_service

# Setup logging
logging.basicConfig(level=logging.INFO)

def verify_expansion():
    print("Testing Schema Expansion (Categories + ... + Customers)...")
    
    # 1. Mock Schema with disjoint tables and intermediate tables
    t_categories = TableSchema(schema_name="dbo", table_name="Categories", description="Categories of products. pk: CategoryID")
    t_customers = TableSchema(schema_name="dbo", table_name="Customers", description="Customer info. pk: CustomerID")
    t_products = TableSchema(schema_name="dbo", table_name="Products", description="Product info. fk: CategoryID references Categories.")
    t_orders = TableSchema(schema_name="dbo", table_name="Orders", description="Order headers. fk: CustomerID references Customers.")
    t_orderdetails = TableSchema(schema_name="dbo", table_name="Order Details", description="Line items. fk: OrderID references Orders, ProductID references Products.")
    
    all_schemas = [t_categories, t_customers, t_products, t_orders, t_orderdetails]
    
    # 2. Mock Vector Store
    mock_vs = MagicMock()
    # Mocking that Value Search finds Categories (via Seafood) and Customers (via Canada)
    mock_vs.search_values.return_value = [
        {"schema_name": "dbo", "table_name": "Categories", "value": "Seafood"},
        {"schema_name": "dbo", "table_name": "Customers", "value": "Canada"}
    ]
    # Schema search initial finds nothing extra
    mock_vs.search_schemas.return_value = [] 
    
    # Configure search_schemas to return the specific tables when searched by name (during expansion)
    def search_schemas_side_effect(query, top_k=5):
        query = query.lower()
        if "categories" in query: return [t_categories]
        if "customers" in query: return [t_customers]
        if "products" in query: return [t_products]
        if "orders" in query: return [t_orders]
        if "order details" in query: return [t_orderdetails]
        return []
    
    mock_vs.search_schemas.side_effect = search_schemas_side_effect
    
    mock_vs.search_fewshots.return_value = []
    mock_vs.get_all_schemas.return_value = all_schemas
    
    # Replace globals
    original_vs = generation_service.vector_store
    generation_service.vector_store = mock_vs
    
    # 3. Mock LLM
    mock_llm = MagicMock()
    # MOCK THE EXTRACT TABLES RETURN (Empty initially)
    mock_llm.extract_tables_from_sql.return_value = []
    # MOCK THE SUGGEST INTERMEDIATE TABLES RETURN (The Fix)
    mock_llm.suggest_intermediate_tables.return_value = ["dbo.Orders", "dbo.Order Details", "dbo.Products"]
    
    # Mock validation response
    mock_llm.validate_schema_references.return_value = "SCHEMA_COMPLETE: YES"
    # Mock generation response (Fix for TypeError)
    mock_llm.generate_sql_with_context.return_value = "SELECT * FROM dbo.Orders"
    
    with patch('app.services.generation_service.get_llm_service', return_value=mock_llm):
        # Mock actual SQL gen to avoid needing a real model
        # Mock actual SQL gen to avoid needing a real model
        with patch('app.services.generation_service.validate_sql_with_db', return_value=(True, "", [])):
             # Mock the generate call inside validation if needed? 
             # No, we just want to inspect the context passed to the prompt. 
             # But getting the context from the function return (response.context_text) is best.
             
            req = GenerateSQLRequest(query="How much seafood sold to Canada?")
            
            # Since we mocked validate, generate_sql_for_request will proceed to return a response object
            response = generation_service.generate_sql_for_request(req)
            
            # Analyze Result
            print("\n--- Analysis ---")
            context_text = response.context_text or "" # This is the full prompt info
            
            print(f"Explanation: {response.explanation}")
            
            # Check if prompt contains the intermediates
            missing_tables = []
            for t in ["Categories", "Customers", "Products", "Orders", "Order Details"]:
                if t not in context_text and f"[dbo].[{t}]" not in context_text: 
                     # Loose match check
                     if f"dbo.{t}" not in context_text:
                         missing_tables.append(t)
            
            if not missing_tables:
                print("SUCCESS: All intermediate tables found in context!")
            else:
                print(f"FAILURE: Missing tables in context: {missing_tables}")
            
            # Check for Reason Steps instruction
            if "REASONING PROCESS" in context_text:
                print("SUCCESS: Reasoning Process instructions present.")
            else:
                print("FAILURE: Reasoning Process instructions missing.")

            # Check for Value Mappings
            if "VERIFIED DATA MAPPINGS" in context_text:
                 print("SUCCESS: Verified Value Mappings present.")
            else:
                 print("FAILURE: Verified Value Mappings missing.")

    generation_service.vector_store = original_vs

if __name__ == "__main__":
    verify_expansion()
