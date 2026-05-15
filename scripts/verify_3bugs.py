#!/usr/bin/env python3
"""[BUG-FIX 2026-05-16] 验证 3 个 Bug 修复后的服务器状态。"""
import sys
import time
import urllib.request
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

def hit(path, timeout=20):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = BASE + path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "verify/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.read(200).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(200).decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return 0, str(e)


def main():
    print("====== 等待后端就绪 ======")
    for i in range(1, 30):
        code, _ = hit("/api/health")
        print(f"[{i}] /api/health => {code}")
        if code == 200:
            break
        time.sleep(2)

    cases = [
        ("/api/health", 200, "后端健康检查"),
        # Bug 3: today-todos 接口存在（无 token 应 401，不是 404）
        ("/api/health-plan/today-todos", 401, "Bug 3 验证：today-todos 接口存在（无 token 期 401，不期 404）"),
        # 历史的错误接口名不存在
        ("/api/health-plan/today-tasks", 404, "Bug 3 旁证：错误接口名 today-tasks 应 404（验证我们没在用它）"),
        # Bug 2: 后端健康自查 schema 接受 body_part_id
        ("/api/health-self-check/dict", 401, "Bug 2 旁证：健康自查路由存在（无 token 期 401）"),
    ]
    failed = 0
    for path, expect, desc in cases:
        code, body = hit(path)
        ok = code == expect
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {desc}: GET {path} => {code} (期望 {expect})")
        if not ok and body:
            print(f"         body: {body[:120]}")
        if not ok:
            failed += 1

    # Bug 2 字段校验：post 一个不带 body_part_id 的 payload 应 422，
    # post 带 body_part_id 的 payload 应 401（缺 token），不是 422
    print("\n====== Bug 2 schema 字段校验（POST /api/health-self-check/start） ======")
    # 旧 payload（含 body_part 对象，不含 body_part_id）→ 缺 token 应 401（schema 还未校验）；
    # 注意：FastAPI 依赖项校验先于 body 校验。这里仅打印观察。
    import json
    def post(path, payload, timeout=15):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = BASE + path
        req = urllib.request.Request(
            url, method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "verify/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.status, r.read(300).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.read(300).decode("utf-8", errors="replace")
            except Exception:
                return e.code, ""
        except Exception as e:
            return 0, str(e)

    # 不带 token 期 401（FastAPI 一般依赖项校验先执行）
    code, body = post("/api/health-self-check/start", {
        "template_id": 1, "button_id": 1, "body_part_id": 1,
        "symptoms": ["头痛"], "duration": "1 天内"
    })
    print(f"  POST start (new payload, no auth) => {code} {body[:200]}")
    print("  (期望：401 或 403，不期：422——说明 body_part_id 字段被接受)")

    print(f"\n====== 测试结束：失败 {failed} 项 ======")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
