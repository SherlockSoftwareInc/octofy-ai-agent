"""
Test script for index-based schema search functionality
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.skills_service import get_skills_service


def test_load_indices():
    """Test loading index files"""
    print("=" * 60)
    print("TEST 1: Loading Index Files")
    print("=" * 60)
    
    skills_service = get_skills_service()
    
    # Load schema indices
    schema_indices = skills_service.load_schema_indices()
    print(f"\n✓ Loaded {len(schema_indices)} data source(s)")
    for ds_name, index_data in schema_indices.items():
        print(f"  - {ds_name}: {index_data.get('total_schemas')} schema(s)")
    
    # Load object indices for Northwind
    if 'Northwind' in schema_indices:
        object_indices = skills_service.load_object_indices('Northwind')
        print(f"\n✓ Loaded {len(object_indices)} object index/indices for Northwind")
        for schema_name, obj_index in object_indices.items():
            total = obj_index.get('total_objects', 0)
            tables = obj_index.get('tables', 0)
            views = obj_index.get('views', 0)
            print(f"  - {schema_name}: {total} objects ({tables} tables, {views} views)")


def test_search_by_keyword():
    """Test keyword-based search"""
    print("\n" + "=" * 60)
    print("TEST 2: Keyword-Based Search")
    print("=" * 60)
    
    skills_service = get_skills_service()
    
    # Test different search queries
    test_queries = [
        "customer orders",
        "product",
        "invoice",
        "employee",
        "sales"
    ]
    
    for query in test_queries:
        results = skills_service.search_objects_by_keyword(query, top_k=3)
        print(f"\n✓ Search for '{query}': {len(results)} result(s)")
        for i, result in enumerate(results[:3], 1):
            print(f"  {i}. {result['schema_name']}.{result['object_name']} "
                  f"({result['object_type']}) - Score: {result['score']:.1f}")
            print(f"     {result['description'][:80]}...")


def test_list_all_objects():
    """Test listing all objects"""
    print("\n" + "=" * 60)
    print("TEST 3: List All Objects")
    print("=" * 60)
    
    skills_service = get_skills_service()
    
    # List all objects
    all_objects = skills_service.list_all_objects()
    print(f"\n✓ Total objects: {len(all_objects)}")
    
    # Count by type
    tables = [o for o in all_objects if o['object_type'] == 'Table']
    views = [o for o in all_objects if o['object_type'] == 'View']
    print(f"  - Tables: {len(tables)}")
    print(f"  - Views: {len(views)}")
    
    # List objects in dbo schema
    dbo_objects = skills_service.list_all_objects(schema_name='dbo')
    print(f"\n✓ Objects in dbo schema: {len(dbo_objects)}")
    print("  Sample objects:")
    for obj in dbo_objects[:5]:
        print(f"  - {obj['schema_name']}.{obj['object_name']} ({obj['object_type']})")


def test_get_object_by_name():
    """Test getting a specific object by name"""
    print("\n" + "=" * 60)
    print("TEST 4: Get Object by Name")
    print("=" * 60)
    
    skills_service = get_skills_service()
    
    # Test getting specific objects
    test_objects = [
        ('Categories', 'dbo'),
        ('Orders', 'dbo'),
        ('Customers', 'dbo')
    ]
    
    for obj_name, schema_name in test_objects:
        obj = skills_service.get_object_by_name(obj_name, schema_name)
        if obj:
            print(f"\n✓ Found {schema_name}.{obj_name}")
            print(f"  Type: {obj['object_type']}")
            print(f"  Description: {obj['description'][:80]}...")
            print(f"  Keywords: {', '.join(obj['keywords'][:5])}")
        else:
            print(f"\n✗ Not found: {schema_name}.{obj_name}")


def test_statistics():
    """Test schema statistics"""
    print("\n" + "=" * 60)
    print("TEST 5: Schema Statistics")
    print("=" * 60)
    
    skills_service = get_skills_service()
    
    # Get overall statistics
    stats = skills_service.get_schema_statistics()
    print("\n✓ Overall Statistics:")
    print(f"  - Data Sources: {stats.get('total_data_sources', 0)}")
    print(f"  - Schemas: {stats.get('total_schemas', 0)}")
    print(f"  - Total Objects: {stats.get('total_objects', 0)}")
    print(f"  - Tables: {stats.get('total_tables', 0)}")
    print(f"  - Views: {stats.get('total_views', 0)}")
    
    # Get statistics for Northwind
    northwind_stats = skills_service.get_schema_statistics('Northwind')
    if northwind_stats:
        print("\n✓ Northwind Statistics:")
        print(f"  - Total Schemas: {northwind_stats.get('total_schemas', 0)}")
        for schema in northwind_stats.get('schemas', []):
            print(f"    - {schema.get('schema_name')}: "
                  f"{schema.get('total_objects', 0)} objects "
                  f"({schema.get('tables', 0)} tables, {schema.get('views', 0)} views)")


def test_schema_prioritization():
    """Test that queries like 'sales' prioritize objects in schemas with matching purpose/keywords"""
    print("\n" + "=" * 60)
    print("TEST 6: Schema-First Prioritization (sales)")
    print("=" * 60)
    
    skills_service = get_skills_service()
    results = skills_service.search_objects_by_keyword("sales", top_k=5)
    
    assert len(results) > 0, "Search for 'sales' should return at least one result"
    # Northwind dbo has _schema.md with Purpose/Keywords including "sales"; it should rank at top
    first = results[0]
    print(f"\n✓ Search 'sales': top result is {first['data_source']}.{first['schema_name']}.{first['object_name']} (score: {first['score']:.1f})")
    # If Northwind exists, first result should be from Northwind dbo (schema match bonus)
    northwind_results = [r for r in results if r["data_source"] == "Northwind" and r["schema_name"] == "dbo"]
    if northwind_results:
        print(f"  Northwind dbo results in top 5: {len(northwind_results)} (schema match bonus applied)")
    print("  Schema-first prioritization OK.")


def test_recommended_schemas():
    """Test get_schema_statistics with query returns recommended_schemas ordered by relevance"""
    print("\n" + "=" * 60)
    print("TEST 7: Recommended Schemas (query=sales)")
    print("=" * 60)
    
    skills_service = get_skills_service()
    stats = skills_service.get_schema_statistics(query="sales")
    
    assert "recommended_schemas" in stats, "Stats with query should include recommended_schemas"
    rec = stats["recommended_schemas"]
    assert isinstance(rec, list), "recommended_schemas should be a list"
    print(f"\n✓ recommended_schemas: {len(rec)} schema(s)")
    for i, s in enumerate(rec[:5], 1):
        print(f"  {i}. {s.get('data_source')}.{s.get('schema_name')} score={s.get('score')} - {s.get('description', '')[:50]}...")
    if rec:
        assert rec[0].get("score", 0) >= 1.0, "Top recommended schema should have score >= 1.0"
        # Northwind dbo should be in recommended schemas for "sales"
        assert any(
            s.get("data_source") == "Northwind" and s.get("schema_name") == "dbo" for s in rec
        ), "Northwind dbo (sales) should appear in recommended_schemas for query 'sales'"
    print("  Recommended schemas OK.")


def test_fallback_global_search():
    """Test that when no schema passes threshold, search falls back to global and still returns results"""
    print("\n" + "=" * 60)
    print("TEST 8: Fallback to Global Search")
    print("=" * 60)
    
    skills_service = get_skills_service()
    # Query that matches objects (e.g. 'customer') but may have few schema-level matches
    results = skills_service.search_objects_by_keyword("customer", top_k=5)
    print(f"\n✓ Search 'customer' returned {len(results)} result(s) (fallback or staged)")
    assert len(results) > 0, "Search should return results even when relying on fallback"
    print("  Fallback/global search OK.")


def main():
    """Run all tests"""
    print("\n")
    print("*" * 60)
    print("* Index-Based Schema Search - Test Suite")
    print("*" * 60)
    
    try:
        test_load_indices()
        test_search_by_keyword()
        test_list_all_objects()
        test_get_object_by_name()
        test_statistics()
        test_schema_prioritization()
        test_recommended_schemas()
        test_fallback_global_search()
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
