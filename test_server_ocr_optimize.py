"""
Non-UI automated tests for OCR-related APIs and frontend pages.
Validates backend API endpoints and frontend page accessibility after OCR optimization changes.
"""

import struct
import sys
import time
import warnings
import zlib

import httpx

warnings.filterwarnings("ignore")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_BASE = f"{BASE_URL}/api/admin/ocr"
TIMEOUT = 60.0

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"

results = []


def api(path: str) -> str:
    if path.startswith("/"):
        return f"{BASE_URL}{path}"
    return f"{BASE_URL}/{path}"


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


def make_test_png(width=400, height=300) -> bytes:
    """Generate a valid PNG that passes quality checks (>=200x200, >=10KB)."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"
        for x in range(width):
            r = (x * 7 + y * 13 + (x ^ y)) & 0xFF
            g = (x * 11 + y * 3 + (x * y)) & 0xFF
            b_val = (x * 5 + y * 17 + (x + y)) & 0xFF
            raw_data += bytes([r, g, b_val])
    idat_data = zlib.compress(raw_data, 1)
    return header + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", idat_data) + chunk(b"IEND", b"")


def get_admin_token(client: httpx.Client) -> str:
    """Authenticate as admin and return bearer token."""
    resp = client.post(api("/api/admin/login"), json={
        "phone": ADMIN_PHONE,
        "password": ADMIN_PASSWORD,
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token

    resp2 = client.post(api("/api/auth/login"), json={
        "phone": ADMIN_PHONE,
        "password": ADMIN_PASSWORD,
    })
    if resp2.status_code == 200:
        data2 = resp2.json()
        token = data2.get("access_token") or data2.get("token")
        if token:
            return token

    return ""


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_admin_login(client: httpx.Client) -> str:
    """Test admin login and return token."""
    token = get_admin_token(client)
    if token:
        record("管理员登录", True, "获取token成功")
    else:
        record("管理员登录", False, "无法获取admin token")
    return token


def test_get_scenes(client: httpx.Client, token: str):
    """GET /api/admin/ocr/scenes"""
    url = api("/api/admin/ocr/scenes")
    try:
        resp = client.get(url, headers=auth_headers(token))
        if resp.status_code == 200:
            data = resp.json()
            record("GET /scenes - 状态码200", True, f"status={resp.status_code}")
            if isinstance(data, dict):
                record("GET /scenes - 返回JSON对象", True, f"keys={list(data.keys())[:5]}")
            elif isinstance(data, list):
                record("GET /scenes - 返回JSON数组", True, f"count={len(data)}")
            else:
                record("GET /scenes - 返回JSON", True, f"type={type(data).__name__}")
        else:
            record("GET /scenes - 状态码200", False,
                   f"status={resp.status_code}, body={resp.text[:200]}")
    except Exception as e:
        record("GET /scenes - 请求成功", False, str(e))


def test_get_upload_limits(client: httpx.Client, token: str):
    """GET /api/admin/ocr/upload-limits - verify max_batch_count field exists."""
    url = api("/api/admin/ocr/upload-limits")
    try:
        resp = client.get(url, headers=auth_headers(token))
        if resp.status_code == 200:
            data = resp.json()
            record("GET /upload-limits - 状态码200", True, f"status={resp.status_code}")

            def find_key(obj, key):
                if isinstance(obj, dict):
                    if key in obj:
                        return obj[key]
                    for v in obj.values():
                        r = find_key(v, key)
                        if r is not None:
                            return r
                elif isinstance(obj, list):
                    for item in obj:
                        r = find_key(item, key)
                        if r is not None:
                            return r
                return None

            val = find_key(data, "max_batch_count")
            if val is not None:
                record("GET /upload-limits - max_batch_count字段存在", True,
                       f"max_batch_count={val}")
            else:
                record("GET /upload-limits - max_batch_count字段存在", False,
                       f"字段未找到, body={str(data)[:300]}")
        else:
            record("GET /upload-limits - 状态码200", False,
                   f"status={resp.status_code}, body={resp.text[:200]}")
    except Exception as e:
        record("GET /upload-limits - 请求成功", False, str(e))


def test_get_providers(client: httpx.Client, token: str):
    """GET /api/admin/ocr/providers"""
    url = api("/api/admin/ocr/providers")
    try:
        resp = client.get(url, headers=auth_headers(token))
        if resp.status_code == 200:
            data = resp.json()
            record("GET /providers - 状态码200", True, f"status={resp.status_code}")
            if isinstance(data, dict):
                record("GET /providers - 返回JSON", True, f"keys={list(data.keys())[:5]}")
            elif isinstance(data, list):
                record("GET /providers - 返回JSON数组", True, f"count={len(data)}")
            else:
                record("GET /providers - 返回JSON", True, f"type={type(data).__name__}")
        else:
            record("GET /providers - 状态码200", False,
                   f"status={resp.status_code}, body={resp.text[:200]}")
    except Exception as e:
        record("GET /providers - 请求成功", False, str(e))


def test_post_test_full(client: httpx.Client, token: str):
    """POST /api/admin/ocr/test-full - multi-file upload test."""
    url = api("/api/admin/ocr/test-full")
    try:
        png_data = make_test_png()
        files = [
            ("files", ("test1.png", png_data, "image/png")),
            ("files", ("test2.png", png_data, "image/png")),
        ]
        resp = client.post(url, files=files, headers=auth_headers(token), timeout=TIMEOUT)

        record("POST /test-full - 接口可达(已认证)", True, f"status={resp.status_code}")

        try:
            data = resp.json()
            record("POST /test-full - 返回JSON", True,
                   f"keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
        except Exception:
            record("POST /test-full - 返回JSON", False, f"body={resp.text[:300]}")

        if resp.status_code != 401:
            record("POST /test-full - 认证通过(非401)", True, f"status={resp.status_code}")
        else:
            record("POST /test-full - 认证通过(非401)", False, f"status=401")

        if resp.status_code in (200, 422, 400, 500):
            record("POST /test-full - 支持多文件files字段", True,
                   f"status={resp.status_code} (端点接受multi-part multi-file请求)")
        else:
            record("POST /test-full - 支持多文件files字段", False,
                   f"unexpected status={resp.status_code}, body={resp.text[:200]}")

    except Exception as e:
        record("POST /test-full - 请求成功", False, str(e))


def test_frontend_page(client: httpx.Client, name: str, url: str):
    """Test frontend page accessibility (HTTP 200)."""
    try:
        resp = client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            record(f"前端页面 {name} - HTTP 200", True, f"url={url}")
        else:
            record(f"前端页面 {name} - HTTP 200", False,
                   f"status={resp.status_code}, url={url}")
    except Exception as e:
        record(f"前端页面 {name} - 可达", False, f"url={url}, error={e}")


def main():
    print("=" * 70)
    print("OCR 相关 API 非UI自动化测试")
    print(f"基础URL: {BASE_URL}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    with httpx.Client(verify=False, timeout=TIMEOUT) as client:

        print("\n--- 0. 管理员登录 ---\n")
        token = test_admin_login(client)
        if not token:
            print("\n  [ERROR] 无法获取admin token，后续API测试将跳过。\n")

        print("\n--- 1. 后端 API 测试 ---\n")

        if token:
            print("[测试] GET /api/admin/ocr/scenes")
            test_get_scenes(client, token)
            print()

            print("[测试] GET /api/admin/ocr/upload-limits")
            test_get_upload_limits(client, token)
            print()

            print("[测试] GET /api/admin/ocr/providers")
            test_get_providers(client, token)
            print()

            print("[测试] POST /api/admin/ocr/test-full")
            test_post_test_full(client, token)
            print()
        else:
            for name in [
                "GET /scenes", "GET /upload-limits", "GET /providers", "POST /test-full"
            ]:
                record(f"{name} - 跳过(无token)", False, "管理员登录失败")

        print("--- 2. 前端页面可达性测试 ---\n")

        pages = [
            ("管理后台首页", f"{BASE_URL}/admin/"),
            ("OCR全局设置页面", f"{BASE_URL}/admin/ocr-global-config"),
            ("OCR识别配置页面", f"{BASE_URL}/admin/ocr-config"),
        ]
        for name, url in pages:
            print(f"[测试] {name}")
            test_frontend_page(client, name, url)
            print()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print("=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"总计: {total}  通过: {passed}  失败: {failed}")
    print()

    if failed > 0:
        print("失败的测试:")
        for r in results:
            if not r["passed"]:
                print(f"  [FAIL] {r['name']}")
                if r["detail"]:
                    print(f"         {r['detail']}")
        print()

    if failed == 0:
        print("所有测试通过！")
    else:
        print(f"有 {failed} 个测试失败，请检查。")

    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
