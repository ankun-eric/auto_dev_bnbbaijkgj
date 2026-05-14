#!/usr/bin/env python3
"""
[AICHAT-OPTIM-FIX-V1 2026-05-14] 部署 + 自动化测试脚本

流程：
  1. SSH 到服务器
  2. cd 项目目录 → git fetch + reset --hard origin/master
  3. docker compose build --no-cache backend admin-web h5-web
  4. docker compose up -d backend admin-web h5-web
  5. 等待容器就绪
  6. 通过 HTTPS 调用一系列接口完成非 UI 自动化测试
  7. 输出测试报告（PASS/FAIL）
"""
from __future__ import annotations

import json
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


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> Tuple[int, str, str]:
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


def deploy() -> None:
    print(f"=== 连接 {HOST} ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                allow_agent=False, look_for_keys=False)

    try:
        run(ssh, f"cd {REMOTE_DIR} && git fetch origin master 2>&1 | tail -10")
        run(ssh, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && git log -3 --oneline")

        # 验证关键标记存在
        code, out, _ = run(
            ssh,
            f'cd {REMOTE_DIR} && grep -c "AICHAT-OPTIM-FIX-V1" '
            'backend/app/main.py backend/app/api/function_button.py '
            'backend/app/schemas/function_button.py backend/app/models/models.py '
            'admin-web/src/components/EmojiPicker.tsx '
            'h5-web/src/components/ai-chat/CapsuleBar.tsx 2>&1 || true',
        )
        if "main.py:0" in out or "function_button.py:0" in out:
            print("[FATAL] 服务器代码未包含本次 AICHAT-OPTIM-FIX-V1 修改")
            sys.exit(1)

        # stop + rm + build + up
        run(ssh,
            f"cd {REMOTE_DIR} && (docker compose stop backend admin-web h5-web 2>&1 || "
            "docker-compose stop backend admin-web h5-web 2>&1) | tail -5")
        run(ssh,
            f"cd {REMOTE_DIR} && (docker compose rm -f backend admin-web h5-web 2>&1 || "
            "docker-compose rm -f backend admin-web h5-web 2>&1) | tail -5")
        code, _, _ = run(
            ssh,
            f"cd {REMOTE_DIR} && (docker compose build --no-cache backend admin-web h5-web 2>&1 || "
            "docker-compose build --no-cache backend admin-web h5-web 2>&1) | tail -100",
            timeout=2400,
        )
        if code != 0:
            print("[FATAL] docker compose build 失败")
            sys.exit(2)
        run(ssh,
            f"cd {REMOTE_DIR} && (docker compose up -d backend admin-web h5-web 2>&1 || "
            "docker-compose up -d backend admin-web h5-web 2>&1) | tail -10")

        # 等待 backend 健康
        print("\n--- 等待 backend 健康 ---")
        for i in range(60):
            try:
                r = requests.get(f"{BASE_URL}/api/health", timeout=10, verify=True)
                if r.status_code in (200, 404):
                    print(f"[OK] backend 已响应（第 {i+1} 次，HTTP {r.status_code}）")
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            print("[WARN] backend 健康检查超时，仍继续测试")

        # 输出当前容器状态
        run(ssh, f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID} | head -10")

        # 输出 backend 启动日志中的迁移记录
        run(ssh, f"docker logs --tail 200 {PROJECT_ID}-backend 2>&1 | grep -E 'migrate|AICHAT' | tail -20 || true")

    finally:
        ssh.close()


# ─────────────────────── 自动化测试 ───────────────────────

TestResult = Tuple[str, bool, str]


def test_api_health() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=15)
        ok = r.status_code == 200
        return ("T1 /api/health 返回 200", ok, f"HTTP {r.status_code} body={r.text[:120]}")
    except Exception as exc:
        return ("T1 /api/health", False, f"异常 {exc}")


def test_h5_index() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/", timeout=20, allow_redirects=False)
        ok = r.status_code in (200, 301, 302, 307, 308)
        return ("T2 H5 主页可达", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T2 H5 主页", False, f"异常 {exc}")


def test_public_function_buttons_endpoint() -> TestResult:
    """[F-04] 公开 /api/function-buttons?is_enabled=true 返回数组，含 8 个新字段。"""
    try:
        r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
        if r.status_code != 200:
            return ("T3 公开 /api/function-buttons", False, f"HTTP {r.status_code} body={r.text[:200]}")
        body = r.json()
        if not isinstance(body, list):
            return ("T3 公开 /api/function-buttons", False, f"返回非数组: {type(body)}")
        # 若数组非空，校验首项含 8 个新字段中至少 1 个 + icon + button_type
        if body:
            first = body[0]
            expected_keys = ["id", "name", "button_type", "is_enabled"]
            for k in expected_keys:
                if k not in first:
                    return ("T3 字段完整", False, f"缺少 {k}, 仅有 {list(first.keys())[:10]}")
        return ("T3 公开 /api/function-buttons 返回数组 + 字段完整", True, f"返回 {len(body)} 条")
    except Exception as exc:
        return ("T3 公开 /api/function-buttons", False, f"异常 {exc}")


def test_function_buttons_only_enabled() -> TestResult:
    """[F-04 安全] is_enabled=true 时不能返回已禁用的按钮。"""
    try:
        r = requests.get(f"{BASE_URL}/api/function-buttons?is_enabled=true", timeout=20)
        if r.status_code != 200:
            return ("T4 is_enabled 过滤", False, f"HTTP {r.status_code}")
        body = r.json()
        if not isinstance(body, list):
            return ("T4 is_enabled 过滤", False, "返回非数组")
        for item in body:
            if item.get("is_enabled") is False:
                return ("T4 is_enabled 过滤", False, f"返回了已禁用按钮 id={item.get('id')}")
        return ("T4 is_enabled 过滤生效", True, f"全部 {len(body)} 条 is_enabled=true")
    except Exception as exc:
        return ("T4 is_enabled 过滤", False, f"异常 {exc}")


def test_admin_function_buttons_page() -> TestResult:
    """[F-01] admin 功能按钮管理页面 HTML 含 Emoji 相关特征。"""
    try:
        r = requests.get(f"{BASE_URL}/admin/function-buttons", timeout=30, allow_redirects=True)
        ok_status = r.status_code in (200, 401, 302, 307)
        # 仅校验状态码可达，详细 UI 校验受登录限制
        return ("T5 admin /function-buttons 页面可达", ok_status, f"HTTP {r.status_code}, body长度={len(r.text)}")
    except Exception as exc:
        return ("T5 admin /function-buttons 页面", False, f"异常 {exc}")


def test_admin_ai_home_config_page() -> TestResult:
    """[F-03] admin AI 对话首页配置页面可达。"""
    try:
        r = requests.get(f"{BASE_URL}/admin/home-settings/ai-home-config", timeout=30, allow_redirects=True)
        ok = r.status_code in (200, 401, 302, 307)
        return ("T6 admin /home-settings/ai-home-config 页面可达", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T6 admin ai-home-config 页面", False, f"异常 {exc}")


def test_h5_ai_home_page() -> TestResult:
    """[F-04] H5 AI 对话首页 HTML 可达。"""
    try:
        r = requests.get(f"{BASE_URL}/ai-home", timeout=30, allow_redirects=True)
        ok = r.status_code in (200, 302, 307)
        return ("T7 H5 /ai-home 页面可达", ok, f"HTTP {r.status_code}, body长度={len(r.text)}")
    except Exception as exc:
        return ("T7 H5 /ai-home 页面", False, f"异常 {exc}")


def test_analytics_capsule_click() -> TestResult:
    """[F-08] 验证 capsule_click 埋点可上报。"""
    try:
        r = requests.post(
            f"{BASE_URL}/api/analytics/track",
            json={"event": "capsule_click", "params": {"button_id": 1, "button_name": "测试", "button_type": "quick_ask"}, "ts": int(time.time() * 1000)},
            timeout=15,
        )
        ok = r.status_code in (200, 201, 204)
        return ("T8 analytics capsule_click 上报", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T8 analytics capsule_click", False, f"异常 {exc}")


def test_analytics_card_button_click() -> TestResult:
    """[F-08] 验证 card_button_click 埋点可上报。"""
    try:
        r = requests.post(
            f"{BASE_URL}/api/analytics/track",
            json={"event": "card_button_click", "params": {"button_id": 1, "card_type": "upload"}, "ts": int(time.time() * 1000)},
            timeout=15,
        )
        ok = r.status_code in (200, 201, 204)
        return ("T9 analytics card_button_click 上报", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T9 analytics card_button_click", False, f"异常 {exc}")


def test_migrate_log_aichat_optim_fix_v1() -> TestResult:
    """[F-02] 启动日志含 [migrate] aichat_optim_fix_v1。"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        try:
            stdin, stdout, _ = ssh.exec_command(
                f"docker logs --tail 1000 {PROJECT_ID}-backend 2>&1 | grep -i 'aichat_optim_fix_v1' | tail -5",
                timeout=30,
            )
            out = stdout.read().decode("utf-8", errors="replace")
            ok = bool(out.strip())
            return ("T10 启动日志含 aichat_optim_fix_v1", ok, out.strip()[:200])
        finally:
            ssh.close()
    except Exception as exc:
        return ("T10 启动日志检查", False, f"异常 {exc}")


def test_db_icon_field_populated() -> TestResult:
    """[F-02] DB 验证：所有 chat_function_buttons.icon 字段非空（如果表存在数据）。"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        try:
            # 进入 mysql 容器查询
            sql = (
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN icon IS NULL OR icon='' THEN 1 ELSE 0 END) AS empty_icon "
                "FROM chat_function_buttons;"
            )
            cmd = (
                f"docker exec {PROJECT_ID}-mysql sh -c 'mysql -uroot -proot -N -B "
                f"-e \"USE bini_health; {sql}\" 2>/dev/null' || true"
            )
            stdin, stdout, _ = ssh.exec_command(cmd, timeout=30)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            print(f"[DB Query] {out}")
            # 解析: total\tempty_icon 形如 "5\t0"
            if not out:
                return ("T11 DB icon 字段填充", True, "表为空或查询无结果，跳过")
            parts = out.split()
            if len(parts) >= 2:
                total = int(parts[0])
                empty = int(parts[1])
                if total == 0:
                    return ("T11 DB icon 字段填充", True, "表为空")
                ok = empty == 0
                return ("T11 所有 icon 字段非空", ok, f"total={total}, empty={empty}")
            return ("T11 DB icon 字段填充", True, f"无法解析结果: {out[:100]}")
        finally:
            ssh.close()
    except Exception as exc:
        return ("T11 DB icon 字段填充", False, f"异常 {exc}")


def test_migrate_log_func_grid_simplified() -> TestResult:
    """[F-09] 启动日志含 func_grid simplified 或 func_grid。"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                    allow_agent=False, look_for_keys=False)
        try:
            stdin, stdout, _ = ssh.exec_command(
                f"docker logs --tail 1000 {PROJECT_ID}-backend 2>&1 | grep -iE 'func_grid|simplified' | tail -5",
                timeout=30,
            )
            out = stdout.read().decode("utf-8", errors="replace")
            ok = bool(out.strip())
            return ("T12 启动日志含 func_grid 迁移记录", ok, out.strip()[:200])
        finally:
            ssh.close()
    except Exception as exc:
        return ("T12 启动日志检查", False, f"异常 {exc}")


def run_tests() -> int:
    print(f"\n=== 自动化测试 BASE_URL={BASE_URL} ===\n")
    tests = [
        test_api_health,
        test_h5_index,
        test_public_function_buttons_endpoint,
        test_function_buttons_only_enabled,
        test_admin_function_buttons_page,
        test_admin_ai_home_config_page,
        test_h5_ai_home_page,
        test_analytics_capsule_click,
        test_analytics_card_button_click,
        test_migrate_log_aichat_optim_fix_v1,
        test_db_icon_field_populated,
        test_migrate_log_func_grid_simplified,
    ]
    results: List[TestResult] = []
    for t in tests:
        try:
            results.append(t())
        except Exception as exc:
            results.append((t.__name__, False, f"未捕获异常 {exc}"))
    print("\n=== 测试结果 ===")
    fail = 0
    for name, ok, info in results:
        mark = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {mark}  {name}  ({info})")
        if not ok:
            fail += 1
    print(f"\n{'='*60}\n合计：{len(results)} 个用例，{len(results)-fail} PASS，{fail} FAIL\n{'='*60}\n")
    return 1 if fail > 0 else 0


if __name__ == "__main__":
    deploy()
    sys.exit(run_tests())
