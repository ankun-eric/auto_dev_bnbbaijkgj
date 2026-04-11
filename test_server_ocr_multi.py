"""
OCR 多图上传功能 - 非UI自动化测试
待部署后执行（服务器需已部署新代码）

覆盖端点：
  POST /api/ocr/batch-recognize
  POST /api/admin/ocr/test-ocr
  POST /api/admin/ocr/test-full
  GET  /api/admin/ocr/records
"""

import io
import struct
import sys
import zlib

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE_URL}/api"


def create_test_png() -> bytes:
    """创建最小有效的 1x1 像素 PNG 图片（红色像素）。"""
    header = b"\x89PNG\r\n\x1a\n"

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    raw_data = b"\x00\xff\x00\x00"  # filter byte + RGB
    compressed = zlib.compress(raw_data)
    idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    return header + ihdr + idat + iend


def make_png_files(count: int):
    """返回可直接传给 requests 的 multipart files 列表（count 个 PNG）。"""
    png_bytes = create_test_png()
    return [
        ("files", (f"test_{i}.png", io.BytesIO(png_bytes), "image/png"))
        for i in range(count)
    ]


def main():
    passed = 0
    failed = 0
    errors = []

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f"  PASS: {msg}")

    def fail(msg):
        nonlocal failed
        errors.append(msg)
        failed += 1
        print(f"  FAIL: {msg}")

    # ------------------------------------------------------------------ #
    # TC-001: Health check / 服务可达性
    # ------------------------------------------------------------------ #
    print("\nTC-001: 服务可达性检查 (GET /api/health)")
    try:
        r = requests.get(f"{API}/health", verify=False, timeout=10)
        if r.status_code == 200:
            ok("Health check 返回 200")
        else:
            fail(f"Health check 失败: status {r.status_code}")
    except Exception as e:
        fail(f"Health check 异常: {e}")

    # ------------------------------------------------------------------ #
    # 登录获取 token（admin + 普通用户）
    # ------------------------------------------------------------------ #
    print("\nSetup: Admin 登录")
    admin_token = None
    admin_headers = {}
    try:
        r = requests.post(
            f"{API}/auth/login",
            json={"phone": "13800000000", "password": "admin123"},
            verify=False,
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            admin_token = data.get("access_token") or data.get("token")
            if admin_token:
                admin_headers = {"Authorization": f"Bearer {admin_token}"}
                print(f"  INFO: Admin token 获取成功")
            else:
                print(f"  WARN: 登录返回 200 但无 token: {data}")
        else:
            print(f"  WARN: Admin 登录失败 status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        print(f"  WARN: Admin 登录异常: {e}")

    # 普通用户 token（与 admin 相同账号，视业务而定；若有独立用户账号可替换）
    user_token = admin_token
    user_headers = admin_headers

    # ------------------------------------------------------------------ #
    # TC-002: 批量识别接口接受多图
    # ------------------------------------------------------------------ #
    print("\nTC-002: 批量识别接口接受多图 (POST /api/ocr/batch-recognize, 2张图)")
    try:
        files = make_png_files(2)
        r = requests.post(
            f"{API}/ocr/batch-recognize",
            files=files,
            headers=user_headers,
            verify=False,
            timeout=30,
        )
        # 接口存在且不是 404/405
        if r.status_code == 404:
            fail("接口不存在 (404)，请确认已部署新代码")
        elif r.status_code == 405:
            fail("接口方法不允许 (405)")
        elif r.status_code in (200, 201):
            data = r.json()
            required_fields = {"results", "total", "success_count", "fail_count"}
            missing = required_fields - set(data.keys())
            if missing:
                fail(f"响应缺少字段: {missing}，实际: {list(data.keys())}")
            else:
                ok("响应包含 results / total / success_count / fail_count")
                if data.get("total") == 2:
                    ok("total == 2，与上传图片数量一致")
                else:
                    fail(f"total 期望 2，实际 {data.get('total')}")
        elif r.status_code in (401, 403):
            fail(f"认证失败 ({r.status_code})，请检查 token")
        else:
            # 其他非 2xx 也视为失败，但打印详情辅助排查
            fail(f"意外状态码 {r.status_code}，body: {r.text[:300]}")
    except Exception as e:
        fail(f"TC-002 异常: {e}")

    # ------------------------------------------------------------------ #
    # TC-003: 批量识别超过数量限制应返回 400
    # ------------------------------------------------------------------ #
    print("\nTC-003: 批量识别超过限制 (6张图，期望 400)")
    try:
        files = make_png_files(6)
        r = requests.post(
            f"{API}/ocr/batch-recognize",
            files=files,
            headers=user_headers,
            verify=False,
            timeout=30,
        )
        if r.status_code == 400:
            ok("超出数量限制正确返回 400")
        elif r.status_code == 422:
            ok("超出数量限制返回 422（Unprocessable Entity，可接受）")
        elif r.status_code == 404:
            fail("接口不存在 (404)，请确认已部署新代码")
        else:
            fail(f"期望 400，实际 {r.status_code}，body: {r.text[:300]}")
    except Exception as e:
        fail(f"TC-003 异常: {e}")

    # ------------------------------------------------------------------ #
    # TC-004: 管理端多图测试接口存在性 (POST /api/admin/ocr/test-ocr)
    # ------------------------------------------------------------------ #
    print("\nTC-004: 管理端多图测试接口存在性 (POST /api/admin/ocr/test-ocr)")
    if not admin_token:
        fail("跳过：无 admin token")
    else:
        try:
            files = make_png_files(1)
            data = {"provider": "mock"}
            r = requests.post(
                f"{API}/admin/ocr/test-ocr",
                files=files,
                data=data,
                headers=admin_headers,
                verify=False,
                timeout=30,
            )
            if r.status_code == 404:
                fail("接口不存在 (404)，请确认已部署新代码")
            elif r.status_code == 405:
                fail("接口方法不允许 (405)")
            elif r.status_code in (401, 403):
                fail(f"认证失败 ({r.status_code})")
            else:
                # 200 / 400 / 422 / 500 均表示接口存在
                ok(f"接口存在，返回 status={r.status_code}（非 404/405）")
                if r.status_code == 200:
                    resp_data = r.json()
                    if "merged_ocr_text" in resp_data or "results" in resp_data:
                        ok("响应包含预期字段 (merged_ocr_text 或 results)")
                    else:
                        print(f"  INFO: 响应字段: {list(resp_data.keys())}")
        except Exception as e:
            fail(f"TC-004 异常: {e}")

    # ------------------------------------------------------------------ #
    # TC-004b: 管理端完整测试接口存在性 (POST /api/admin/ocr/test-full)
    # ------------------------------------------------------------------ #
    print("\nTC-004b: 管理端完整测试接口存在性 (POST /api/admin/ocr/test-full)")
    if not admin_token:
        fail("跳过：无 admin token")
    else:
        try:
            # 先获取一个有效的 scene_id
            scene_id = 1
            r_scenes = requests.get(
                f"{API}/admin/ocr/scenes", headers=admin_headers, verify=False, timeout=10
            )
            if r_scenes.status_code == 200:
                scenes = r_scenes.json()
                if scenes:
                    scene_id = scenes[0]["id"]

            files = make_png_files(1)
            data = {"provider": "mock", "scene_id": str(scene_id)}
            r = requests.post(
                f"{API}/admin/ocr/test-full",
                files=files,
                data=data,
                headers=admin_headers,
                verify=False,
                timeout=30,
            )
            if r.status_code == 404:
                fail("接口不存在 (404)，请确认已部署新代码")
            elif r.status_code == 405:
                fail("接口方法不允许 (405)")
            elif r.status_code in (401, 403):
                fail(f"认证失败 ({r.status_code})")
            else:
                ok(f"接口存在，返回 status={r.status_code}（非 404/405）")
                if r.status_code == 200:
                    resp_data = r.json()
                    expected = {"merged_ocr_text", "merged_ai_result"}
                    present = expected & set(resp_data.keys())
                    if present:
                        ok(f"响应包含预期字段: {present}")
                    else:
                        print(f"  INFO: 响应字段: {list(resp_data.keys())}")
        except Exception as e:
            fail(f"TC-004b 异常: {e}")

    # ------------------------------------------------------------------ #
    # TC-005: OcrCallRecord 支持 image_count 字段
    # ------------------------------------------------------------------ #
    print("\nTC-005: OcrCallRecord 支持 image_count 字段 (GET /api/admin/ocr/records)")
    if not admin_token:
        fail("跳过：无 admin token")
    else:
        try:
            r = requests.get(
                f"{API}/admin/ocr/records",
                headers=admin_headers,
                verify=False,
                timeout=10,
            )
            if r.status_code == 404:
                fail("接口不存在 (404)，请确认已部署新代码")
            elif r.status_code in (401, 403):
                fail(f"认证失败 ({r.status_code})")
            elif r.status_code == 200:
                data = r.json()
                # 响应可能是列表或分页对象 {"items": [...], "total": ...}
                records = data if isinstance(data, list) else data.get("items", data.get("records", []))
                if not isinstance(records, list):
                    fail(f"无法解析记录列表，响应类型: {type(data).__name__}，内容: {str(data)[:200]}")
                elif len(records) == 0:
                    # 无记录时无法验证字段，但接口本身正常
                    ok("接口返回 200，暂无记录（无法验证 image_count 字段，需有数据后再测）")
                else:
                    first = records[0]
                    if "image_count" in first:
                        ok(f"记录包含 image_count 字段（值: {first['image_count']}）")
                    else:
                        fail(f"记录缺少 image_count 字段，实际字段: {list(first.keys())}")
            else:
                fail(f"意外状态码 {r.status_code}，body: {r.text[:300]}")
        except Exception as e:
            fail(f"TC-005 异常: {e}")

    # ------------------------------------------------------------------ #
    # 汇总
    # ------------------------------------------------------------------ #
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
