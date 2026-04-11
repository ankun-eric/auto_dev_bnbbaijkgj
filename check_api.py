#!/usr/bin/env python3
"""Check API endpoints."""
import requests

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

# Try different login endpoints
login_endpoints = [
    "/auth/login",
    "/auth/login-admin",
    "/admin/login",
    "/admin/auth/login",
    "/users/login",
    "/token",
    "/auth/token",
]

print("=== Checking API health ===")
r = requests.get(f"{API_URL}/health", timeout=10)
print(f"GET /api/health: {r.status_code} - {r.text[:200]}")

print("\n=== Checking API docs ===")
r = requests.get(f"{API_URL}/docs", timeout=10)
print(f"GET /api/docs: {r.status_code}")
if r.status_code == 200:
    print(r.text[:500])

print("\n=== Trying login endpoints ===")
for endpoint in login_endpoints:
    try:
        r = requests.post(f"{API_URL}{endpoint}", 
                         json={"username": "admin", "password": "admin123"},
                         timeout=10)
        print(f"POST {endpoint}: {r.status_code} - {r.text[:100]}")
    except Exception as e:
        print(f"POST {endpoint}: ERROR {e}")

print("\n=== Try form-data login ===")
try:
    r = requests.post(f"{API_URL}/auth/login", 
                     data={"username": "admin", "password": "admin123"},
                     timeout=10)
    print(f"POST /auth/login (form): {r.status_code} - {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Check openapi spec
print("\n=== Check OpenAPI spec ===")
r = requests.get(f"{API_URL}/openapi.json", timeout=10)
if r.status_code == 200:
    data = r.json()
    paths = list(data.get("paths", {}).keys())
    print(f"Available paths ({len(paths)}):")
    for p in sorted(paths):
        print(f"  {p}")
else:
    print(f"GET /openapi.json: {r.status_code}")
