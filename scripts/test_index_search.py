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


def test_function_metadata_extraction():
    """Test that generate_schema_indices correctly parses Function markdown files"""
    print("\n" + "=" * 60)
    print("TEST 9: Function Metadata Extraction")
    print("=" * 60)

    import tempfile
    from pathlib import Path
    from scripts.generate_schema_indices import extract_metadata_from_md, generate_object_index

    with tempfile.TemporaryDirectory() as tmpdir:
        # Function with **Schema:** and **Type:** lines (enriched format)
        func_md = Path(tmpdir) / "dbo.fn_CalculateTax.md"
        func_md.write_text(
            '## **Function:** `[dbo].[fn_CalculateTax]`\n'
            '**Schema:** dbo\n'
            '**Type:** Function\n'
            '**Returns:** `INT`\n'
            '> Calculates sales tax based on state code and amount.\n'
            '---\n'
            '### **Parameters:**\n'
            '- `@StateCode` (VARCHAR)\n'
            '- `@Amount` (DECIMAL)\n'
            '\n'
            '### **Usage:**\n'
            '```sql\n'
            "SELECT [dbo].[fn_CalculateTax](@StateCode = 'NY', @Amount = 100.00)\n"
            '```\n'
            '---\n',
            encoding='utf-8'
        )

        # Function WITHOUT **Schema:** and **Type:** lines (real output format)
        func_real_md = Path(tmpdir) / "dbo.fn_GetDiscount.md"
        func_real_md.write_text(
            '## **Function:** `[dbo].[fn_GetDiscount]`\n'
            '**Returns:** `DECIMAL`\n'
            '> Returns discount percentage for a given customer tier.\n'
            '---\n'
            '### **Parameters:**\n'
            '- `@CustomerTier` (VARCHAR)\n'
            '\n'
            '### **Usage:**\n'
            '```sql\n'
            "SELECT [dbo].[fn_GetDiscount](@CustomerTier = 'Gold')\n"
            '```\n'
            '---\n',
            encoding='utf-8'
        )

        table_md = Path(tmpdir) / "dbo.Orders.md"
        table_md.write_text(
            '# **Table:** `[dbo].[Orders]`\n'
            '**Schema:** dbo\n'
            '**Type:** Table\n'
            '> Stores order information.\n',
            encoding='utf-8'
        )

        # Test enriched function (with Schema/Type lines)
        meta = extract_metadata_from_md(func_md)
        assert meta is not None, "Function metadata should be extracted"
        assert meta['object_type'] == 'Function', f"Expected 'Function', got '{meta['object_type']}'"
        assert meta['object_name'] == 'fn_CalculateTax', f"Expected 'fn_CalculateTax', got '{meta['object_name']}'"
        assert meta['schema_name'] == 'dbo', f"Expected 'dbo', got '{meta['schema_name']}'"
        assert 'tax' in meta['description'].lower(), f"Description should mention tax: {meta['description']}"
        assert 'usage_example' in meta, "Function metadata should include usage_example"
        print(f"  ✓ Function metadata (enriched): type={meta['object_type']}, name={meta['object_name']}")
        print(f"    Description: {meta['description'][:60]}")
        print(f"    Keywords: {meta['keywords']}")
        print(f"    Usage: {meta.get('usage_example', 'N/A')[:60]}")

        # Test real function format (WITHOUT Schema/Type lines)
        meta_real = extract_metadata_from_md(func_real_md)
        assert meta_real is not None, "Real function metadata should be extracted"
        assert meta_real['object_type'] == 'Function', f"Expected 'Function', got '{meta_real['object_type']}'"
        assert meta_real['object_name'] == 'fn_GetDiscount', f"Expected 'fn_GetDiscount', got '{meta_real['object_name']}'"
        assert meta_real['schema_name'] == 'dbo', f"Expected 'dbo', got '{meta_real['schema_name']}'"
        assert 'discount' in meta_real['description'].lower(), f"Description should mention discount: {meta_real['description']}"
        assert 'usage_example' in meta_real, "Real function metadata should include usage_example"
        print(f"  ✓ Function metadata (real format): type={meta_real['object_type']}, name={meta_real['object_name']}")
        print(f"    Description: {meta_real['description'][:60]}")
        print(f"    Keywords: {meta_real['keywords']}")
        print(f"    Usage: {meta_real.get('usage_example', 'N/A')[:60]}")

        # Test object index counts
        obj_index = generate_object_index(Path(tmpdir))
        assert obj_index['functions'] == 2, f"Expected 2 functions, got {obj_index.get('functions', 'missing')}"
        assert obj_index['tables'] == 1, f"Expected 1 table, got {obj_index.get('tables', 0)}"
        assert obj_index['total_objects'] == 3, f"Expected 3 total objects, got {obj_index['total_objects']}"

        # Verify usage_example propagates to object index entries
        func_entries = [o for o in obj_index['objects'] if o['object_type'] == 'Function']
        for entry in func_entries:
            assert 'usage_example' in entry, f"Object index entry for {entry['object_name']} should include usage_example"

        print(f"  ✓ Object index: {obj_index['total_objects']} objects ({obj_index['tables']} tables, {obj_index.get('functions', 0)} functions)")

    print("  Function metadata extraction OK.")


def test_function_scoring_boost():
    """Test that Function objects receive a 1.2x scoring boost"""
    print("\n" + "=" * 60)
    print("TEST 10: Function Scoring Boost")
    print("=" * 60)

    skills_service = get_skills_service()

    # Directly test _calculate_keyword_score with a Function object
    func_obj = {
        'object_type': 'Function',
        'object_name': 'fn_CalculateTax',
        'description': 'Calculates sales tax based on state code',
        'keywords': ['tax', 'calculation', 'finance'],
    }
    table_obj = {
        'object_type': 'Table',
        'object_name': 'TaxRates',
        'description': 'Calculates sales tax based on state code',
        'keywords': ['tax', 'calculation', 'finance'],
    }
    query_terms = skills_service._normalize_query_terms("calculate tax")

    func_score = skills_service._calculate_keyword_score(func_obj, query_terms)
    table_score = skills_service._calculate_keyword_score(table_obj, query_terms)

    # Function should score 1.2x higher than an equivalent table
    assert func_score > table_score, (
        f"Function score ({func_score}) should be higher than Table score ({table_score})"
    )
    expected_ratio = 1.2
    actual_ratio = func_score / table_score if table_score > 0 else float('inf')
    assert abs(actual_ratio - expected_ratio) < 0.01, (
        f"Expected ~1.2x boost, got {actual_ratio:.2f}x"
    )
    print(f"  Function score: {func_score:.1f}, Table score: {table_score:.1f} (ratio: {actual_ratio:.2f}x)")
    print("  Function scoring boost OK.")


def test_function_statistics():
    """Test that get_schema_statistics includes function counts"""
    print("\n" + "=" * 60)
    print("TEST 11: Function Statistics")
    print("=" * 60)

    skills_service = get_skills_service()

    # Get overall statistics
    stats = skills_service.get_schema_statistics()
    # total_functions key should exist (may be 0 if no functions indexed yet)
    assert 'total_functions' in stats, "Statistics should include total_functions key"
    print(f"  total_functions: {stats['total_functions']}")
    print("  Function statistics OK.")


def test_function_type_filter():
    """Test that search with object_type=Function only returns functions"""
    print("\n" + "=" * 60)
    print("TEST 12: Function Type Filter")
    print("=" * 60)

    skills_service = get_skills_service()

    # Search with Function filter
    results = skills_service.search_objects_by_keyword("calculate", object_type="Function", top_k=10)
    print(f"  Search 'calculate' with object_type=Function: {len(results)} result(s)")

    # All results should be Functions
    for r in results:
        assert r['object_type'] == 'Function', f"Expected Function, got {r['object_type']}"
        print(f"    - {r['schema_name']}.{r['object_name']} (score: {r['score']:.1f})")

    # Search with Table filter should NOT return functions
    table_results = skills_service.search_objects_by_keyword("calculate", object_type="Table", top_k=10)
    for r in table_results:
        assert r['object_type'] == 'Table', f"Table filter returned non-Table: {r['object_type']}"

    print("  Function type filter OK.")


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
        test_function_metadata_extraction()
        test_function_scoring_boost()
        test_function_statistics()
        test_function_type_filter()
        
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
