#!/usr/bin/env python3
"""[BUG-FIX 2026-05-16] 健康自查 start 接口连续 5 次稳定性测试

验证清单 #3：三端抽屉提交后均能稳定返回 AI 健康参考回答（连续 5 次以上无"分析失败"）
此处验证后端接口稳定性，三端共用同一后端。
"""
import json
import ssl
import sys
import time
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def request(method, path, payload=None, token=None, timeout=120):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = BASE + path
    headers = {"Content-Type": "application/json", "User-Agent": "stress/1.0"}
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
            return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def main():
    # 登录
    request("POST", "/api/auth/sms-code", {"phone": "13800138000", "type": "login"})
    code, body = request("POST", "/api/auth/sms-login", {"phone": "13800138000", "code": "123456"})
    if code != 200:
        print(f"[FAIL] 登录失败 {code}")
        return 1
    token = body["access_token"]

    # 找按钮
    code, btns = request("GET", "/api/function-buttons", token=token)
    health_btn = next((b for b in btns if b.get("button_type") == "health_self_check"), None)
    if not health_btn:
        print("[FAIL] 找不到 health_self_check 按钮")
        return 1
    button_id = health_btn["id"]
    template_id = health_btn.get("health_check_template_id") or 1

    # 模板
    code, tpl = request("GET", f"/api/health-self-check/template/{template_id}", token=token)
    if code != 200:
        print(f"[FAIL] 模板加载 {code}")
        return 1

    print(f"\n====== 连续 5 次提交健康自查（button_id={button_id}, template={template_id}） ======")
    success = 0
    fail = 0
    parts = tpl["body_parts_detail"]
    durations = tpl["duration_options"]
    for i in range(1, 6):
        part = parts[(i - 1) % len(parts)]
        symptom = part["symptoms"][0]
        duration = durations[(i - 1) % len(durations)]
        payload = {
            "template_id": template_id,
            "button_id": button_id,
            "body_part_id": part["id"],
            "symptoms": [symptom],
            "duration": duration,
        }
        t0 = time.time()
        code, body = request("POST", "/api/health-self-check/start", payload, token=token, timeout=120)
        elapsed = time.time() - t0
        ai_content = body.get("ai_content", "") if isinstance(body, dict) else ""
        ok = code == 200 and len(ai_content) > 0
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] 第{i}次 部位={part['name']}, 症状={symptom}, 持续={duration} => HTTP {code}, AI 长度={len(ai_content)}, 耗时 {elapsed:.1f}s")
        if ok:
            success += 1
        else:
            fail += 1
            print(f"        错误详情: {str(body)[:200]}")

    print(f"\n====== 结果：{success}/5 通过，{fail} 失败 ======")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
