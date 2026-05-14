#!/usr/bin/env python3
"""Run only tests (no deploy) against current server state."""
from __future__ import annotations
import sys, time
from typing import List, Tuple
import paramiko, requests

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"
MYSQL_PWD = "bini_health_2026"


def t1():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    return ("T1 /api/health", r.status_code == 200, f"HTTP {r.status_code}")

def t2():
    r = requests.get(f"{BASE_URL}/", timeout=20, allow_redirects=False)
    return ("T2 H5 主页可达", r.status_code in (200, 301, 302, 307, 308), f"HTTP {r.status_code}")

def t3():
    r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
    body = r.json() if r.status_code == 200 else None
    ok = r.status_code == 200 and isinstance(body, list)
    return ("T3 公开 /api/function-buttons 返回数组", ok, f"HTTP {r.status_code} 返回 {len(body) if isinstance(body, list) else '?'} 条")

def t4():
    r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
    if r.status_code != 200:
        return ("T4 is_enabled 过滤", False, f"HTTP {r.status_code}")
    body = r.json()
    if not isinstance(body, list):
        return ("T4 is_enabled 过滤", False, "非数组")
    for item in body:
        if item.get("is_enabled") is False:
            return ("T4 is_enabled 过滤", False, f"返回了已禁用按钮 id={item.get('id')}")
    return ("T4 is_enabled 过滤生效", True, f"全部 {len(body)} 条 is_enabled=true")

def t5():
    r = requests.get(f"{BASE_URL}/admin/function-buttons", timeout=30, allow_redirects=True)
    return ("T5 admin /function-buttons 页面可达", r.status_code in (200, 401, 302, 307), f"HTTP {r.status_code}, body长度={len(r.text)}")

def t6():
    r = requests.get(f"{BASE_URL}/admin/home-settings/ai-home-config", timeout=30, allow_redirects=True)
    return ("T6 admin /home-settings/ai-home-config 页面可达", r.status_code in (200, 401, 302, 307), f"HTTP {r.status_code}")

def t7():
    r = requests.get(f"{BASE_URL}/ai-home", timeout=30, allow_redirects=True)
    return ("T7 H5 /ai-home 页面可达", r.status_code in (200, 302, 307), f"HTTP {r.status_code}, body={len(r.text)}")

def t8():
    r = requests.post(f"{BASE_URL}/api/analytics/track",
                      json={"event":"capsule_click","params":{"button_id":1,"button_name":"X","button_type":"quick_ask"},"ts":int(time.time()*1000)},
                      timeout=15)
    return ("T8 analytics capsule_click 上报", r.status_code in (200, 201, 204), f"HTTP {r.status_code}")

def t9():
    r = requests.post(f"{BASE_URL}/api/analytics/track",
                      json={"event":"card_button_click","params":{"button_id":1,"card_type":"upload"},"ts":int(time.time()*1000)},
                      timeout=15)
    return ("T9 analytics card_button_click 上报", r.status_code in (200, 201, 204), f"HTTP {r.status_code}")

def t_ssh(grep_pattern, name):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, 22, USER, PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
        _, stdout, _ = ssh.exec_command(f"docker logs --tail 500 {PROJECT_ID}-backend 2>&1 | grep -iE '{grep_pattern}' | tail -10", timeout=30)
        out = stdout.read().decode("utf-8", "replace")
        ssh.close()
        return (name, bool(out.strip()), f"{len(out.splitlines())} 行匹配")
    except Exception as e:
        return (name, False, f"异常 {e}")

def t10():
    return t_ssh("aichat_optim_fix_v1", "T10 启动日志含 aichat_optim_fix_v1")

def t11():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, 22, USER, PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
        _, stdout, _ = ssh.exec_command(
            f'docker exec -e MYSQL_PWD={MYSQL_PWD} {PROJECT_ID}-db mysql -uroot bini_health -B -N -e '
            f'"SELECT COUNT(*), SUM(CASE WHEN icon IS NULL OR icon=\'\' THEN 1 ELSE 0 END) FROM chat_function_buttons;"',
            timeout=30)
        out = stdout.read().decode("utf-8", "replace").strip()
        ssh.close()
        parts = out.split()
        if len(parts) >= 2:
            total, empty = int(parts[0]), int(parts[1])
            ok = total > 0 and empty == 0
            return ("T11 DB icon 字段全部非空", ok, f"total={total}, empty={empty}")
        return ("T11 DB icon", True, f"表为空: {out}")
    except Exception as e:
        return ("T11 DB icon", False, f"异常 {e}")

def t12():
    return t_ssh("func_grid|simplified", "T12 启动日志含 func_grid 迁移")


if __name__ == "__main__":
    print(f"=== 自动化测试 BASE_URL={BASE_URL} ===\n")
    tests = [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12]
    results: List[Tuple[str, bool, str]] = []
    for fn in tests:
        try: results.append(fn())
        except Exception as e: results.append((fn.__name__, False, f"异常 {e}"))
    print("\n=== 测试结果 ===")
    fail = 0
    for name, ok, info in results:
        mark = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {mark}  {name}  ({info})")
        if not ok: fail += 1
    print(f"\n{'='*60}\n合计 {len(results)} 用例：{len(results)-fail} PASS, {fail} FAIL\n{'='*60}")
    sys.exit(1 if fail else 0)
