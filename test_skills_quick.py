#!/usr/bin/env python3
"""Quick test script for skills service"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.skills_service import get_skills_service
from app.services.discovery_service import perform_three_pronged_discovery, check_smart_threshold
from app.services.llm_service import get_llm_service

def test_skills_loading():
    """Test loading data sources and groups"""
    print("=" * 60)
    print("TEST 1: Loading Data Sources")
    print("=" * 60)
    
    skills = get_skills_service()
    
    # Test 1: Load index
    sources = skills.load_data_sources_index()
    print(f"[SUCCESS] Loaded {len(sources)} data sources")
    for source in sources:
        print(f"  - {source.name} ({source.type})")
        print(f"    Keywords: {', '.join(source.keywords)}")
    
    print()

def test_keyword_search():
    """Test keyword-based search"""
    print("=" * 60)
    print("TEST 2: Keyword Search")
    print("=" * 60)
    
    skills = get_skills_service()
    
    test_queries = [
        "customer orders",
        "product categories",
        "employee information",
        "sales by region"
    ]
    
    for query in test_queries:
        print(f"\n[QUERY] '{query}'")
        result = skills.search_data_groups_by_keywords(query)
        print(f"  Found {len(result.matched_groups)} groups, {len(result.candidate_tables)} tables")
        
        # Show top 3 tables
        for i, table in enumerate(result.candidate_tables[:3], 1):
            print(f"    {i}. {table.schema_name}.{table.table_name} (score: {table.score})")

def test_table_loading():
    """Test loading table schemas"""
    print("\n" + "=" * 60)
    print("TEST 3: Load Table Schemas")
    print("=" * 60)
    
    skills = get_skills_service()
    
    table_names = ["dbo.Customers", "dbo.Orders", "dbo.Products"]
    print(f"\n[INFO] Loading schemas for: {', '.join(table_names)}")
    
    schemas = skills.load_table_schemas(table_names)
    print(f"[SUCCESS] Loaded {len(schemas)} table schemas")
    
    for schema in schemas:
        print(f"\n  Table: {schema.schema_name}.{schema.table_name}")
        print(f"    Type: {schema.table_type}")
        print(f"    Columns: {len(schema.columns)}")
        print(f"    Description preview: {schema.description[:100] if schema.description else 'N/A'}...")

def test_three_pronged_discovery():
    """Test full three-pronged discovery with new strategy"""
    print("\n" + "=" * 60)
    print("TEST 4: Three-Pronged Discovery (NEW STRATEGY)")
    print("=" * 60)
    
    try:
        llm = get_llm_service()
        
        # Test Case 1: Query that might have exact knowledge base match
        test_cases = [
            "Show me customers who ordered products in 1997",
            "List all products and their categories",
            "What are the total sales by region?"
        ]
        
        for query in test_cases:
            print(f"\n{'='*60}")
            print(f"[QUERY] '{query}'")
            print(f"{'='*60}")
            
            print("[INFO] Running three-pronged discovery with new strategy...")
            result = perform_three_pronged_discovery(query, llm)
            
            # Check for exact match
            if result.exact_match_found:
                print("\n[EXACT MATCH FOUND]")
                print(f"  Original Question: {result.exact_match_query.get('question', 'N/A')}")
                print(f"  Match Score: {result.exact_match_query.get('score', 'N/A')}")
                print(f"  SQL Preview: {result.exact_match_query.get('sql_query', 'N/A')[:100]}...")
                print(f"  Tables: {result.exact_match_query.get('tables', [])}")
                print(f"  Merged Candidates: {len(result.merged_candidates)}")
                for i, table in enumerate(result.merged_candidates[:5], 1):
                    print(f"    {i}. {table.schema_name}.{table.table_name} (score: {table.score})")
            else:
                print("\n[NO EXACT MATCH - PROCEEDING TO SKILLS/VALUE DISCOVERY]")
                
            # Check if user selection is required
            if result.requires_user_selection:
                print(f"\n[USER SELECTION REQUIRED]")
                print(f"  Total selection candidates: {len(result.selection_candidates)}")
                print(f"  Skills tables found: {len(result.skills_tables)}")
                print(f"  Value index tables found: {len(result.value_tables)}")
                
                print("\n  Top candidates for user selection:")
                for i, table in enumerate(result.selection_candidates[:10], 1):
                    matched_by = ', '.join(table.matched_by) if table.matched_by else 'unknown'
                    print(f"    {i}. {table.schema_name}.{table.table_name}")
                    print(f"       Score: {table.score}, Matched by: [{matched_by}]")
            else:
                print(f"\n[AUTO-PROCEED - No user selection needed]")
                print(f"  Merged candidates: {len(result.merged_candidates)}")
            
            print(f"\n[SUMMARY]")
            print(f"  - Exact match found: {result.exact_match_found}")
            print(f"  - Requires user selection: {result.requires_user_selection}")
            print(f"  - Skills tables: {len(result.skills_tables)}")
            print(f"  - Value tables: {len(result.value_tables)}")
            print(f"  - Knowledge base tables: {len(result.knowledge_base_tables)}")
            print(f"  - Merged candidates: {len(result.merged_candidates)}")
            print(f"  - Selection candidates: {len(result.selection_candidates)}")
        
    except Exception as e:
        print(f"[ERROR] Three-pronged discovery failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        test_skills_loading()
        test_keyword_search()
        test_table_loading()
        test_three_pronged_discovery()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
