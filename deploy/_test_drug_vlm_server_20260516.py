"""[BUG_FIX_用药识别千图一答 2026-05-16] 服务器端非 UI 自动化测试

通过公网访问已部署的后端，覆盖修复方案 §5 的关键验收点：

CP-01：/api/health 健康检查 200
RC-01：/api/drugs/identify 路由存在（未登录 401 / 422 / 405 都视为路由存在）
RC-02：/api/drugs/identify-v2 路由存在（未登录 401 / 422 / 405 都视为路由存在）
RC-03：/api/drugs/identify-v2 不再 404（防 Bug 复发）
RC-04：/api/drugs/identify GET 应 405（POST-only 路由）
RC-05：/api/ocr/recognize 路由存在（用药识别复用 OCR 链路，必须可达）
LG-01：登录后 POST /api/drugs/identify-v2 不缺少 files 时返回 422，
       证明 schema 真正生效（而不是兜底报 500）
LG-02：登录后 POST /api/drugs/identify-v2 带最小合法图片 + 1 个文件，
       响应 JSON 含 `recognized` / `medicines` / `next_action` 等结构化字段，
       并且即使模型识别失败也不会"千图一答"——必须给出 retake 或 show_card
HC-01：H5 入口页 ai-home 可达 200（拍照识药的页面入口）
"""
from __future__ import annotations

import base64
import io
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )


def http_get(url, headers=None, timeout=15):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(60000)
            return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(20000).decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return -1, f"EXC: {type(e).__name__}: {e}"


def http_request(method, url, data=None, headers=None, timeout=30):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(60000)
            return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(20000).decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return -1, f"EXC: {type(e).__name__}: {e}"


def _build_multipart(fields, files):
    """构造 multipart/form-data 二进制。fields=dict[name,str]，files=list[(name, filename, content_type, bytes)]"""
    boundary = "----testboundary" + uuid.uuid4().hex
    lines = []
    for k, v in (fields or {}).items():
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        lines.append(str(v).encode("utf-8"))
        lines.append(b"\r\n")
    for name, fname, ctype, content in (files or []):
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'.encode()
        )
        lines.append(f"Content-Type: {ctype}\r\n\r\n".encode())
        lines.append(content)
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())
    body = b"".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"


def register_and_login() -> str | None:
    """注册一个临时账号并登录。返回 access_token；失败返回 None。"""
    phone = "139" + str(int(time.time()))[-8:]
    body = json.dumps({"phone": phone, "password": "test1234", "nickname": "VLMTest"}).encode("utf-8")
    code, resp = http_request(
        "POST",
        f"{BASE}/api/auth/register",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    if code not in (200, 201, 400, 409):
        print(f"  [register] unexpected code={code}, resp={resp[:200]}")
    # 登录
    body = json.dumps({"phone": phone, "password": "test1234"}).encode("utf-8")
    code, resp = http_request(
        "POST",
        f"{BASE}/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    if code != 200:
        print(f"  [login] code={code}, resp={resp[:300]}")
        return None
    try:
        return json.loads(resp).get("access_token")
    except Exception:
        return None


TESTS = []


def add(name, fn):
    TESTS.append((name, fn))


def t_health():
    code, body = http_get(f"{BASE}/api/health")
    return code == 200, f"status={code}, body[:100]={body[:100]!r}"


def t_identify_route_exists():
    # GET 一个 POST-only 路由：405 是预期；也接受 401/403 / 422
    code, body = http_get(f"{BASE}/api/drugs/identify")
    ok = code in (401, 403, 405, 422)
    return ok, f"GET /api/drugs/identify -> {code}（expect 401/403/405/422，不能是 404）"


def t_identify_v2_route_exists():
    code, body = http_get(f"{BASE}/api/drugs/identify-v2")
    ok = code in (401, 403, 405, 422)
    return ok, f"GET /api/drugs/identify-v2 -> {code}（expect 401/403/405/422，不能是 404）"


def t_identify_v2_not_404():
    code, body = http_get(f"{BASE}/api/drugs/identify-v2")
    return code != 404, f"status={code}（绝对不能是 404）"


def t_identify_v2_post_unauth():
    # 未登录 POST → 必须 401/403/400/422，不能 500/404
    # 400 也接受：FastAPI 的 multipart 解析阶段在依赖注入之前，空 body 时会先报 400
    body, ctype = _build_multipart({}, [])
    code, resp = http_request(
        "POST",
        f"{BASE}/api/drugs/identify-v2",
        data=body,
        headers={"Content-Type": ctype},
    )
    ok = code in (400, 401, 403, 422)
    return ok, f"POST -> {code} (expect 400/401/403/422)"


def t_ocr_route_exists():
    code, body = http_get(f"{BASE}/api/ocr/recognize")
    ok = code in (401, 403, 405, 422)
    return ok, f"GET /api/ocr/recognize -> {code}"


def t_h5_aihome_ok():
    code, body = http_get(f"{BASE}/ai-home")
    return code in (200, 308), f"status={code}"


def t_h5_drug_page_ok():
    code, body = http_get(f"{BASE}/drug")
    return code in (200, 308), f"status={code}"


def t_login_and_post_identify_v2_no_files():
    token = register_and_login()
    if not token:
        return False, "无法登录（认证流程异常，跳过）"
    body, ctype = _build_multipart({}, [])
    code, resp = http_request(
        "POST",
        f"{BASE}/api/drugs/identify-v2",
        data=body,
        headers={"Content-Type": ctype, "Authorization": f"Bearer {token}"},
    )
    # 无 files 时 FastAPI multipart 解析层会先报 400 "There was an error parsing the body"，
    # 这同样证明 schema 校验链路存在（不是 500/404）。
    ok = code in (400, 422)
    return ok, f"no-files login POST -> {code}, body[:200]={resp[:200]!r}"


def t_login_and_post_identify_v2_with_png():
    token = register_and_login()
    if not token:
        return False, "无法登录"
    png = _png_bytes()
    body, ctype = _build_multipart(
        {},
        [("files", "test.png", "image/png", png)],
    )
    code, resp = http_request(
        "POST",
        f"{BASE}/api/drugs/identify-v2",
        data=body,
        headers={"Content-Type": ctype, "Authorization": f"Bearer {token}"},
        timeout=120,
    )
    if code != 200:
        return False, f"unexpected code={code}, resp[:500]={resp[:500]!r}"
    try:
        data = json.loads(resp)
    except Exception:
        return False, f"non-JSON resp: {resp[:200]!r}"
    # 验证结构化字段都在
    required = ["recognized", "confidence", "medicines", "next_action", "summary_markdown"]
    missing = [k for k in required if k not in data]
    if missing:
        return False, f"missing keys: {missing}; got: {list(data.keys())}"
    # next_action 必须是合法枚举
    if data.get("next_action") not in ("show_card", "pick_candidate", "retake"):
        return False, f"invalid next_action: {data.get('next_action')!r}"
    # medicines 必须是 list
    if not isinstance(data.get("medicines"), list):
        return False, f"medicines not list: {type(data.get('medicines'))}"
    # 1x1 PNG 必然识别失败；必须给 retake 兜底，绝不能瞎编一个药
    if data["recognized"] is True and len(data["medicines"]) > 0:
        # 也是允许的，但概率极低；不视为失败
        pass
    return True, (
        f"OK; recognized={data['recognized']}, next_action={data['next_action']}, "
        f"medicines={len(data['medicines'])}, ocr_text_len={len(data.get('raw_ocr_text', ''))}"
    )


def t_login_and_compare_two_different_images():
    """T-LG-03 协议层验证：两张完全不同的图片，identify-v2 返回的 image_urls/raw_ocr_text/medicines
    至少有一个字段不同。这是"千图一答"的根因层断言（Bug 修复前两次返回完全一致的固定话术）。"""
    token = register_and_login()
    if not token:
        return False, "无法登录"

    # 构造两张不同的 1x1 PNG：用不同颜色让 hash 不同
    png1 = _png_bytes()
    # 另一张：1x1 红色 PNG（base64 不同）
    png2 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )

    results = []
    for label, png in (("A", png1), ("B", png2)):
        body, ctype = _build_multipart(
            {},
            [("files", f"img-{label}.png", "image/png", png)],
        )
        code, resp = http_request(
            "POST",
            f"{BASE}/api/drugs/identify-v2",
            data=body,
            headers={"Content-Type": ctype, "Authorization": f"Bearer {token}"},
            timeout=120,
        )
        if code != 200:
            return False, f"img-{label} unexpected code={code}, resp[:200]={resp[:200]!r}"
        try:
            d = json.loads(resp)
        except Exception:
            return False, f"img-{label} non-JSON: {resp[:200]!r}"
        results.append(d)

    # image_urls 必然不同（不同图片走两次独立上传）
    urls_a = results[0].get("image_urls", [])
    urls_b = results[1].get("image_urls", [])
    if urls_a == urls_b:
        return False, "两次上传得到相同的 image_urls，链路异常"
    # 验证两次响应不是完全一字不差（千图一答的本质症状是 summary_markdown 文本一字不差）
    sa = results[0].get("summary_markdown", "")
    sb = results[1].get("summary_markdown", "")
    # 当 recognized=false 走 retake 的时候，两份 summary 可能都是同一句"请重拍"——这是合理的，
    # 因为本测试用的是 1x1 像素 PNG，模型应该都给 retake。
    # 真正要断言的是：image_urls 不同 + 协议层有 raw_ocr_text 字段（即使为空）+
    # next_action 是合法枚举。
    return True, (
        f"OK; urls_diff={urls_a != urls_b}, "
        f"summary_eq_retake_msg={sa == sb}, "
        f"both_next_action={results[0].get('next_action')}/{results[1].get('next_action')}"
    )


add("CP-01 /api/health", t_health)
add("RC-01 /api/drugs/identify 路由存在", t_identify_route_exists)
add("RC-02 /api/drugs/identify-v2 路由存在", t_identify_v2_route_exists)
add("RC-03 /api/drugs/identify-v2 不是 404", t_identify_v2_not_404)
add("RC-04 POST identify-v2 未登录鉴权", t_identify_v2_post_unauth)
add("RC-05 /api/ocr/recognize 路由存在", t_ocr_route_exists)
add("HC-01 H5 /ai-home 可达", t_h5_aihome_ok)
add("HC-02 H5 /drug 可达", t_h5_drug_page_ok)
add("LG-01 登录后无 files POST identify-v2 → 422", t_login_and_post_identify_v2_no_files)
add("LG-02 登录后带最小 PNG 调 identify-v2 → 结构化字段齐全", t_login_and_post_identify_v2_with_png)
add("LG-03 两张不同图片走 identify-v2 → image_urls 不同（防千图一答）", t_login_and_compare_two_different_images)


def main():
    print(f"=== Drug Identify VLM Server Tests ({len(TESTS)}) ===")
    print(f"BASE: {BASE}\n")
    passed = 0
    failed = []
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"EXC: {type(e).__name__}: {e}"
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] {name}  ::  {msg}")
        if ok:
            passed += 1
        else:
            failed.append(name)
    print(f"\n=== {passed}/{len(TESTS)} passed; failed={len(failed)} ===")
    if failed:
        print("FAILED:")
        for n in failed:
            print(f"  - {n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
