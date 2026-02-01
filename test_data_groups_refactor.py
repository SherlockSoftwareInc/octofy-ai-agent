"""
Test script to verify the .data-groups refactoring works correctly
"""

from pathlib import Path
from app.services.skills_service import SkillsService
from app.services.skills_admin_service import (
    create_data_source, create_data_group, delete_data_group,
    _read_data_groups_file, SKILLS_BASE_PATH
)

def test_load_data_groups_for_source():
    """Test loading data groups for a specific source"""
    print("\n[TEST 1] Loading data groups for Northwind data source")
    
    skills_service = SkillsService()
    groups = skills_service.load_data_groups_for_source("Northwind")
    
    print(f"  Found {len(groups)} data groups")
    
    if len(groups) > 0:
        print(f"  First group: {groups[0].name}")
        print(f"  File path: {groups[0].file_path}")
        print("  [PASS] Successfully loaded data groups from .data-groups file")
    else:
        print("  [FAIL] No groups found")
        return False
    
    return True


def test_read_data_groups_file():
    """Test reading .data-groups file directly"""
    print("\n[TEST 2] Reading .data-groups file directly")
    
    ds_dir = SKILLS_BASE_PATH / "northwind"
    groups = _read_data_groups_file(ds_dir)
    
    print(f"  Found {len(groups)} entries")
    
    if len(groups) > 0:
        name, filename = groups[0]
        print(f"  First entry: {name} | {filename}")
        print("  [PASS] Successfully read .data-groups file")
    else:
        print("  [FAIL] No entries found")
        return False
    
    return True


def test_create_and_delete_data_group():
    """Test creating and deleting a data group updates .data-groups file"""
    print("\n[TEST 3] Creating and deleting a data group")
    
    try:
        # Create a test data group
        print("  Creating test data group...")
        result = create_data_group({
            'name': 'Test Group',
            'data_source': 'Northwind',
            'description': 'Test group for validation',
            'keywords': ['test', 'validation'],
            'category': 'Test',
            'tables': []
        })
        
        print(f"  Created: {result['file_path']}")
        
        # Check if it's in .data-groups file
        ds_dir = SKILLS_BASE_PATH / "northwind"
        groups = _read_data_groups_file(ds_dir)
        
        found = any(filename == '_test-group-group.md' for _, filename in groups)
        
        if found:
            print("  [PASS] Entry added to .data-groups file")
        else:
            print("  [FAIL] Entry NOT found in .data-groups file")
            return False
        
        # Delete the test group
        print("  Deleting test data group...")
        delete_data_group(result['file_path'])
        
        # Check if it's removed from .data-groups file
        groups = _read_data_groups_file(ds_dir)
        found = any(filename == '_test-group-group.md' for _, filename in groups)
        
        if not found:
            print("  [PASS] Entry removed from .data-groups file")
        else:
            print("  [FAIL] Entry still in .data-groups file after deletion")
            return False
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def test_create_data_source_creates_data_groups_file():
    """Test that creating a new data source creates .data-groups file"""
    print("\n[TEST 4] Creating new data source creates .data-groups file")
    
    try:
        # Create test data source
        print("  Creating test data source...")
        result = create_data_source({
            'name': 'Test Source',
            'type': 'SQL Server',
            'description': 'Test source for validation',
            'keywords': ['test'],
            'status': 'Active'
        })
        
        # Check if .data-groups file exists
        ds_dir = SKILLS_BASE_PATH / "test-source"
        data_groups_file = ds_dir / ".data-groups"
        
        if data_groups_file.exists():
            print("  [PASS] .data-groups file created")
            
            # Clean up
            import shutil
            shutil.rmtree(ds_dir)
            print("  Cleaned up test data source")
            
            return True
        else:
            print("  [FAIL] .data-groups file NOT created")
            
            # Clean up anyway
            import shutil
            if ds_dir.exists():
                shutil.rmtree(ds_dir)
            
            return False
            
    except Exception as e:
        print(f"  [ERROR] {e}")
        
        # Clean up
        ds_dir = SKILLS_BASE_PATH / "test-source"
        if ds_dir.exists():
            import shutil
            shutil.rmtree(ds_dir)
        
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing .data-groups Refactoring")
    print("=" * 60)
    
    results = []
    
    results.append(("Load data groups for source", test_load_data_groups_for_source()))
    results.append(("Read .data-groups file", test_read_data_groups_file()))
    results.append(("Create/Delete data group", test_create_and_delete_data_group()))
    results.append(("Create data source", test_create_data_source_creates_data_groups_file()))
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nPassed: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[FAILURE] Some tests failed")


if __name__ == '__main__':
    main()
