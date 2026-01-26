import sys
import os
import logging
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())

from app.models.schemas import GenerateSQLRequest, TableSchema
from app.services import generation_service

# Setup logging
logging.basicConfig(level=logging.INFO)

def reproduce_missing_link():
    print("Testing Context for Disjoint Tables (Categories + Customers)...")
    
    # 1. Mock Schema with disjoint tables and intermediate tables
    # "Seafood" -> Categories
    # "Canada" -> Customers
    # Path: Categories -> Products -> OrderDetails -> Orders -> Customers
    
    t_categories = TableSchema(schema_name="dbo", table_name="Categories", description="Categories of products. pk: CategoryID")
    t_customers = TableSchema(schema_name="dbo", table_name="Customers", description="Customer info. pk: CustomerID")
    
    # Intermediates (usually not discovered by name match)
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
    # Schema search finds nothing generic or maybe same
    mock_vs.search_schemas.return_value = [] 
    # Few shot finds nothing
    mock_vs.search_fewshots.return_value = []
    
    mock_vs.get_all_schemas.return_value = all_schemas
    
    # Replace globals
    original_vs = generation_service.vector_store
    generation_service.vector_store = mock_vs
    
    # Mock LLM to simulate extraction (empty) and SQL gen intent
    mock_llm = MagicMock()
    mock_llm.extract_tables_from_sql.return_value = []
    
    with patch('app.services.generation_service.get_llm_service', return_value=mock_llm):
        
        # We need to spy on 'hydrate_discovery_context' or check the final context passed to LLM
        # But `generate_sql_for_request` does a lot of work. 
        # Let's just run it and check the `context` in the result object
        
        # We also need to mock validate_sql_with_db to avoid actual DB calls
        with patch('app.services.generation_service.validate_sql_with_db', return_value=(False, "Validation Failed: Tables missing", [])):
            req = GenerateSQLRequest(query="How much seafood sold to Canada?")
            response = generation_service.generate_sql_for_request(req)
            
            # Analyze Result
            print("\n--- Analysis ---")
            relevant = response.context_text # This contains the schema text passed to LLM
            
            found_categories = "Table: dbo.Categories" in relevant
            found_customers = "Table: dbo.Customers" in relevant
            found_products = "Table: dbo.Products" in relevant
            found_orders = "Table: dbo.Orders" in relevant
            found_details = "Table: dbo.Order Details" in relevant
            
            print(f"Found Categories: {found_categories}")
            print(f"Found Customers: {found_customers}")
            print(f"Found Products (Intermediate): {found_products}")
            print(f"Found Orders (Intermediate): {found_orders}")
            print(f"Found Order Details (Intermediate): {found_details}")
            
            if found_categories and found_customers and not (found_products and found_orders):
                print("\nFAILURE REPRODUCED: Found disjoint start/end tables but missing intermediate tables.")
            else:
                print("\nContext looks okay or simulation failed to reproduce.")

    generation_service.vector_store = original_vs

if __name__ == "__main__":
    reproduce_missing_link()
