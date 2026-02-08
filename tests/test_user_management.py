"""
Comprehensive test script for user management system.

Tests all endpoints and authentication methods.
"""
import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Test results
test_results = []
admin_token = None
admin_api_key = None
test_user_id = None
test_conversation_id = None


def log_test(test_name, success, details=""):
    """Log test result."""
    status = "[PASS]" if success else "[FAIL]"
    result = {
        "test": test_name,
        "success": success,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    print(f"{status} - {test_name}")
    if details:
        print(f"  Details: {details}")


def test_1_admin_login():
    """Test admin login with username and password."""
    global admin_token, admin_api_key
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        
        if response.status_code == 200:
            data = response.json()
            admin_token = data.get("access_token")
            
            if admin_token and data.get("user", {}).get("role") == "admin":
                log_test("Admin Login", True, f"Token received, user role: admin")
                return True
            else:
                log_test("Admin Login", False, "Token or role missing")
                return False
        else:
            log_test("Admin Login", False, f"Status: {response.status_code}, {response.text}")
            return False
    
    except Exception as e:
        log_test("Admin Login", False, f"Exception: {str(e)}")
        return False


def test_2_get_current_user():
    """Test getting current user info with JWT token."""
    global admin_api_key
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            admin_api_key = data.get("api_key")
            
            if admin_api_key and data.get("username") == ADMIN_USERNAME:
                log_test("Get Current User", True, f"API Key: {admin_api_key[:20]}...")
                return True
            else:
                log_test("Get Current User", False, "API key or username missing")
                return False
        else:
            log_test("Get Current User", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Get Current User", False, f"Exception: {str(e)}")
        return False


def test_3_api_key_authentication():
    """Test API key authentication."""
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"X-API-Key": admin_api_key}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("username") == ADMIN_USERNAME:
                log_test("API Key Authentication", True, "API key auth successful")
                return True
            else:
                log_test("API Key Authentication", False, "Wrong user returned")
                return False
        else:
            log_test("API Key Authentication", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("API Key Authentication", False, f"Exception: {str(e)}")
        return False


def test_4_create_user():
    """Test creating a new user (admin only)."""
    global test_user_id
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123",
                "full_name": "Test User",
                "role": "user"
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            test_user_id = data.get("id")
            
            if test_user_id and data.get("username") == "testuser":
                log_test("Create User", True, f"User ID: {test_user_id}")
                return True
            else:
                log_test("Create User", False, "User ID or username missing")
                return False
        else:
            log_test("Create User", False, f"Status: {response.status_code}, {response.text}")
            return False
    
    except Exception as e:
        log_test("Create User", False, f"Exception: {str(e)}")
        return False


def test_5_list_users():
    """Test listing all users (admin only)."""
    try:
        response = requests.get(
            f"{BASE_URL}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            users = data.get("users", [])
            total = data.get("total", 0)
            
            if total >= 2:  # At least admin + testuser
                log_test("List Users", True, f"Found {total} users")
                return True
            else:
                log_test("List Users", False, f"Expected 2+ users, found {total}")
                return False
        else:
            log_test("List Users", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("List Users", False, f"Exception: {str(e)}")
        return False


def test_6_update_user_profile():
    """Test updating own profile."""
    try:
        response = requests.put(
            f"{BASE_URL}/users/me",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"full_name": "Updated Admin Name"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("full_name") == "Updated Admin Name":
                log_test("Update Profile", True, "Profile updated successfully")
                return True
            else:
                log_test("Update Profile", False, "Full name not updated")
                return False
        else:
            log_test("Update Profile", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Update Profile", False, f"Exception: {str(e)}")
        return False


def test_7_regenerate_api_key():
    """Test regenerating API key."""
    global admin_api_key
    old_key = admin_api_key
    
    try:
        response = requests.post(
            f"{BASE_URL}/users/me/regenerate-api-key",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            new_key = data.get("api_key")
            
            if new_key and new_key != old_key:
                admin_api_key = new_key
                log_test("Regenerate API Key", True, f"New key: {new_key[:20]}...")
                return True
            else:
                log_test("Regenerate API Key", False, "Key unchanged or missing")
                return False
        else:
            log_test("Regenerate API Key", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Regenerate API Key", False, f"Exception: {str(e)}")
        return False


def test_8_create_conversation():
    """Test creating a conversation."""
    global test_conversation_id
    
    try:
        response = requests.post(
            f"{BASE_URL}/conversations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test Conversation",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, this is a test message",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                ]
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            test_conversation_id = data.get("id")
            
            if test_conversation_id and data.get("title") == "Test Conversation":
                log_test("Create Conversation", True, f"Conversation ID: {test_conversation_id}")
                return True
            else:
                log_test("Create Conversation", False, "ID or title missing")
                return False
        else:
            log_test("Create Conversation", False, f"Status: {response.status_code}, {response.text}")
            return False
    
    except Exception as e:
        log_test("Create Conversation", False, f"Exception: {str(e)}")
        return False


def test_9_list_conversations():
    """Test listing conversations."""
    try:
        response = requests.get(
            f"{BASE_URL}/conversations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            conversations = data.get("conversations", [])
            total = data.get("total", 0)
            
            if total >= 1:
                log_test("List Conversations", True, f"Found {total} conversation(s)")
                return True
            else:
                log_test("List Conversations", False, f"Expected 1+ conversations, found {total}")
                return False
        else:
            log_test("List Conversations", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("List Conversations", False, f"Exception: {str(e)}")
        return False


def test_10_get_conversation():
    """Test getting a specific conversation."""
    try:
        response = requests.get(
            f"{BASE_URL}/conversations/{test_conversation_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            messages = data.get("messages", [])
            
            if len(messages) >= 1 and data.get("title") == "Test Conversation":
                log_test("Get Conversation", True, f"{len(messages)} message(s) retrieved")
                return True
            else:
                log_test("Get Conversation", False, "Messages or title missing")
                return False
        else:
            log_test("Get Conversation", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Get Conversation", False, f"Exception: {str(e)}")
        return False


def test_11_update_conversation():
    """Test updating a conversation."""
    try:
        response = requests.put(
            f"{BASE_URL}/conversations/{test_conversation_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "Updated Conversation Title"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("title") == "Updated Conversation Title":
                log_test("Update Conversation", True, "Title updated successfully")
                return True
            else:
                log_test("Update Conversation", False, "Title not updated")
                return False
        else:
            log_test("Update Conversation", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Update Conversation", False, f"Exception: {str(e)}")
        return False


def test_12_role_based_access_control():
    """Test that regular users cannot access admin endpoints."""
    try:
        # Login as test user
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        
        if login_response.status_code != 200:
            log_test("RBAC - User Login", False, "Could not login as testuser")
            return False
        
        user_token = login_response.json().get("access_token")
        
        # Try to access admin endpoint
        admin_response = requests.get(
            f"{BASE_URL}/admin/users",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        
        if admin_response.status_code == 403:
            log_test("RBAC - Access Control", True, "User correctly denied admin access")
            return True
        else:
            log_test("RBAC - Access Control", False, f"Expected 403, got {admin_response.status_code}")
            return False
    
    except Exception as e:
        log_test("RBAC - Access Control", False, f"Exception: {str(e)}")
        return False


def test_13_delete_conversation():
    """Test deleting a conversation."""
    try:
        response = requests.delete(
            f"{BASE_URL}/conversations/{test_conversation_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 204:
            log_test("Delete Conversation", True, "Conversation deleted successfully")
            return True
        else:
            log_test("Delete Conversation", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Delete Conversation", False, f"Exception: {str(e)}")
        return False


def test_14_delete_user():
    """Test deleting a user (admin only)."""
    try:
        response = requests.delete(
            f"{BASE_URL}/admin/users/{test_user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 204:
            log_test("Delete User", True, "User deleted successfully")
            return True
        else:
            log_test("Delete User", False, f"Status: {response.status_code}")
            return False
    
    except Exception as e:
        log_test("Delete User", False, f"Exception: {str(e)}")
        return False


def run_all_tests():
    """Run all tests in sequence."""
    print("=" * 80)
    print("USER MANAGEMENT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 80)
    print()
    
    # Wait for server to be ready
    print("Waiting for server to start...")
    time.sleep(3)
    
    # Run tests
    tests = [
        test_1_admin_login,
        test_2_get_current_user,
        test_3_api_key_authentication,
        test_4_create_user,
        test_5_list_users,
        test_6_update_user_profile,
        test_7_regenerate_api_key,
        test_8_create_conversation,
        test_9_list_conversations,
        test_10_get_conversation,
        test_11_update_conversation,
        test_12_role_based_access_control,
        test_13_delete_conversation,
        test_14_delete_user,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[FAIL] - {test_func.__name__}: {str(e)}")
            failed += 1
        
        time.sleep(0.5)  # Small delay between tests
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed / (passed + failed) * 100):.1f}%")
    print("=" * 80)
    
    # Save results to file
    with open("test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": passed + failed,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / (passed + failed) * 100,
            "results": test_results
        }, f, indent=2)
    
    print("\nDetailed results saved to: test_results.json")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
