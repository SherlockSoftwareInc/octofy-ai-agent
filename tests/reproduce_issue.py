import requests
import json

url = "http://localhost:8100/api/v1/generate-r"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "***REMOVED***"
}
data = {
    "query": "Find top selling products"
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(response.text)
except Exception as e:
    print(f"Request failed: {e}")
