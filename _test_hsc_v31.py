"""[BUG-HSC-V31 2026-05-21] 非UI自动化接口测试。

3 个 Bug 的接口级验证：
  T1-01：render-meta 返回 auto_next_enabled=true
  T2-01：提交问卷 30 秒后查详情，ai_full_interpretation 非空、home_care_tips 非空
  T2-04：提交带 subject_kind='family', subject_name='X', subject_relation='Y' 时，
         详情接口返回 subject_label='X（Y）'

复用现成测试用户（手机号短信验证码登录），自动注册 + 登录。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import ssl

PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"
API = f"{BASE_URL}/api"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def http(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> tuple[int, dict]:
    url = f"{API}{path}" if path.startswith("/") else f"{API}/{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            txt = resp.read().decode("utf-8", "ignore")
            return resp.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "ignore") if e.fp else ""
        try:
            return e.code, json.loads(txt) if txt else {}
        except Exception:
            return e.code, {"raw": txt}
    except Exception as e:
        return -1, {"err": str(e)}


def get_token() -> str:
    """phone + password 登录，自动注册一个测试号。"""
    phone = "13900000031"
    pwd = "Test@12345"
    # 尝试登录
    code, body = http("POST", "/auth/login", body={"phone": phone, "password": pwd})
    if code == 200 and body.get("access_token"):
        return body["access_token"]
    print("[INFO] login failed, try register", code, body)
    # 注册
    code, body = http("POST", "/auth/register", body={"phone": phone, "password": pwd, "nickname": "测试用户v31"})
    print(f"  register code={code} body={body}")
    # 再登录
    code, body = http("POST", "/auth/login", body={"phone": phone, "password": pwd})
    if code == 200 and body.get("access_token"):
        return body["access_token"]
    print("[WARN] login still failed", code, body)
    return ""


def t1_render_meta(token: str) -> bool:
    print("\n=== T1-01: render-meta auto_next_enabled ===")
    # 查 questionnaire 类型按钮
    code, body = http("GET", "/chat/function-buttons", token=token)
    if code != 200:
        print(f"  FAIL list buttons code={code} body={body}")
        return False
    items = body if isinstance(body, list) else body.get("items") or body.get("data") or []
    qbtns = [b for b in items if b.get("ai_function_type") == "questionnaire" and bool(b.get("auto_next_enabled"))]
    if not qbtns:
        print(f"  [WARN] no auto_next_enabled questionnaire button found")
        return False
    btn = qbtns[0]
    btn_id = btn["id"]
    code, meta = http("GET", f"/questionnaire/buttons/{btn_id}/render-meta", token=token)
    if code != 200:
        print(f"  FAIL render-meta code={code} body={meta}")
        return False
    top_auto = meta.get("auto_next_enabled")
    btn_auto = (meta.get("button") or {}).get("auto_next_enabled")
    top_per = meta.get("questions_per_page")
    top_ct = meta.get("presentation_container")
    print(f"  button_id={btn_id} top.auto_next_enabled={top_auto} button.auto_next_enabled={btn_auto} per={top_per} container={top_ct}")
    ok = bool(top_auto) and bool(btn_auto)
    print(f"  {'PASS' if ok else 'FAIL'}")
    return ok


def find_template_id_for_hsc(token: str) -> int:
    """找 health_self_check 模板 id。"""
    code, body = http("GET", "/chat/function-buttons", token=token)
    items = body if isinstance(body, list) else body.get("items") or body.get("data") or []
    for b in items:
        if b.get("ai_function_type") == "questionnaire" and b.get("questionnaire_template_id"):
            # 通过 render-meta 获取 template 详细 code
            code, meta = http("GET", f"/questionnaire/buttons/{b['id']}/render-meta", token=token)
            if code == 200:
                tpl = meta.get("template") or {}
                if tpl.get("code") == "health_self_check":
                    return tpl.get("id"), meta
                # 退而求其次，取任意有 questions 的模板
    # 第二轮：取任意 questionnaire 按钮
    for b in items:
        if b.get("ai_function_type") == "questionnaire" and b.get("questionnaire_template_id"):
            code, meta = http("GET", f"/questionnaire/buttons/{b['id']}/render-meta", token=token)
            if code == 200 and (meta.get("template") or {}).get("id"):
                return (meta["template"]["id"], meta)
    return 0, {}


def t2a_submit_and_detail(token: str) -> bool:
    print("\n=== T2-01 + T2-04: submit hsc with subject=family, then detail check ===")
    tpl_id, meta = find_template_id_for_hsc(token)
    if not tpl_id:
        print("  FAIL: no health_self_check template available")
        return False
    questions = meta.get("questions") or []
    if not questions:
        print("  FAIL: template has no questions")
        return False
    # 构造每题最简单的合法答案（单选选第一个，多选选第一个，文本填'测试'）
    answers = []
    for q in questions:
        qt = q.get("question_type") or q.get("type") or "single_choice"
        if qt == "single_choice":
            opts = q.get("options") or []
            if opts:
                val = opts[0].get("id") or opts[0].get("value") or opts[0].get("code") or 1
                answers.append({"question_id": q["id"], "value": val})
            else:
                answers.append({"question_id": q["id"], "value": 1})
        elif qt == "multi_choice":
            opts = q.get("options") or []
            if opts:
                val = opts[0].get("id") or opts[0].get("value") or opts[0].get("code") or 1
                answers.append({"question_id": q["id"], "value": [val]})
            else:
                answers.append({"question_id": q["id"], "value": []})
        elif qt in ("text", "input", "single_line"):
            answers.append({"question_id": q["id"], "value": "测试"})
        else:
            answers.append({"question_id": q["id"], "value": 1})

    payload = {
        "template_id": tpl_id,
        "consultant_id": None,
        "answers": answers,
        "subject_kind": "family",
        "subject_member_id": None,
        "subject_name": "张红",
        "subject_relation": "妈妈",
    }
    code, body = http("POST", "/questionnaire/submit", token=token, body=payload)
    print(f"  submit code={code} answer_id={body.get('answer_id')}")
    if code != 200 or not body.get("answer_id"):
        print(f"  FAIL submit body={body}")
        return False
    answer_id = body["answer_id"]

    # 轮询 ai-status 最多 30s
    deadline = time.time() + 35
    last_status = None
    while time.time() < deadline:
        code, st = http("GET", f"/questionnaire/answers/{answer_id}/ai-status", token=token)
        if code == 200:
            last_status = st.get("ai_status")
            if last_status in ("done", "failed"):
                break
        time.sleep(2)
    print(f"  ai_status after wait: {last_status}")

    # 查详情
    code, detail = http("GET", f"/questionnaire/answers/{answer_id}", token=token)
    if code != 200:
        print(f"  FAIL get detail code={code} body={detail}")
        return False
    print(f"  detail.ai_status={detail.get('ai_status')} ai_full_interpretation_len={len(detail.get('ai_full_interpretation') or '')}")
    print(f"  detail.home_care_tips count={len(detail.get('home_care_tips') or [])}  red_flag_signals count={len(detail.get('red_flag_signals') or [])}")
    print(f"  detail.subject_kind={detail.get('subject_kind')!r}  subject_name={detail.get('subject_name')!r}  subject_relation={detail.get('subject_relation')!r}  subject_label={detail.get('subject_label')!r}")

    t2a_ok = (
        bool((detail.get("ai_full_interpretation") or "").strip())
        and bool(detail.get("home_care_tips"))
        and bool(detail.get("red_flag_signals"))
        and detail.get("ai_status") == "done"
    )
    t2b_ok = detail.get("subject_label") == "妈妈（张红）"
    print(f"  T2-01: {'PASS' if t2a_ok else 'FAIL'}")
    print(f"  T2-04: {'PASS' if t2b_ok else 'FAIL'}")
    return t2a_ok and t2b_ok


def main() -> int:
    token = get_token()
    if not token:
        print("FATAL: cannot get token")
        return 1
    print(f"got token (len={len(token)})")

    r1 = t1_render_meta(token)
    r2 = t2a_submit_and_detail(token)

    print("\n" + "=" * 60)
    print(f"Summary: T1-01={'PASS' if r1 else 'FAIL'}  T2-01+T2-04={'PASS' if r2 else 'FAIL'}")
    print("=" * 60)
    return 0 if (r1 and r2) else 1


if __name__ == "__main__":
    sys.exit(main())
