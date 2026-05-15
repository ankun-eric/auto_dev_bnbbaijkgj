#!/usr/bin/env python3
"""[BUG-FIX 2026-05-16] 健康自查端到端测试（带真实登录）

测试链路：
1. 测试号 13800138000 + 验证码 123456 登录拿 token
2. GET /api/health-self-check/dict （部位字典）
3. GET /api/health-self-check/template/1
4. GET /api/health-plan/today-todos （Bug 3 修复后 today-todos 接口正常返回）
5. POST /api/health-self-check/start 用新 payload 提交（body_part_id）→ 拿到 AI 回答
6. 反例：POST /start 用旧 payload（含 body_part 对象、archive_name 等无 body_part_id）→ 应 422

预期：1~5 全部通过；6 应 422
"""
import json
import ssl
import sys
import time
import urllib.request
import urllib.parse

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
TEST_PHONE = "13800138000"
TEST_CODE = "123456"


def request(method, path, payload=None, token=None, timeout=60):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = BASE + path
    headers = {"Content-Type": "application/json", "User-Agent": "e2e/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(body) if body else {}
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
            return e.code, json.loads(body) if body else {}
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def must(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}: {detail}")
    return ok


def main():
    print("====== 健康自查 E2E 测试（含登录） ======\n")
    failed = 0

    # 1. 请求验证码（测试号会得到固定码 123456）
    code, body = request("POST", "/api/auth/sms-code", {"phone": TEST_PHONE, "type": "login"})
    if not must("请求验证码", code in (200, 201), f"=> {code} {body}"):
        failed += 1

    # 2. 登录
    code, body = request("POST", "/api/auth/sms-login", {"phone": TEST_PHONE, "code": TEST_CODE})
    if not must("SMS 登录", code == 200 and isinstance(body, dict) and body.get("access_token"),
                f"=> {code} {str(body)[:200]}"):
        failed += 1
        return 1
    token = body["access_token"]
    print(f"  拿到 token: {token[:30]}...")

    # 3. dict
    code, body = request("GET", "/api/health-self-check/dict", token=token)
    parts = body if isinstance(body, list) else []
    if not must("健康自查字典", code == 200 and len(parts) > 0, f"=> {code}, parts={len(parts)}"):
        failed += 1

    # 4. 找一个 health_self_check 类型的按钮
    code, btns = request("GET", "/api/function-buttons", token=token)
    health_btn = None
    if isinstance(btns, list):
        for b in btns:
            if b.get("button_type") == "health_self_check":
                health_btn = b
                break
    if not must("找到 health_self_check 按钮", health_btn is not None,
                f"=> 找到按钮 id={health_btn['id'] if health_btn else 'N/A'}"):
        # 退而求其次：直接在数据库查
        return 1
    button_id = health_btn["id"]
    template_id = health_btn.get("health_check_template_id") or 1

    # 5. template
    code, tpl = request("GET", f"/api/health-self-check/template/{template_id}", token=token)
    if not must(f"健康自查模板 {template_id}", code == 200, f"=> {code}, template id={tpl.get('id') if isinstance(tpl, dict) else 'N/A'}"):
        failed += 1
        return 1
    part_id = tpl["body_parts_detail"][0]["id"]
    symptom = tpl["body_parts_detail"][0]["symptoms"][0]
    duration = tpl["duration_options"][0]

    # 6. today-todos
    code, body = request("GET", "/api/health-plan/today-todos", token=token)
    if not must("Bug 3：today-todos 接口", code == 200 and isinstance(body, dict),
                f"=> {code}, total_count={body.get('total_count') if isinstance(body, dict) else 'N/A'}"):
        failed += 1

    # 7. start（新 payload，含 body_part_id）→ 200 + ai_content
    code, body = request("POST", "/api/health-self-check/start", {
        "template_id": template_id,
        "button_id": button_id,
        "body_part_id": part_id,
        "symptoms": [symptom],
        "duration": duration,
    }, token=token, timeout=120)
    ai_content = body.get("ai_content", "") if isinstance(body, dict) else ""
    if not must("Bug 2：start 新 payload 成功", code == 200 and len(ai_content) > 0,
                f"=> {code}, ai_content 长度={len(ai_content)}, body={str(body)[:200]}"):
        failed += 1
    else:
        print(f"     AI 回答前 80 字: {ai_content[:80]}")

    # 8. 反例：start（旧 payload，不含 body_part_id）→ 422
    code, body = request("POST", "/api/health-self-check/start", {
        "template_id": template_id,
        "button_id": button_id,
        "archive_id": None,
        "archive_name": "本人",
        "archive_age": None,
        "archive_gender": None,
        "body_part": {"id": part_id, "name": "头部", "icon": "🧠"},
        "symptoms": [symptom],
        "duration": duration,
    }, token=token, timeout=60)
    if not must("Bug 2 反例：旧 payload 应被 schema 拒绝", code == 422,
                f"=> {code} (期望 422)"):
        failed += 1

    print(f"\n====== 端到端测试结束：{'全部通过' if failed == 0 else f'失败 {failed} 项'} ======")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
