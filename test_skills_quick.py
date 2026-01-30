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
    """Test full three-pronged discovery"""
    print("\n" + "=" * 60)
    print("TEST 4: Three-Pronged Discovery")
    print("=" * 60)
    
    try:
        llm = get_llm_service()
        
        query = "Show me customers who ordered products in 1997"
        print(f"\n[QUERY] '{query}'")
        
        print("[INFO] Running three-pronged discovery...")
        result = perform_three_pronged_discovery(query, llm)
        
        print(f"\n[RESULTS]")
        print(f"  Skills tables: {len(result.skills_tables)}")
        print(f"  Value index tables: {len(result.value_tables)}")
        print(f"  Knowledge base tables: {len(result.knowledge_base_tables)}")
        print(f"  Merged candidates: {len(result.merged_candidates)}")
        
        print("\n[TOP CANDIDATES]")
        for i, table in enumerate(result.merged_candidates[:5], 1):
            print(f"  {i}. {table.schema_name}.{table.table_name} (score: {table.score})")
        
        # Test threshold
        print("\n[THRESHOLD CHECK]")
        decision = check_smart_threshold(result.merged_candidates)
        print(f"  Auto-proceed: {decision.auto_proceed}")
        print(f"  Total tables: {decision.total_tables}")
        if not decision.auto_proceed:
            print(f"  Reason: {decision.trigger_reason}")
        
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
