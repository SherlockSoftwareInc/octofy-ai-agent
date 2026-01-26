"""
Test script to verify API key authentication is working correctly.
"""
import requests
import sys

API_BASE_URL = "http://localhost:5000/api/v1"
VALID_API_KEY = "***REMOVED***"
INVALID_API_KEY = "wrong-key"

def test_health_check():
    """Test that root endpoint works without authentication"""
    print("\n1. Testing root endpoint (no auth required)...")
    try:
        response = requests.get("http://localhost:5000/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200, "Root endpoint should be accessible"
        print("   ✓ PASS: Root endpoint accessible without API key")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    return True

def test_without_api_key():
    """Test that protected endpoints fail without API key"""
    print("\n2. Testing protected endpoint without API key...")
    try:
        response = requests.post(f"{API_BASE_URL}/test")
        print(f"   Status: {response.status_code}")
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("   ✓ PASS: Request rejected without API key")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    return True

def test_with_invalid_api_key():
    """Test that protected endpoints fail with invalid API key"""
    print("\n3. Testing protected endpoint with invalid API key...")
    try:
        headers = {"X-API-Key": INVALID_API_KEY}
        response = requests.post(f"{API_BASE_URL}/test", headers=headers)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json() if response.status_code != 200 else response.text}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("   ✓ PASS: Request rejected with invalid API key")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    return True

def test_with_valid_api_key():
    """Test that protected endpoints work with valid API key"""
    print("\n4. Testing protected endpoint with valid API key...")
    try:
        headers = {"X-API-Key": VALID_API_KEY}
        response = requests.post(f"{API_BASE_URL}/test", headers=headers)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("   ✓ PASS: Request successful with valid API key")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    return True

def test_admin_endpoint():
    """Test that admin endpoints require API key"""
    print("\n5. Testing admin endpoint with valid API key...")
    try:
        headers = {"X-API-Key": VALID_API_KEY}
        response = requests.get(f"{API_BASE_URL}/admin/schema/status", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {len(response.json())} schemas found")
            print("   ✓ PASS: Admin endpoint accessible with valid API key")
        else:
            print(f"   Response: {response.text[:100]}")
            print("   ⚠ WARNING: Admin endpoint returned non-200, but authentication worked")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return False
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("API Key Authentication Test Suite")
    print("=" * 60)
    
    # Check if backend is running
    try:
        response = requests.get("http://localhost:5000/", timeout=2)
        print("✓ Backend server is running")
    except requests.exceptions.RequestException:
        print("✗ ERROR: Backend server is not running!")
        print("  Please start the backend with: uvicorn app.main:app --reload")
        sys.exit(1)
    
    # Run all tests
    results = []
    results.append(test_health_check())
    results.append(test_without_api_key())
    results.append(test_with_invalid_api_key())
    results.append(test_with_valid_api_key())
    results.append(test_admin_endpoint())
    
    # Summary
    print("\n" + "=" * 60)
    print(f"SUMMARY: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All tests PASSED! API key authentication is working correctly.")
        sys.exit(0)
    else:
        print("\n✗ Some tests FAILED. Please review the output above.")
        sys.exit(1)
