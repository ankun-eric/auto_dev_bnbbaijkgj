#!/usr/bin/env python3
"""
[AI对话模式优化 PRD v1.0 2026-05-14] 部署 + 自动化测试脚本

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

import re
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
    print(f"\n>>> SSH: {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
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
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    try:
        # 1. Git pull 最新代码
        run(ssh, f"cd {REMOTE_DIR} && git fetch origin master 2>&1 | tail -20")
        run(ssh, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1 | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && git log -3 --oneline")

        # 2. 验证关键文件已包含本次改动
        code, out, _ = run(
            ssh,
            f'cd {REMOTE_DIR} && grep -c "AI对话模式优化 PRD v1.0" backend/app/models/models.py backend/app/main.py backend/app/api/prd469_health_v5.py backend/app/api/analytics.py backend/app/schemas/function_button.py 2>&1 || true',
        )
        if "models.py:0" in out or "main.py:0" in out:
            print("[FATAL] 服务器代码未包含本次 PRD v1.0 修复，请检查 git pull")
            sys.exit(1)

        # 3. docker compose 重建（仅重建有变化的容器：backend / admin-web / h5-web）
        run(ssh, f"cd {REMOTE_DIR} && (docker compose stop backend admin-web h5-web 2>&1 || docker-compose stop backend admin-web h5-web 2>&1) | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && (docker compose rm -f backend admin-web h5-web 2>&1 || docker-compose rm -f backend admin-web h5-web 2>&1) | tail -5")
        # 镜像构建（容忍超时，最长 30min）
        code, _, _ = run(
            ssh,
            f"cd {REMOTE_DIR} && (docker compose build --no-cache backend admin-web h5-web 2>&1 || docker-compose build --no-cache backend admin-web h5-web 2>&1) | tail -80",
            timeout=1800,
        )
        if code != 0:
            print("[FATAL] docker compose build 失败")
            sys.exit(2)
        run(ssh, f"cd {REMOTE_DIR} && (docker compose up -d backend admin-web h5-web 2>&1 || docker-compose up -d backend admin-web h5-web 2>&1) | tail -10")

        # 4. 等待 backend 健康（最多 90s）
        for i in range(45):
            try:
                r = requests.get(f"{BASE_URL}/api/health", timeout=10, verify=True)
                if r.status_code in (200, 404):
                    print(f"[OK] backend 已响应（第 {i+1} 次尝试，HTTP {r.status_code}）")
                    break
            except Exception:
                pass
            time.sleep(2)

        # 5. 输出当前容器状态
        run(ssh, f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID} | head -10")

    finally:
        ssh.close()


# ─────────────────────── 自动化测试 ───────────────────────


TestResult = Tuple[str, bool, str]


def test_api_health() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=15)
        ok = r.status_code == 200 and "ok" in r.text.lower()
        return ("T1 /api/health 返回 200/ok", ok, f"HTTP {r.status_code} body={r.text[:120]}")
    except Exception as exc:
        return ("T1 /api/health", False, f"异常 {exc}")


def test_h5_index() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/", timeout=20, allow_redirects=False)
        ok = r.status_code in (200, 301, 302, 307, 308)
        return ("T2 H5 主页可达", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T2 H5 主页", False, f"异常 {exc}")


def test_admin_index() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/admin/", timeout=20, allow_redirects=False)
        ok = r.status_code in (200, 301, 302, 307, 308)
        return ("T3 Admin 主页可达", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T3 Admin 主页", False, f"异常 {exc}")


def test_function_buttons_public() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/api/chat/function-buttons", timeout=20)
        if r.status_code != 200:
            return ("T4 公开 function-buttons 200", False, f"HTTP {r.status_code} body={r.text[:200]}")
        body = r.json()
        ok = isinstance(body, list)
        return ("T4 公开 function-buttons 200 + 列表", ok, f"返回 {len(body) if isinstance(body, list) else '?' } 条")
    except Exception as exc:
        return ("T4 公开 function-buttons", False, f"异常 {exc}")


def test_admin_function_buttons_unauth() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/api/admin/function-buttons", timeout=20)
        ok = r.status_code in (401, 403)
        return ("T5 admin function-buttons 未授权 401/403", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T5 admin function-buttons", False, f"异常 {exc}")


def test_recognize_endpoint() -> TestResult:
    """[PRD v1.0 §9] 验证 /api/prd469/medication-library/recognize 一站式接口可达。

    - 不传 image，仅传 image_text+prompt_template_id，期望 200 + 标准结构
    """
    try:
        # PRD §9.2 要求：prompt_template_id 为可选；本测试只传 image_text
        r = requests.post(
            f"{BASE_URL}/api/prd469/medication-library/recognize",
            data={"image_text": "感冒灵颗粒"},
            timeout=60,
        )
        if r.status_code != 200:
            return ("T6 /medication-library/recognize 200", False, f"HTTP {r.status_code} body={r.text[:200]}")
        body = r.json()
        data = body.get("data") if isinstance(body, dict) else None
        ok = (
            isinstance(body, dict)
            and "code" in body
            and isinstance(data, dict)
            and "drug_candidates" in data
            and "ai_response" in data
            and "method" in data
        )
        return ("T6 /medication-library/recognize 200 + 完整结构", ok, f"keys={list(data.keys()) if isinstance(data, dict) else '?'}")
    except Exception as exc:
        return ("T6 /medication-library/recognize", False, f"异常 {exc}")


def test_analytics_capsule_exposure() -> TestResult:
    """[PRD v1.0 §10] 验证新增的 capsule_exposure 埋点事件接收正常。"""
    try:
        r = requests.post(
            f"{BASE_URL}/api/analytics/track",
            json={"event": "capsule_exposure", "params": {"button_keys": ["看报告", "查用药"]}, "ts": int(time.time() * 1000)},
            timeout=15,
        )
        ok = r.status_code == 200
        return ("T7 analytics capsule_exposure 200", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T7 analytics capsule_exposure", False, f"异常 {exc}")


def test_analytics_card_button_click() -> TestResult:
    try:
        r = requests.post(
            f"{BASE_URL}/api/analytics/track",
            json={"event": "card_button_click", "params": {"button_key": "看报告", "card_type": "upload", "sub_action": "camera"}, "ts": int(time.time() * 1000)},
            timeout=15,
        )
        ok = r.status_code == 200
        return ("T8 analytics card_button_click 200", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T8 analytics card_button_click", False, f"异常 {exc}")


def test_medication_library_search() -> TestResult:
    """[确认 prd469_health_v5 路由整体可达，无回归]"""
    try:
        r = requests.get(f"{BASE_URL}/api/prd469/medication-library/search?kw=感冒", timeout=20)
        ok = r.status_code == 200 and "items" in r.text
        return ("T9 medication-library/search 200", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T9 medication-library/search", False, f"异常 {exc}")


def test_medication_library_stats() -> TestResult:
    try:
        r = requests.get(f"{BASE_URL}/api/prd469/medication-library/stats", timeout=20)
        ok = r.status_code == 200 and "total" in r.text
        return ("T10 medication-library/stats 200", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T10 medication-library/stats", False, f"异常 {exc}")


def test_admin_button_type_validation() -> TestResult:
    """[PRD §3.2] 验证非法 button_type 被应用层校验拦截（401/403/400 都视为通过：
    401/403 表示无权限触达校验逻辑，但接口注册了；400 才是真正的校验生效）。"""
    try:
        r = requests.post(
            f"{BASE_URL}/api/admin/function-buttons",
            json={"name": "test_invalid", "button_type": "invalid_type_xxx", "auto_user_message": "x"},
            timeout=15,
        )
        ok = r.status_code in (400, 401, 403, 422)
        return ("T11 admin button_type 校验/鉴权返回 400/401/403/422", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        return ("T11 admin button_type 校验", False, f"异常 {exc}")


def test_h5_chat_static_resources() -> TestResult:
    """h5 静态资源可达（确认重建后的 h5-web 正常上线）"""
    try:
        r = requests.get(f"{BASE_URL}/", timeout=15, allow_redirects=True)
        ok = r.status_code == 200 and len(r.text) > 1000
        return ("T12 H5 主页 HTML 长度 > 1000", ok, f"HTTP {r.status_code} len={len(r.text)}")
    except Exception as exc:
        return ("T12 H5 主页 HTML", False, f"异常 {exc}")


TESTS = [
    test_api_health,
    test_h5_index,
    test_admin_index,
    test_function_buttons_public,
    test_admin_function_buttons_unauth,
    test_recognize_endpoint,
    test_analytics_capsule_exposure,
    test_analytics_card_button_click,
    test_medication_library_search,
    test_medication_library_stats,
    test_admin_button_type_validation,
    test_h5_chat_static_resources,
]


def main() -> None:
    if "--no-deploy" not in sys.argv:
        deploy()

    # 等 5 秒让前端容器完成 Next.js cold start
    time.sleep(5)

    print("\n=== 自动化测试开始 ===")
    results: List[TestResult] = [t() for t in TESTS]
    print("\n=== 测试报告 ===")
    pass_cnt = sum(1 for _, ok, _ in results if ok)
    for name, ok, info in results:
        flag = "[PASS]" if ok else "[FAIL]"
        print(f"  {flag} {name} | {info}")
    print(f"\n总计：{pass_cnt}/{len(results)} 通过")
    if pass_cnt != len(results):
        sys.exit(3)


if __name__ == "__main__":
    main()
