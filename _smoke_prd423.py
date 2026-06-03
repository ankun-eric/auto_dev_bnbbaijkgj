#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[PRD-423] 服务器侧非UI自动化测试 - 验证 10 个埋点事件 + 主要页面访问"""
import sys, time, json
sys.stdout.reconfigure(encoding='utf-8')
import urllib.request, ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = []

def req(method, path, body=None, name=None):
    url = BASE + path
    data = None
    headers = {'Content-Type': 'application/json'}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, context=ctx, timeout=15) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        content = e.read().decode('utf-8', errors='replace')[:200]
    except Exception as e:
        status = -1
        content = str(e)[:200]
    ok = 200 <= status < 400
    results.append((name or f"{method} {path}", status, ok, content[:150]))
    return status, content

# 1. EVT 上报（10 个事件全部尝试）
events = [
    ("EVT-01", "ai_chat_page_view", {"default_target": "self"}),
    ("EVT-02", "ai_chat_target_switch", {"from_target": "self", "to_target": "family"}),
    ("EVT-03", "ai_chat_archive_history", {"session_id": 123, "message_count": 8}),
    ("EVT-04", "ai_chat_profile_row_show", {"target_name": "妈妈"}),
    ("EVT-05", "ai_chat_profile_card_expand", {"target_name": "妈妈"}),
    ("EVT-06", "ai_chat_profile_card_collapse", {"trigger": "icon"}),
    ("EVT-07", "ai_chat_scroll_to_bottom_click", {"unread_count": 2}),
    ("EVT-08", "ai_chat_punchcard_drag", {"from_y": 120, "to_y": 220}),
    ("EVT-09", "ai_chat_no_self_profile_tip_click", {}),
    ("EVT-10", "ai_chat_send", {"target_type": "self", "content_length": 18}),
]
for tag, ev, params in events:
    req("POST", "/api/analytics/track", {"event": ev, "params": params, "ts": int(time.time()*1000)}, name=f"{tag} {ev}")

# 2. 批量上报
req("POST", "/api/analytics/track/batch",
    {"items": [{"event": e, "params": p, "ts": int(time.time()*1000)} for _, e, p in events[:3]]},
    name="track/batch")

# 3. 关键页面/接口
req("GET", "/", name="H5 root")
req("GET", "/ai-home", name="H5 ai-home")
req("GET", "/chat-history", name="H5 chat-history")
req("GET", "/api/family/members", name="API family members")  # 可能 401，但接口应能响应
req("GET", "/api/ai-home-config", name="API ai-home-config")

# 输出报告
print("=" * 80)
print(f"{'NAME':<50} {'STATUS':<8} {'OK':<5}")
print("=" * 80)
ok_cnt = 0
fail_cnt = 0
for name, status, ok, content in results:
    flag = '✓' if ok else '✗'
    print(f"{name:<50} {status:<8} {flag:<5}")
    if ok:
        ok_cnt += 1
    else:
        fail_cnt += 1
        print(f"   -> {content}")

print("=" * 80)
print(f"PASS: {ok_cnt}  FAIL: {fail_cnt}  TOTAL: {len(results)}")
sys.exit(0 if fail_cnt == 0 else 1)
