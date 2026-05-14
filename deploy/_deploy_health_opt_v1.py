#!/usr/bin/env python3
"""[PRD-HEALTH-OPT-V1 2026-05-14] 健康档案优化 部署 + 自动化测试

流程：
  1. SSH 到服务器
  2. git fetch + reset --hard origin/master
  3. docker compose build --no-cache backend admin-web h5-web
  4. docker compose up -d backend admin-web h5-web
  5. 等待容器就绪
  6. 执行服务器自动化测试
"""
from __future__ import annotations
import sys
import time
from typing import List, Tuple

import paramiko
import requests

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"


def run(ssh, cmd: str, timeout: int = 1800) -> Tuple[int, str, str]:
    print(f"\n>>> SSH: {cmd[:140]}{'...' if len(cmd) > 140 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out_lines: List[str] = []
    for line in iter(stdout.readline, ""):
        if not line:
            break
        sys.stdout.write(line)
        sys.stdout.flush()
        out_lines.append(line)
    code = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace")
    if err:
        print(f"[stderr] {err.strip()[:500]}")
    return code, "".join(out_lines), err


def deploy():
    print(f"=== 连接 {HOST} ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                allow_agent=False, look_for_keys=False)
    try:
        run(ssh, f"cd {REMOTE_DIR} && git fetch origin master 2>&1 | tail -10")
        run(ssh, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && git log -3 --oneline")
        # 验证关键代码标记
        code, out, _ = run(
            ssh,
            f'cd {REMOTE_DIR} && grep -c "PRD-HEALTH-OPT-V1" '
            'backend/app/main.py backend/app/api/ai_call.py 2>&1 || true',
        )
        if "main.py:0" in out or "ai_call.py:0" in out:
            print("[FATAL] 服务器代码未包含 PRD-HEALTH-OPT-V1 修改")
            sys.exit(1)

        services = "backend admin-web h5-web"
        run(ssh, f"cd {REMOTE_DIR} && (docker compose stop {services} 2>&1 || docker-compose stop {services} 2>&1) | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && (docker compose rm -f {services} 2>&1 || docker-compose rm -f {services} 2>&1) | tail -5")
        rc, _, _ = run(
            ssh,
            f"cd {REMOTE_DIR} && (docker compose build --no-cache {services} 2>&1 || docker-compose build --no-cache {services} 2>&1) | tail -60",
            timeout=2400,
        )
        if rc != 0:
            print(f"[FATAL] build 失败 rc={rc}")
            sys.exit(1)
        run(ssh, f"cd {REMOTE_DIR} && (docker compose up -d {services} 2>&1 || docker-compose up -d {services} 2>&1) | tail -5")
        time.sleep(25)
        run(ssh, f"docker logs --tail 80 {PROJECT_ID}-backend 2>&1 | tail -100")
    finally:
        ssh.close()


def _req(method: str, path: str, **kwargs):
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", 30)
    return requests.request(method, url, verify=True, **kwargs)


def get_admin_token() -> str:
    try:
        r = _req("POST", "/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
        if r.status_code == 200:
            data = r.json()
            return data.get("access_token") or data.get("token") or ""
    except Exception as e:
        print(f"[WARN] admin login: {e}")
    return ""


def get_user_token() -> str:
    """尝试普通用户登录"""
    candidates = [
        {"phone": "13800000001", "password": "123456"},
        {"phone": "13800000000", "password": "admin123"},
    ]
    for body in candidates:
        try:
            r = _req("POST", "/api/auth/login", json=body)
            if r.status_code == 200:
                data = r.json()
                tok = data.get("access_token") or data.get("token")
                if tok:
                    return tok
        except Exception:
            pass
    return ""


def run_tests() -> int:
    results: List[Tuple[str, bool, str]] = []

    def add(name: str, passed: bool, note: str = ""):
        results.append((name, passed, note))
        flag = "✅" if passed else "❌"
        print(f"{flag} {name} {('—' + note) if note else ''}")

    # T1 backend health
    try:
        r = _req("GET", "/api/health")
        add("T1 /api/health 200", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        add("T1 /api/health 200", False, str(e))

    # T2 H5 健康档案页可达
    try:
        r = _req("GET", "/health-profile-v2/", allow_redirects=True)
        ok = r.status_code in (200, 308) or (200 <= r.status_code < 400)
        add("T2 /health-profile-v2 可达", ok, f"status={r.status_code}")
    except Exception as e:
        add("T2 /health-profile-v2 可达", False, str(e))

    # T3 H5 设备页可达
    try:
        r = _req("GET", "/devices/", allow_redirects=True)
        ok = r.status_code in (200, 308) or (200 <= r.status_code < 400)
        add("T3 /devices 可达", ok, f"status={r.status_code}")
    except Exception as e:
        add("T3 /devices 可达", False, str(e))

    # T4 用药计划 add 页可达（h5）
    try:
        r = _req("GET", "/health-plan/medications/add/", allow_redirects=True)
        ok = r.status_code in (200, 308) or (200 <= r.status_code < 400)
        add("T4 /health-plan/medications/add 可达", ok, f"status={r.status_code}")
    except Exception as e:
        add("T4 /health-plan/medications/add 可达", False, str(e))

    # T5 ai-call quota 401 未登录
    try:
        r = _req("GET", "/api/ai-call/quota")
        add("T5 /api/ai-call/quota 未登录 401", r.status_code == 401, f"status={r.status_code}")
    except Exception as e:
        add("T5 /api/ai-call/quota 未登录 401", False, str(e))

    user_tok = get_user_token()
    if user_tok:
        try:
            r = _req("GET", "/api/ai-call/quota", headers={"Authorization": f"Bearer {user_tok}"})
            ok = r.status_code == 200 and ("monthly_quota" in r.text)
            add("T6 /api/ai-call/quota 登录 200 + 字段完整", ok, f"status={r.status_code}, body={r.text[:120]}")
        except Exception as e:
            add("T6 /api/ai-call/quota 登录 200", False, str(e))
    else:
        add("T6 /api/ai-call/quota 登录 200", False, "未能登录用户（跳过）")

    # T7 admin api 401 未登录
    try:
        r = _req("GET", "/api/admin/ai-call/membership-levels")
        add("T7 admin/ai-call/membership-levels 未登录 401", r.status_code in (401, 403), f"status={r.status_code}")
    except Exception as e:
        add("T7 admin api 401", False, str(e))

    # T8 admin api 登录
    admin_tok = get_admin_token()
    if admin_tok:
        try:
            r = _req("GET", "/api/admin/ai-call/membership-levels", headers={"Authorization": f"Bearer {admin_tok}"})
            ok = r.status_code == 200
            data = r.json() if ok else []
            has_normal = any(d.get("level_code") == "normal" for d in data) if isinstance(data, list) else False
            has_health = any(d.get("level_code") == "health" for d in data) if isinstance(data, list) else False
            add("T8 admin levels 列表 normal+health", ok and has_normal and has_health,
                f"status={r.status_code}, count={len(data) if isinstance(data, list) else 'n/a'}")
        except Exception as e:
            add("T8 admin levels", False, str(e))

        try:
            r = _req("GET", "/api/admin/ai-call/config", headers={"Authorization": f"Bearer {admin_tok}"})
            ok = r.status_code == 200
            txt = r.text
            ok2 = ("default_dnd_start" in txt) and ("retry_max" in txt) and ("rule_a_per_plan_once" in txt)
            add("T9 admin config 字段完整", ok and ok2, f"status={r.status_code}, body={txt[:200]}")
        except Exception as e:
            add("T9 admin config", False, str(e))
    else:
        add("T8 admin levels", False, "admin token 未取得")
        add("T9 admin config", False, "admin token 未取得")

    # T10 启动迁移日志
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        _, out, _ = run(ssh, f"docker logs {PROJECT_ID}-backend 2>&1 | grep -E 'health_opt_v1' | tail -20")
        add("T10 [migrate] health_opt_v1 日志", "health_opt_v1" in out, "")
        ssh.close()
    except Exception as e:
        add("T10 启动日志", False, str(e))

    # T11 数据库表存在
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        cmd = (
            f"docker exec {PROJECT_ID}-db sh -lc "
            "'mysql -uroot -p${MYSQL_ROOT_PASSWORD} -N -e \""
            "SHOW TABLES LIKE \\\"ai_call_%\\\";\" bini_health 2>/dev/null || true'"
        )
        _, out, _ = run(ssh, cmd)
        ok = ("ai_call_membership_levels" in out and "ai_call_global_config" in out and "ai_call_logs" in out)
        add("T11 DB 表 ai_call_* 已创建", ok, out[:200])
        ssh.close()
    except Exception as e:
        add("T11 DB 表", False, str(e))

    # T12 medication_plans 新增列
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        cmd = (
            f"docker exec {PROJECT_ID}-db sh -lc "
            "'mysql -uroot -p${MYSQL_ROOT_PASSWORD} -N -e \""
            "SHOW COLUMNS FROM medication_plans LIKE \\\"ai_call_%\\\";\" bini_health 2>/dev/null || true'"
        )
        _, out, _ = run(ssh, cmd)
        ok = ("ai_call_enabled" in out and "ai_call_dnd_start" in out and "ai_call_target_user_id" in out)
        add("T12 medication_plans 加列 ai_call_*", ok, out[:200])
        ssh.close()
    except Exception as e:
        add("T12 medication_plans 加列", False, str(e))

    # T13 admin 页面可达
    try:
        r = _req("GET", "/ai-call-config/", allow_redirects=True)
        ok = r.status_code in (200, 308) or (200 <= r.status_code < 400)
        add("T13 admin /ai-call-config 可达", ok, f"status={r.status_code}")
    except Exception as e:
        add("T13 admin /ai-call-config", False, str(e))

    # T14 h5 容器构建产物含 BH_TOKENS
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        _, out, _ = run(
            ssh,
            f"docker exec {PROJECT_ID}-h5-web sh -lc "
            "'grep -r \"BH_TOKENS\\|health-tokens\\|bh-top-device-entry\" /app/.next/ 2>/dev/null "
            "| head -3 | wc -l' || true",
        )
        cnt = 0
        try:
            cnt = int((out or "0").strip().split()[-1])
        except Exception:
            pass
        add("T14 h5 .next 构建含 health-tokens/设备入口", cnt >= 1, f"hits={cnt}")
        ssh.close()
    except Exception as e:
        add("T14 h5 构建产物", False, str(e))

    # 汇总
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    print(f"\n=========\n汇总：{passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    deploy()
    rc = run_tests()
    sys.exit(rc)
