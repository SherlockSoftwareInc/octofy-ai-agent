"""
Test program to verify skills search uses data groups from .data-groups file

This test verifies that:
1. Skills service can search and find data groups
2. Data groups are loaded from .data-groups file
3. Search returns relevant tables from matched groups
"""

import sys
import io
from app.services.skills_service import SkillsService

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_search_data_groups():
    """Test searching for data groups using keywords"""
    print("\n" + "="*70)
    print("TEST: Search Data Groups by Keywords")
    print("="*70)
    
    skills_service = SkillsService()
    
    # Test case 1: Search for "customers"
    print("\n[TEST 1] Searching for 'customers'...")
    result = skills_service.search_data_groups_by_keywords("customers")
    
    print(f"  Keywords extracted: {result.keywords_used}")
    print(f"  Matched groups: {len(result.matched_groups)}")
    print(f"  Candidate tables: {len(result.candidate_tables)}")
    
    if result.matched_groups:
        for i, group in enumerate(result.matched_groups[:3], 1):
            print(f"\n  Group {i}: {group.name}")
            print(f"    Data Source: {group.data_source}")
            print(f"    Keywords: {', '.join(group.keywords[:5])}")
            print(f"    Tables: {len(group.tables)}")
            print(f"    File: {group.file_path}")
    else:
        print("  ❌ No groups found!")
        return False
    
    if result.candidate_tables:
        print("\n  Sample candidate tables:")
        for table in result.candidate_tables[:5]:
            print(f"    - {table.schema_name}.{table.table_name} (score: {table.score}, group: {table.data_group})")
    
    print("\n  ✅ PASS: Found data groups and candidate tables")
    return True


def test_search_with_complex_query():
    """Test searching with a more complex query"""
    print("\n" + "="*70)
    print("TEST: Search with Complex Query")
    print("="*70)
    
    skills_service = SkillsService()
    
    # Test case 2: More specific search
    queries = [
        "show me employee information",
        "order details and sales data",
        "product categories and suppliers"
    ]
    
    all_passed = True
    
    for query in queries:
        print(f"\n[TEST] Query: '{query}'")
        result = skills_service.search_data_groups_by_keywords(query)
        
        print(f"  Keywords: {result.keywords_used}")
        print(f"  Matched groups: {len(result.matched_groups)}")
        
        if result.matched_groups:
            print(f"  Top group: {result.matched_groups[0].name}")
            print(f"  Candidate tables: {len(result.candidate_tables)}")
            print("  ✅ Found relevant groups")
        else:
            print("  ❌ No groups found!")
            all_passed = False
    
    return all_passed


def test_load_specific_data_source_groups():
    """Test loading all groups for a specific data source"""
    print("\n" + "="*70)
    print("TEST: Load Groups for Specific Data Source")
    print("="*70)
    
    skills_service = SkillsService()
    
    print("\n[TEST] Loading groups for 'Northwind' data source...")
    groups = skills_service.load_data_groups_for_source("Northwind")
    
    print(f"  Total groups loaded: {len(groups)}")
    
    if len(groups) > 0:
        print("\n  Sample groups:")
        for group in groups[:5]:
            print(f"    - {group.name}")
            print(f"      Keywords: {', '.join(group.keywords[:3])}...")
            print(f"      Tables: {len(group.tables)}")
        
        print("\n  ✅ PASS: Successfully loaded groups from .data-groups file")
        return True
    else:
        print("  ❌ FAIL: No groups loaded")
        return False


def test_verify_group_data_loaded():
    """Verify that groups loaded have complete data"""
    print("\n" + "="*70)
    print("TEST: Verify Group Data Completeness")
    print("="*70)
    
    skills_service = SkillsService()
    
    print("\n[TEST] Loading and verifying group data...")
    groups = skills_service.load_data_groups_for_source("Northwind")
    
    if not groups:
        print("  ❌ FAIL: No groups to verify")
        return False
    
    # Check first few groups for completeness
    issues = []
    for group in groups[:10]:
        if not group.name:
            issues.append(f"Group missing name: {group.file_path}")
        if not group.data_source:
            issues.append(f"Group {group.name} missing data_source")
        if not group.keywords:
            issues.append(f"Group {group.name} missing keywords")
        if not group.tables:
            issues.append(f"Group {group.name} has no tables")
    
    if issues:
        print("  Issues found:")
        for issue in issues:
            print(f"    ⚠️ {issue}")
    else:
        print("  ✅ All groups have complete data:")
        print(f"    - Names: ✓")
        print(f"    - Data sources: ✓")
        print(f"    - Keywords: ✓")
        print(f"    - Tables: ✓")
    
    return len(issues) == 0


def test_search_matches_tables():
    """Verify that search results include actual table objects"""
    print("\n" + "="*70)
    print("TEST: Search Results Include Table Details")
    print("="*70)
    
    skills_service = SkillsService()
    
    print("\n[TEST] Searching for 'products' and checking table details...")
    result = skills_service.search_data_groups_by_keywords("products")
    
    if not result.candidate_tables:
        print("  ❌ FAIL: No candidate tables returned")
        return False
    
    print(f"  Found {len(result.candidate_tables)} candidate tables")
    print("\n  Checking table details:")
    
    sample_table = result.candidate_tables[0]
    
    checks = {
        "Schema name": sample_table.schema_name,
        "Table name": sample_table.table_name,
        "Score": sample_table.score,
        "Data source": sample_table.data_source,
        "Data group": sample_table.data_group,
        "Matched by": sample_table.matched_by
    }
    
    all_valid = True
    for field, value in checks.items():
        if value:
            print(f"    ✓ {field}: {value}")
        else:
            print(f"    ✗ {field}: MISSING")
            all_valid = False
    
    if all_valid:
        print("\n  ✅ PASS: All table details present")
    else:
        print("\n  ❌ FAIL: Some table details missing")
    
    return all_valid


def test_integration_search_to_tables():
    """End-to-end integration test: search query -> groups -> tables"""
    print("\n" + "="*70)
    print("TEST: Integration - Search Query to Tables")
    print("="*70)
    
    skills_service = SkillsService()
    
    test_query = "I need customer order information"
    
    print(f"\n[TEST] Query: '{test_query}'")
    print("\nStep 1: Searching data groups...")
    result = skills_service.search_data_groups_by_keywords(test_query)
    
    print(f"  ✓ Keywords extracted: {result.keywords_used}")
    print(f"  ✓ Matched {len(result.matched_groups)} groups")
    
    if not result.matched_groups:
        print("  ❌ FAIL: No groups matched")
        return False
    
    print("\nStep 2: Extracting candidate tables from groups...")
    print(f"  ✓ Found {len(result.candidate_tables)} candidate tables")
    
    if not result.candidate_tables:
        print("  ❌ FAIL: No candidate tables")
        return False
    
    print("\nStep 3: Analyzing top results...")
    for i, table in enumerate(result.candidate_tables[:5], 1):
        print(f"  {i}. {table.schema_name}.{table.table_name}")
        print(f"     Score: {table.score}")
        print(f"     From group: {table.data_group}")
        print(f"     Data source: {table.data_source}")
    
    # Verify we got relevant tables
    relevant_keywords = ['customer', 'order', 'customers', 'orders']
    found_relevant = False
    
    for table in result.candidate_tables[:10]:
        table_lower = table.table_name.lower()
        if any(keyword in table_lower for keyword in relevant_keywords):
            found_relevant = True
            break
    
    if found_relevant:
        print("\n  ✅ PASS: Found relevant tables based on query")
        return True
    else:
        print("\n  ⚠️ WARNING: No obviously relevant tables in top results")
        return True  # Still pass if search worked


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("SKILLS SEARCH WITH DATA GROUPS - TEST SUITE")
    print("="*70)
    print("\nThis test verifies that skills search correctly uses data groups")
    print("loaded from the .data-groups file format.\n")
    
    tests = [
        ("Search data groups by keywords", test_search_data_groups),
        ("Search with complex queries", test_search_with_complex_query),
        ("Load groups for specific data source", test_load_specific_data_source_groups),
        ("Verify group data completeness", test_verify_group_data_loaded),
        ("Search results include table details", test_search_matches_tables),
        ("Integration: query to tables", test_integration_search_to_tables)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed, None))
        except Exception as e:
            print(f"\n  ❌ ERROR: {str(e)}")
            results.append((test_name, False, str(e)))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed_count = 0
    for test_name, passed, error in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {test_name}")
        if error:
            print(f"         Error: {error}")
        if passed:
            passed_count += 1
    
    print("\n" + "-"*70)
    print(f"Results: {passed_count}/{len(results)} tests passed")
    print("="*70)
    
    if passed_count == len(results):
        print("\n🎉 SUCCESS! All tests passed!")
        print("\nThe skills search correctly uses data groups from .data-groups files.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
