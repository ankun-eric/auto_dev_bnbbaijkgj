"""Server-side tests for AI chat history feature."""
import httpx
import asyncio
import sys

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
ADMIN_PHONE = "13800000000"
ADMIN_PASS = "admin123"

results = []

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))

async def main():
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        # Login as admin via /api/admin/login
        print("\n=== Login ===")
        resp = await client.post(f"{BASE_URL}/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASS})
        if resp.status_code != 200:
            print(f"Admin login failed: {resp.status_code} {resp.text}")
            sys.exit(1)
        admin_token = resp.json()["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        record("Admin login", True)

        # TC-001: Admin list sessions
        print("\n=== Admin API Tests ===")
        resp = await client.get(f"{BASE_URL}/admin/chat-sessions", headers=admin_headers)
        record("TC-001: Admin list sessions", resp.status_code == 200, f"status={resp.status_code}")
        
        # TC-002: No auth → 401
        resp = await client.get(f"{BASE_URL}/admin/chat-sessions")
        record("TC-002: No auth → 401", resp.status_code == 401, f"status={resp.status_code}")

        # TC-003: Admin list with filters
        resp = await client.get(f"{BASE_URL}/admin/chat-sessions", params={"user_search": "test", "page": 1, "page_size": 5}, headers=admin_headers)
        record("TC-003: Admin list with filters", resp.status_code == 200, f"status={resp.status_code}")

        # Create a test session via user API first
        print("\n=== Create test session ===")
        resp = await client.post(f"{BASE_URL}/chat/sessions", json={"session_type": "health_qa", "title": "测试对话"}, headers=admin_headers)
        if resp.status_code == 200:
            session_data = resp.json()
            test_session_id = session_data["id"]
            record("Create test session", True, f"id={test_session_id}")
        else:
            record("Create test session", False, f"status={resp.status_code}")
            test_session_id = None

        # TC-004: Admin get session detail
        if test_session_id:
            resp = await client.get(f"{BASE_URL}/admin/chat-sessions/{test_session_id}", headers=admin_headers)
            record("TC-004: Admin session detail", resp.status_code == 200, f"status={resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                has_messages = "messages" in data
                record("TC-004b: Detail has messages field", has_messages)

        # TC-005: Admin session detail 404
        resp = await client.get(f"{BASE_URL}/admin/chat-sessions/999999", headers=admin_headers)
        record("TC-005: Session 404", resp.status_code == 404, f"status={resp.status_code}")

        # TC-006: Export CSV
        if test_session_id:
            resp = await client.get(f"{BASE_URL}/admin/chat-sessions/{test_session_id}/export", params={"format": "csv"}, headers=admin_headers)
            record("TC-006: Export CSV", resp.status_code == 200 and "text/csv" in resp.headers.get("content-type", ""), f"status={resp.status_code}, ct={resp.headers.get('content-type', '')}")

        # User API Tests
        print("\n=== User API Tests ===")
        
        # TC-007: User list sessions
        resp = await client.get(f"{BASE_URL}/chat-sessions", headers=admin_headers)
        record("TC-007: User list sessions", resp.status_code == 200, f"status={resp.status_code}")

        # TC-008: No auth → 401
        resp = await client.get(f"{BASE_URL}/chat-sessions")
        record("TC-008: User list no auth → 401", resp.status_code == 401, f"status={resp.status_code}")

        # TC-009: User get session detail
        if test_session_id:
            resp = await client.get(f"{BASE_URL}/chat-sessions/{test_session_id}", headers=admin_headers)
            record("TC-009: User session detail", resp.status_code == 200, f"status={resp.status_code}")

        # TC-010: Rename session
        if test_session_id:
            resp = await client.put(f"{BASE_URL}/chat-sessions/{test_session_id}", json={"title": "重命名后的对话"}, headers=admin_headers)
            record("TC-010: Rename session", resp.status_code == 200, f"status={resp.status_code}")

        # TC-011: Pin session
        if test_session_id:
            resp = await client.put(f"{BASE_URL}/chat-sessions/{test_session_id}/pin", json={"is_pinned": True}, headers=admin_headers)
            record("TC-011: Pin session", resp.status_code == 200, f"status={resp.status_code}")
            
            # Verify pin worked
            resp = await client.get(f"{BASE_URL}/chat-sessions/{test_session_id}", headers=admin_headers)
            if resp.status_code == 200:
                record("TC-011b: Pin verified", resp.json().get("is_pinned") == True)

        # TC-012: Share session
        if test_session_id:
            resp = await client.post(f"{BASE_URL}/chat-sessions/{test_session_id}/share", headers=admin_headers)
            record("TC-012: Share session", resp.status_code == 200, f"status={resp.status_code}")
            if resp.status_code == 200:
                share_data = resp.json()
                share_token = share_data.get("share_token")
                record("TC-012b: Share has token", bool(share_token))

                # TC-013: Get shared chat (public)
                if share_token:
                    resp = await client.get(f"{BASE_URL}/shared/chat/{share_token}")
                    record("TC-013: Get shared chat", resp.status_code == 200, f"status={resp.status_code}")
                    if resp.status_code == 200:
                        shared_data = resp.json()
                        record("TC-013b: Shared has messages", "messages" in shared_data)

        # TC-014: Invalid share token
        resp = await client.get(f"{BASE_URL}/shared/chat/invalid_token_xyz")
        record("TC-014: Invalid share token → 404", resp.status_code == 404, f"status={resp.status_code}")

        # TC-015: Delete session (soft delete)
        if test_session_id:
            resp = await client.delete(f"{BASE_URL}/chat-sessions/{test_session_id}", headers=admin_headers)
            record("TC-015: Delete session", resp.status_code == 200, f"status={resp.status_code}")

            # Verify deleted session not in user list
            resp = await client.get(f"{BASE_URL}/chat-sessions", headers=admin_headers)
            if resp.status_code == 200:
                items = resp.json()
                found = any(s.get("id") == test_session_id for s in items)
                record("TC-015b: Deleted not in user list", not found)

            # Admin can still see it
            resp = await client.get(f"{BASE_URL}/admin/chat-sessions/{test_session_id}", headers=admin_headers)
            record("TC-015c: Admin can still see deleted", resp.status_code == 200, f"status={resp.status_code}")

    # Summary
    print("\n" + "=" * 50)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")
    
    if failed > 0:
        print("\nFailed tests:")
        for name, status, detail in results:
            if status == "FAIL":
                print(f"  - {name}: {detail}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
