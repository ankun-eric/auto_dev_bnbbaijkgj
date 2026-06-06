import subprocess
import sys

domain = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
base_url = f"https://{domain}"

# Key pages to test (from requirements)
pages = [
    "/health-profile/archive-list",
    "/health-profile/my-guardians",
    "/family-auth",
    "/messages",
    "/admin/devices/scene-groups",
    "/admin/devices/catalog",
    "/admin/",
]

print("=== Frontend Smoke Tests ===")
for page in pages:
    url = f"{base_url}{page}"
    try:
        result = subprocess.run(
            ["curl", "-s", "--connect-timeout", "5", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        html = result.stdout
        status = "OK" if ("<html" in html.lower() or "<title" in html.lower() or "<!doctype" in html.lower()) else "WARN"
        has_html = "<html" in html.lower() or "<!doctype" in html.lower()
        has_title = "<title" in html.lower()
        content_len = len(html)
        print(f"  [{status}] {page}: html={has_html}, title={has_title}, content_length={content_len}")
    except Exception as e:
        print(f"  [FAIL] {page}: {e}")

# Also check the API endpoints with proper GET requests
print("\n=== API Smoke Tests ===")
api_urls = [
    "/api/health/profile/member/1",
    "/api/family/member/1/unbind",
    "/api/family/management/accept",
    "/api/reverse-guardian/remove",
    "/api/devices/scene-groups",
    "/api/devices/catalog",
]

for api_path in api_urls:
    url = f"{base_url}{api_path}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "NUL", "-w", "%{http_code}", "--connect-timeout", "5", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        http_code = result.stdout.strip()
        print(f"  [{http_code}] {api_path}")
    except Exception as e:
        print(f"  [FAIL] {api_path}: {e}")
