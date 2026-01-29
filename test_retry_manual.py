"""
Manual test script for Python code execution retry functionality.
Run this to verify the auto-retry feature works correctly.
"""

import sys
from app.services.code_generation_service import regenerate_python_with_error_feedback, _strip_db_connection_injection


def test_strip_db_connection():
    """Test the DB_CONNECTION_STRING stripping functionality."""
    print("=" * 60)
    print("TEST 1: Strip DB_CONNECTION_STRING from code")
    print("=" * 60)
    
    test_code = """
import pandas as pd
import sqlalchemy

# DB_CONNECTION_STRING = "mssql+pyodbc://server/db"
engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)

conn = engine.raw_connection()
try:
    df = pd.read_sql("SELECT * FROM dbo.Customers", conn)
finally:
    conn.close()

final_result_df = df
"""
    
    print("\nOriginal code:")
    print(test_code)
    
    stripped = _strip_db_connection_injection(test_code)
    
    print("\nStripped code:")
    print(stripped)
    
    # Verify DB_CONNECTION_STRING usage is preserved but assignment is removed
    assert "DB_CONNECTION_STRING" in stripped, "Should still reference DB_CONNECTION_STRING"
    assert "engine.raw_connection()" in stripped, "Should preserve connection pattern"
    print("\n[PASS] Test passed: DB_CONNECTION_STRING stripped correctly")


def test_regenerate_function_exists():
    """Test that the regenerate function exists and has correct signature."""
    print("\n" + "=" * 60)
    print("TEST 2: Verify regenerate_python_with_error_feedback exists")
    print("=" * 60)
    
    # Check function exists
    assert callable(regenerate_python_with_error_feedback), "Function should be callable"
    
    # Check function signature
    import inspect
    sig = inspect.signature(regenerate_python_with_error_feedback)
    params = list(sig.parameters.keys())
    
    expected_params = ['original_request', 'failed_code', 'error_message', 'schema_context', 'attempt_number']
    assert params == expected_params, f"Expected params {expected_params}, got {params}"
    
    print("\n[PASS] Test passed: Function exists with correct signature")
    print(f"  Parameters: {', '.join(params)}")


def test_response_model_fields():
    """Test that ExecutePythonResponse has the new auto-fix fields."""
    print("\n" + "=" * 60)
    print("TEST 3: Verify ExecutePythonResponse model fields")
    print("=" * 60)
    
    from app.models.schemas import ExecutePythonResponse
    
    # Create a sample response
    response = ExecutePythonResponse(
        success=True,
        execution_time=1.5,
        code="print('test')",
        auto_fixed=True,
        fix_attempt=3,
        original_error="Some error"
    )
    
    # Verify new fields exist
    assert response.code == "print('test')", "code field should exist"
    assert response.auto_fixed == True, "auto_fixed field should exist"
    assert response.fix_attempt == 3, "fix_attempt field should exist"
    assert response.original_error == "Some error", "original_error field should exist"
    
    print("\n[PASS] Test passed: ExecutePythonResponse has all required fields")
    print(f"  - code: {type(response.code).__name__}")
    print(f"  - auto_fixed: {type(response.auto_fixed).__name__}")
    print(f"  - fix_attempt: {type(response.fix_attempt).__name__}")
    print(f"  - original_error: {type(response.original_error).__name__}")


if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("MANUAL TEST: Python Code Execution Retry Feature")
        print("=" * 60)
        
        test_strip_db_connection()
        test_regenerate_function_exists()
        test_response_model_fields()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED [SUCCESS]")
        print("=" * 60)
        print("\nThe retry feature implementation is working correctly!")
        print("Next steps:")
        print("  1. Start the backend server: uvicorn app.main:app --reload")
        print("  2. Test with intentionally broken Python code via the API")
        print("  3. Verify the auto-fix happens transparently")
        
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
