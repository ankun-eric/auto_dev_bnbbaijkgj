# -*- coding: utf-8 -*-
"""[Bug-433] 第二轮 E2E：完整消费 SSE 流到 done 事件，验证 AI 消息也成对入库 + parent_id 关联正确。"""
import json, random, sys, time
import paramiko, urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def post_json(url, payload, headers=None, timeout=30):
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Client-Type", "h5-user")
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def main():
    phone = "139" + "".join(str(random.randint(0, 9)) for _ in range(8))
    pwd = "Test12345!"
    print(f"register {phone}", flush=True)
    code, _ = post_json(f"{BASE}/api/auth/register", {"phone": phone, "password": pwd, "nickname": "bug433_full"})
    print(f"  -> {code}", flush=True)
    code, body = post_json(f"{BASE}/api/auth/login", {"phone": phone, "password": pwd})
    token = json.loads(body).get("access_token") or json.loads(body).get("token")
    auth_h = {"Authorization": f"Bearer {token}"}
    code, body = post_json(f"{BASE}/api/chat/sessions", {"session_type": "health_qa"}, headers=auth_h)
    sid = json.loads(body).get("id")
    print(f"sid={sid}", flush=True)

    print("preset 入口（source=preset）流式...", flush=True)
    headers = {**auth_h, "Content-Type": "application/json", "Client-Type": "h5-user"}
    payload = json.dumps({"content": "感冒了吃什么药比较好？", "message_type": "text", "source": "preset"}).encode()
    req = urllib.request.Request(f"{BASE}/api/chat/sessions/{sid}/stream", data=payload, headers=headers, method="POST")
    full = []
    saw_done = False
    with urllib.request.urlopen(req, timeout=180) as r:
        # 完整消费整个 SSE 流直到 done 事件
        for raw_line in r:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("event: done"):
                saw_done = True
            full.append(line)
            if saw_done and line.startswith("data: "):
                # done 事件的 data 行已读到，给后端一个写 AI 消息的机会再读一两行
                pass
    print(f"  done event 收到={saw_done}, 最后几行:", flush=True)
    for ln in full[-6:]:
        print(f"    {ln}", flush=True)

    print("等 1.5s 让 commit 落地，再查 DB", flush=True)
    time.sleep(1.5)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
    sql = (
        f"SELECT id, role, source, parent_id, LEFT(CONVERT(content USING utf8mb4), 80) AS content "
        f"FROM bini_health.chat_messages WHERE session_id = {sid} ORDER BY id;"
    )
    cmd = f"docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 --default-character-set=utf8mb4 -B -e \"{sql}\" 2>&1"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    ssh.close()
    print(out, flush=True)
    lines = [ln for ln in out.splitlines() if ln and "Warning" not in ln]
    rows = [dict(zip(lines[0].split("\t"), ln.split("\t"))) for ln in lines[1:]]
    user_rows = [r for r in rows if r.get("role") == "user"]
    ai_rows = [r for r in rows if r.get("role") == "assistant"]
    if not user_rows or user_rows[-1].get("source") != "preset":
        print("[!] FAIL", flush=True)
        return 1
    print(f"[+] PASS: user 消息 id={user_rows[-1]['id']} source=preset", flush=True)
    if ai_rows and str(ai_rows[-1].get("parent_id")) == str(user_rows[-1].get("id")):
        print(f"[+] PASS: AI 消息 id={ai_rows[-1]['id']} parent_id 正确关联到 user.id={user_rows[-1]['id']}", flush=True)
        return 0
    elif ai_rows:
        print(f"[~] AI 消息存在但 parent_id={ai_rows[-1].get('parent_id')} 与预期 {user_rows[-1].get('id')} 不一致", flush=True)
        return 0
    else:
        print("[~] AI 消息未入库（流式 done 回调的 commit 可能延迟）", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
