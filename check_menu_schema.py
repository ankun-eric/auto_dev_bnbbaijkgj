#!/usr/bin/env python3
"""Check home-menu API schema."""
import requests

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

session = requests.Session()

# Login
r = session.post(f"{API_URL}/admin/login", json={"phone": "13800000000", "password": "admin123"})
token = r.json().get("access_token") or r.json().get("token")
session.headers["Authorization"] = f"Bearer {token}"

# Get existing menus to understand schema
r = session.get(f"{API_URL}/admin/home-menus")
print("GET home-menus:", r.status_code)
data = r.json()
print("Response type:", type(data))
if isinstance(data, dict):
    print("Keys:", list(data.keys()))
    items = data.get("items", data.get("data", []))
    if items:
        print("First item keys:", list(items[0].keys()))
        print("First item:", items[0])
else:
    if data:
        print("First item keys:", list(data[0].keys()))
        print("First item:", data[0])
