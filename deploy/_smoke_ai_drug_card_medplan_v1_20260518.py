"""[PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 远程冒烟 + pytest

1) 在后端容器内执行新增测试用例 test_ai_drug_card_medplan_v1_20260518.py
2) 外网 HTTPS 冒烟：
   - check-batch 接口 401（未登录）
   - register/login 后调用 check-batch、create、list（with consultant）端到端流程
"""
from __future__ import annotations

import json
import random
import string
import sys
import time
import urllib.parse
import urllib.request

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-6000:])
    if show and err.strip():
        print("STDERR:", err[-1500:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc})")
    return rc, out, err


def http_request(method, path, headers=None, data=None, timeout=20):
    # URL-encode non-ASCII (中文药名)
    if "?" in path:
        base, qs = path.split("?", 1)
        # 保留 = & 等结构字符，仅对 value 中文做编码
        url = BASE_URL + base + "?" + urllib.parse.quote(qs, safe="=&")
    else:
        url = BASE_URL + urllib.parse.quote(path, safe="/:")
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def main():
    # 1) 容器内 pytest
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    backend = f"{DEPLOY_ID}-backend"
    try:
        print("\n=== 在 backend 容器内运行 pytest ===")
        # 先检查是否已安装 pytest
        rc, out, _ = run(client, f"docker exec {backend} python -c 'import pytest, httpx, aiosqlite' 2>&1",
                         ignore_err=True, show=False)
        if rc != 0:
            print("  缺少 pytest 依赖，安装中...")
            run(client, f"docker exec {backend} pip install --quiet pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -10",
                ignore_err=True, timeout=300)
        rc, out, err = run(
            client,
            f"docker exec -w /app {backend} python -m pytest tests/test_ai_drug_card_medplan_v1_20260518.py -v --tb=short 2>&1",
            timeout=600, ignore_err=True,
        )
        if "passed" not in out and rc != 0:
            print("  ⚠️ pytest FAILED")
            return 1
    finally:
        client.close()

    # 2) 外网 HTTPS smoke
    print("\n=== HTTPS smoke ===")
    rnd = ''.join(random.choices(string.digits, k=4))
    phone = f"139{rnd}{int(time.time()) % 1000000:06d}"
    print(f"  phone = {phone}")

    # 401 check-batch
    s, _ = http_request("GET", "/api/health-plan/medications/check-batch?drug_names=test")
    print(f"  unauthorized check-batch: {s}")
    assert s == 401, f"expect 401 got {s}"

    # register
    s, _ = http_request("POST", "/api/auth/register", data={
        "phone": phone, "password": "test123", "nickname": "测试小白",
    })
    print(f"  register: {s}")
    assert s in (200, 201), f"register failed: {s}"

    # login
    s, body = http_request("POST", "/api/auth/login", data={
        "phone": phone, "password": "test123",
    })
    print(f"  login: {s}")
    assert s == 200, f"login failed: {s} {body}"
    token = json.loads(body).get("access_token") or json.loads(body).get("token")
    assert token
    h = {"Authorization": f"Bearer {token}"}

    # check-batch empty → all false
    s, body = http_request("GET", "/api/health-plan/medications/check-batch?drug_names=阿莫西林,布洛芬", headers=h)
    print(f"  check-batch (empty plans): {s} {body[:200]}")
    assert s == 200
    data = json.loads(body)["data"]
    assert data["阿莫西林"] is False and data["布洛芬"] is False

    # create with generic_name
    s, body = http_request("POST", "/api/health-plan/medications", headers=h, data={
        "medicine_name": "阿莫西林胶囊",
        "generic_name": "阿莫西林",
        "dosage_value": "1", "dosage_unit": "片",
        "frequency_per_day": 1, "custom_times": ["08:00"], "remind_time": "08:00",
        "time_period": "custom", "long_term": True,
        "start_date": time.strftime("%Y-%m-%d"),
        "guidance": "饭后",
    })
    print(f"  create: {s} {body[:200]}")
    assert s == 200, f"create failed: {s} {body}"
    j = json.loads(body)
    assert j.get("generic_name") == "阿莫西林"

    # check-batch hit
    s, body = http_request("GET", "/api/health-plan/medications/check-batch?drug_names=阿莫西林,布洛芬", headers=h)
    print(f"  check-batch (after create): {s} {body[:200]}")
    data = json.loads(body)["data"]
    assert data["阿莫西林"] is True, f"expected True got {data}"

    # consultant_id=99 → not hit
    s, body = http_request("GET", "/api/health-plan/medications/check-batch?drug_names=阿莫西林&consultant_id=99", headers=h)
    data = json.loads(body)["data"]
    print(f"  check-batch consultant=99: {data}")
    assert data["阿莫西林"] is False

    # list with consultant_id=0
    s, body = http_request("GET", "/api/health-plan/medications/list?tab=in_progress&consultant_id=0", headers=h)
    print(f"  list (self): {s}")
    assert s == 200
    items = json.loads(body)["items"]
    assert any(it["medicine_name"] == "阿莫西林胶囊" for it in items), "self list missing"

    # list with consultant_id=99 (空)
    s, body = http_request("GET", "/api/health-plan/medications/list?tab=in_progress&consultant_id=99", headers=h)
    items = json.loads(body)["items"]
    print(f"  list (consultant=99) items={len(items)}")
    assert all(it["medicine_name"] != "阿莫西林胶囊" for it in items)

    print("\n=== ✅ 全部 smoke 通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
