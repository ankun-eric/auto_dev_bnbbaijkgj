#!/usr/bin/env python3
"""[PRD-AICHAT-HOME-GRID-V1 2026-05-16] 服务器端非UI自动化测试

通过 HTTPS 调用线上接口验证：
  T1. /api/health 200
  T2. /api/function-buttons 200 返回数组，每个元素含 is_recommended/is_capsule 字段
  T3. /api/function-buttons?position=grid 200，只含 is_recommended=true 的按钮
  T4. /api/function-buttons?position=capsule 200，只含 is_capsule=true 的按钮
  T5. /api/function-buttons 返回的元素满足"is_recommended OR is_capsule"
  T6. /api/function-buttons?position=grid 内所有元素 is_recommended=true
  T7. /api/function-buttons?position=capsule 内所有元素 is_capsule=true
  T8. 管理端 PATCH /api/admin/function-buttons/{id}/toggle-recommended 401 未鉴权
  T9. 管理端 PATCH /api/admin/function-buttons/{id}/toggle-capsule 401 未鉴权
  T10. /ai-home 前端页面 200（HTML）
  T11. /admin 前端页面 200/308
"""
import json
import ssl
import sys
import urllib.error
import urllib.request


BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def _req(method: str, url: str, body=None, headers=None, timeout: int = 30):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = None
    h = {"User-Agent": "prd-aichat-home-grid-v1-test/1.0"}
    if headers:
        h.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, f"err: {e}".encode("utf-8")


def parse_json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def main() -> int:
    results = []

    def case(name: str, ok: bool, detail: str = ""):
        mark = "PASS" if ok else "FAIL"
        results.append((name, ok, detail))
        print(f"[{mark}] {name}  {detail}")
        return ok

    # T1
    code, _ = _req("GET", f"{BASE}/api/health")
    case("T1 /api/health 200", code == 200, f"code={code}")

    # T2
    code, raw = _req("GET", f"{BASE}/api/function-buttons")
    data = parse_json(raw)
    ok = code == 200 and isinstance(data, list) and (len(data) == 0 or ("is_recommended" in data[0] and "is_capsule" in data[0]))
    case("T2 /api/function-buttons 200 + schema", ok, f"code={code} len={len(data) if isinstance(data, list) else 'N/A'}")

    # T3
    code_g, raw_g = _req("GET", f"{BASE}/api/function-buttons?position=grid")
    data_g = parse_json(raw_g)
    case("T3 ?position=grid 200", code_g == 200 and isinstance(data_g, list), f"code={code_g}")

    # T4
    code_c, raw_c = _req("GET", f"{BASE}/api/function-buttons?position=capsule")
    data_c = parse_json(raw_c)
    case("T4 ?position=capsule 200", code_c == 200 and isinstance(data_c, list), f"code={code_c}")

    # T5
    if isinstance(data, list):
        ok = all((bool(it.get("is_recommended")) or bool(it.get("is_capsule"))) for it in data)
        case("T5 all 元素满足 is_recommended OR is_capsule", ok or len(data) == 0,
             f"n={len(data)}")
    else:
        case("T5 数据非 list", False)

    # T6
    if isinstance(data_g, list):
        ok = all(bool(it.get("is_recommended")) for it in data_g)
        case("T6 grid 元素全部 is_recommended=true", ok or len(data_g) == 0, f"n={len(data_g)}")
    else:
        case("T6 数据非 list", False)

    # T7
    if isinstance(data_c, list):
        ok = all(bool(it.get("is_capsule")) for it in data_c)
        case("T7 capsule 元素全部 is_capsule=true", ok or len(data_c) == 0, f"n={len(data_c)}")
    else:
        case("T7 数据非 list", False)

    # T8/T9 未鉴权 PATCH（id=999999 不必存在，鉴权先拦截）
    code8, _ = _req("PATCH", f"{BASE}/api/admin/function-buttons/999999/toggle-recommended",
                    body={"value": True})
    case("T8 PATCH toggle-recommended 未鉴权返回 401/403", code8 in (401, 403), f"code={code8}")
    code9, _ = _req("PATCH", f"{BASE}/api/admin/function-buttons/999999/toggle-capsule",
                    body={"value": True})
    case("T9 PATCH toggle-capsule 未鉴权返回 401/403", code9 in (401, 403), f"code={code9}")

    # T10 前端 /ai-home（Next.js 通常 308 跳转或 200）
    code10, _ = _req("GET", f"{BASE}/ai-home/")
    case("T10 /ai-home 可达", code10 in (200, 301, 302, 308), f"code={code10}")

    # T11 admin 后台首页
    code11, _ = _req("GET", f"{BASE}/admin/")
    case("T11 /admin 可达", code11 in (200, 301, 302, 308), f"code={code11}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n========== {passed}/{total} PASS ==========")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
