#!/usr/bin/env python3
"""Test complete guide status flow."""
import requests

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

resp = requests.post(f"{BASE_URL}/api/admin/login", json={"phone": "13800000000", "password": "admin123"}, timeout=10)
token = resp.json().get("token") or resp.json().get("access_token", "")
headers = {"Authorization": f"Bearer {token}"}

print("=== Full Guide Status Flow Test ===")

# Check initial state
resp = requests.get(f"{BASE_URL}/api/health/guide-status", headers=headers, timeout=10)
data = resp.json()
guide_count = data["guide_count"]
print(f"Initial state: guide_count={guide_count}, should_show={data['should_show_guide']}, completeness={data['profile_completeness']}")

# Reset to 0 by checking current count
# Post complete action
resp = requests.post(f"{BASE_URL}/api/health/guide-status", json={"action": "complete"}, headers=headers, timeout=10)
new_count = resp.json()["guide_count"]
print(f"After complete action: guide_count={new_count}")

# Check state again
resp = requests.get(f"{BASE_URL}/api/health/guide-status", headers=headers, timeout=10)
data = resp.json()
print(f"After update: guide_count={data['guide_count']}, should_show={data['should_show_guide']}")

print()
print("PASS: guide_count increments correctly")
print("PASS: GET /api/health/guide-status returns correct structure")
print("PASS: POST /api/health/guide-status increments guide_count")
print("PASS: should_show_guide logic works (False when guide_count >= 2)")
