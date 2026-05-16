"""[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
服务器侧非UI自动化测试：验证 SSE 通用 intent 协议分发 / 报告解读引擎 /
档案串味修复（修 A/B/C）/ is_self 回填迁移。

运行：python test_server_report_interpret_intent.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Dict, List, Optional

import requests

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27",
).rstrip("/")
API = f"{BASE_URL}/api"
TIMEOUT = 30

# 复用后端内置测试号 + 固定验证码 123456（auth.py::TEST_PHONES）
TEST_PHONE = os.environ.get("TEST_PHONE", "13800138000")
TEST_CODE = os.environ.get("TEST_CODE", "123456")


_results: List[Dict] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    _results.append({"name": name, "ok": bool(ok), "detail": detail})
    flag = "✅" if ok else "❌"
    print(f"{flag} {name} {('- ' + detail) if detail else ''}", flush=True)


def _login() -> Optional[str]:
    """复用后端 sms-code + sms-login 测试号通道。失败则跳过依赖 token 的用例。"""
    # 1) 触发验证码（后端 TEST_PHONES 命中时直接固定 123456）
    try:
        requests.post(
            f"{API}/auth/sms-code",
            json={"phone": TEST_PHONE, "type": "login"},
            timeout=TIMEOUT,
        )
    except Exception as e:
        _record("login.sms_code", False, f"网络异常 {e}")
        return None
    # 2) 用固定验证码登录
    try:
        r2 = requests.post(
            f"{API}/auth/sms-login",
            json={"phone": TEST_PHONE, "code": TEST_CODE},
            timeout=TIMEOUT,
        )
        if r2.status_code != 200:
            _record(
                "login.login",
                False,
                f"HTTP {r2.status_code} body={r2.text[:200]}",
            )
            return None
        data = r2.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            _record("login.token", False, f"返回无 token: {data}")
            return None
        _record("login.token", True)
        return token
    except Exception as e:
        _record("login.login", False, f"异常 {e}")
        return None


def _h(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_session(token: str) -> Optional[int]:
    try:
        r = requests.post(
            f"{API}/chat/sessions",
            headers=_h(token),
            json={"session_type": "health_qa"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            _record("session.create", False, f"HTTP {r.status_code} {r.text[:200]}")
            return None
        data = r.json()
        sid = data.get("id") or data.get("session_id")
        _record("session.create", bool(sid), f"sid={sid}")
        return sid
    except Exception as e:
        _record("session.create", False, str(e))
        return None


def _sse_post(token: str, sid: int, body: Dict, name: str) -> Dict:
    """发起 SSE POST，收集所有 event/data 行，返回结果汇总。"""
    url = f"{API}/chat/sessions/{sid}/stream"
    events: List[Dict] = []
    try:
        with requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=body,
            stream=True,
            timeout=TIMEOUT,
        ) as resp:
            if resp.status_code != 200:
                _record(name, False, f"HTTP {resp.status_code} {resp.text[:200]}")
                return {"ok": False, "events": events}

            current_event = "message"
            for raw in resp.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                line = raw.strip("\r")
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_str = line[len("data:") :].strip()
                    if not data_str:
                        continue
                    try:
                        payload = json.loads(data_str)
                    except Exception:
                        payload = {"_raw": data_str}
                    events.append({"event": current_event, "data": payload})
                    if current_event == "done":
                        break
        return {"ok": True, "events": events}
    except Exception as e:
        _record(name, False, f"异常 {e}")
        return {"ok": False, "events": events}


def test_intent_report_interpret_dispatch(token: str) -> None:
    """T-INTENT-1：显式 intent='report_interpret' + 假图片 URL，
    应被分发到 ReportInterpretEngine，并以 retake / report_interpret meta 完成。"""
    sid = _create_session(token)
    if not sid:
        return
    body = {
        "content": "我上传了一份体检报告，请帮我解读",
        "message_type": "text",
        "source": "preset",
        "intent": "report_interpret",
        "image_urls": [f"{BASE_URL}/non-existent-{uuid.uuid4().hex}.jpg"],
        "button_type": "report_interpret",
    }
    res = _sse_post(token, sid, body, "T-INTENT-1.sse")
    if not res["ok"]:
        _record("T-INTENT-1.dispatch", False, "SSE 异常")
        return
    done_evs = [e for e in res["events"] if e["event"] == "done"]
    if not done_evs:
        _record("T-INTENT-1.dispatch", False, "未收到 done 事件")
        return
    meta = done_evs[-1]["data"].get("meta") or {}
    mt = (meta.get("message_type") or "").lower()
    ct = (meta.get("card_type") or "").lower()
    ok = mt.startswith("report_interpret") or ct.startswith("report")
    _record(
        "T-INTENT-1.dispatch",
        ok,
        f"meta.message_type={mt} card_type={ct}",
    )


def test_intent_report_interpret_retake_on_bad_image(token: str) -> None:
    """T-INTENT-2：图片明显不可达 → 引擎给出 retake 卡片（不调用 LLM）。"""
    sid = _create_session(token)
    if not sid:
        return
    body = {
        "content": "解读这张图",
        "message_type": "text",
        "intent": "report_interpret",
        "image_urls": [
            f"{BASE_URL}/definitely-not-an-image-{uuid.uuid4().hex}.bin",
        ],
        "button_type": "report_interpret",
    }
    res = _sse_post(token, sid, body, "T-INTENT-2.sse")
    done_evs = [e for e in res["events"] if e["event"] == "done"]
    if not done_evs:
        _record("T-INTENT-2.retake", False, "未收到 done 事件")
        return
    meta = done_evs[-1]["data"].get("meta") or {}
    ct = (meta.get("card_type") or "").lower()
    ok = ct == "report_retake"
    _record("T-INTENT-2.retake", ok, f"card_type={ct}")


def test_intent_backward_compat_plain_message(token: str) -> None:
    """T-INTENT-3：老客户端不带 intent / image_urls，普通文字消息行为不变。"""
    sid = _create_session(token)
    if not sid:
        return
    body = {
        "content": "你好，今天天气怎么样？",
        "message_type": "text",
        "source": "text",
    }
    res = _sse_post(token, sid, body, "T-INTENT-3.sse")
    done_evs = [e for e in res["events"] if e["event"] == "done"]
    delta_evs = [e for e in res["events"] if e["event"] == "delta"]
    # 老路径要么返回 done，要么收到至少一个 delta。两者都没有就视为失败
    ok = bool(done_evs) or bool(delta_evs)
    _record(
        "T-INTENT-3.backward_compat",
        ok,
        f"done={len(done_evs)} delta={len(delta_evs)}",
    )


def test_switch_member_self_writes_switch_summary(token: str) -> None:
    """T-SWITCH-1：switch-member 切回"本人"应将 family_member_id 绑定到
    is_self FamilyMember（非 None），并写入 switch_summary 系统消息。"""
    sid = _create_session(token)
    if not sid:
        return
    try:
        r = requests.post(
            f"{API}/chat/sessions/{sid}/switch-member",
            headers=_h(token),
            json={"family_member_id": None},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            _record(
                "T-SWITCH-1.switch_self",
                False,
                f"HTTP {r.status_code} {r.text[:200]}",
            )
            return
        data = r.json()
        fmid = data.get("family_member_id")
        summary = data.get("switch_summary") or ""
        ok = fmid is not None and "切换" in summary
        _record(
            "T-SWITCH-1.switch_self",
            ok,
            f"family_member_id={fmid} summary={summary[:80]}",
        )
    except Exception as e:
        _record("T-SWITCH-1.switch_self", False, str(e))
        return

    # 复查消息列表中是否能找到一条 system 类型的 switch_summary 记录
    try:
        r2 = requests.get(
            f"{API}/chat/sessions/{sid}/messages",
            headers=_h(token),
            timeout=TIMEOUT,
        )
        if r2.status_code != 200:
            _record(
                "T-SWITCH-1.history_check",
                False,
                f"HTTP {r2.status_code} {r2.text[:200]}",
            )
            return
        msgs = r2.json()
        if isinstance(msgs, dict):
            msgs = msgs.get("items") or msgs.get("messages") or []
        sys_msgs = [
            m
            for m in msgs
            if isinstance(m, dict)
            and (m.get("role") == "system" or m.get("message_metadata", {}).get("kind") == "switch_summary")
        ]
        _record(
            "T-SWITCH-1.history_check",
            len(sys_msgs) > 0,
            f"system_msg_count={len(sys_msgs)}",
        )
    except Exception as e:
        _record("T-SWITCH-1.history_check", False, str(e))


def test_family_self_backfill(token: str) -> None:
    """T-BACKFILL：登录用户应至少存在一条 is_self=True 的 FamilyMember
    （由启动迁移或 switch-member 懒创建保证）。"""
    try:
        r = requests.get(f"{API}/family/members", headers=_h(token), timeout=TIMEOUT)
        if r.status_code != 200:
            _record(
                "T-BACKFILL.is_self",
                False,
                f"HTTP {r.status_code} {r.text[:200]}",
            )
            return
        data = r.json()
        items = data if isinstance(data, list) else (data.get("items") or data.get("data") or [])
        has_self = any(bool(it.get("is_self")) for it in items if isinstance(it, dict))
        _record("T-BACKFILL.is_self", has_self, f"family_member_count={len(items)}")
    except Exception as e:
        _record("T-BACKFILL.is_self", False, str(e))


def main() -> int:
    print(f"BASE_URL={BASE_URL}")
    # 健康检查
    try:
        r = requests.get(f"{API}/health", timeout=10)
        _record(
            "service.health",
            r.status_code == 200,
            f"HTTP {r.status_code}",
        )
    except Exception as e:
        _record("service.health", False, str(e))

    token = _login()
    if token:
        # 触发一次 switch-member（切回本人）以驱动懒创建 is_self，再做 backfill 校验
        try:
            sid_tmp = _create_session(token)
            if sid_tmp:
                requests.post(
                    f"{API}/chat/sessions/{sid_tmp}/switch-member",
                    headers=_h(token),
                    json={"family_member_id": None},
                    timeout=TIMEOUT,
                )
        except Exception:
            pass

        test_family_self_backfill(token)
        test_intent_report_interpret_dispatch(token)
        test_intent_report_interpret_retake_on_bad_image(token)
        test_intent_backward_compat_plain_message(token)
        test_switch_member_self_writes_switch_summary(token)
    else:
        print("⚠️  无 token，跳过受保护接口用例", flush=True)

    total = len(_results)
    passed = sum(1 for r in _results if r["ok"])
    failed = total - passed
    print("\n====== Summary ======")
    print(f"total={total} passed={passed} failed={failed}")
    for r in _results:
        if not r["ok"]:
            print(f"  ✗ {r['name']}: {r['detail']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
