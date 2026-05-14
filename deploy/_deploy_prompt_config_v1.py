#!/usr/bin/env python3
"""[PRD-PROMPT-CONFIG-V1 2026-05-14] 部署 + 自动化测试

流程：
  1. SSH 到服务器
  2. git fetch + reset --hard origin/master
  3. docker compose build --no-cache backend admin-web
  4. docker compose up -d backend admin-web
  5. 等待容器就绪
  6. 执行 13 项服务器自动化测试
  7. 输出 PASS/FAIL 报告
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


def run(ssh, cmd: str, timeout: int = 900) -> Tuple[int, str, str]:
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
            f'cd {REMOTE_DIR} && grep -c "PRD-PROMPT-CONFIG-V1" '
            'backend/app/main.py backend/app/api/prompt_templates.py '
            'backend/app/schemas/function_button.py 2>&1 || true',
        )
        if "main.py:0" in out:
            print("[FATAL] 服务器代码未包含 PRD-PROMPT-CONFIG-V1 修改")
            sys.exit(1)

        # 构建 backend + admin-web（h5/小程序/flutter不重构）
        run(ssh, f"cd {REMOTE_DIR} && (docker compose stop backend admin-web 2>&1 || docker-compose stop backend admin-web 2>&1) | tail -5")
        run(ssh, f"cd {REMOTE_DIR} && (docker compose rm -f backend admin-web 2>&1 || docker-compose rm -f backend admin-web 2>&1) | tail -5")
        rc, _, _ = run(
            ssh,
            f"cd {REMOTE_DIR} && (docker compose build --no-cache backend admin-web 2>&1 || docker-compose build --no-cache backend admin-web 2>&1) | tail -40",
            timeout=1800,
        )
        if rc != 0:
            print(f"[FATAL] build 失败 rc={rc}")
            sys.exit(1)
        run(ssh, f"cd {REMOTE_DIR} && (docker compose up -d backend admin-web 2>&1 || docker-compose up -d backend admin-web 2>&1) | tail -5")
        # 等待
        time.sleep(20)
        run(ssh, f"docker logs --tail 80 {PROJECT_ID}-backend 2>&1 | tail -80")
    finally:
        ssh.close()


def _req(method: str, path: str, **kwargs):
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", 30)
    return requests.request(method, url, verify=True, **kwargs)


def get_admin_token() -> str:
    """获取管理员 token（默认 admin 账号 phone=13800000000 password=admin123）"""
    try:
        # 项目使用 phone + password 登录
        r = _req("POST", "/api/auth/login", json={"phone": "13800000000", "password": "admin123"})
        if r.status_code == 200:
            data = r.json()
            return data.get("access_token") or data.get("token") or ""
        else:
            print(f"[admin login non-200] status={r.status_code} body={r.text[:300]}")
    except Exception as e:
        print(f"[admin login error] {e}")
    return ""


def run_tests():
    print("\n=== 服务器自动化测试 ===")
    passed = []
    failed = []

    def assert_test(name: str, ok: bool, detail: str = ""):
        if ok:
            passed.append(name)
            print(f"  ✅ {name}")
        else:
            failed.append((name, detail))
            print(f"  ❌ {name} | {detail[:300]}")

    # T1: backend 健康
    try:
        r = _req("GET", "/api/health")
        assert_test("T1 backend /api/health 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        assert_test("T1 backend /api/health 200", False, str(e))

    # T2: admin 主页可达
    try:
        r = _req("GET", "/")
        assert_test("T2 admin / 主页可达", r.status_code in (200, 301, 302, 308), f"status={r.status_code}")
    except Exception as e:
        assert_test("T2 admin / 主页可达", False, str(e))

    # T3: 公开函数按钮列表（不应 500）
    try:
        r = _req("GET", "/api/function-buttons?is_enabled=true")
        assert_test("T3 公开 /api/function-buttons 返回数组", r.status_code == 200 and isinstance(r.json(), list), f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        assert_test("T3 公开 /api/function-buttons", False, str(e))

    # admin 接口需要 admin 用户身份，但项目登录流程要求 user/merchant 身份，
    # admin 账号默认无法通过 /api/auth/login 拿 token。
    # 因此对 admin 接口的功能验证改为：直接在 backend 容器内用 Python 调用底层逻辑
    # （SSH + docker exec backend python -c）；以及 SSH 查询 DB 验证迁移结果。

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
                allow_agent=False, look_for_keys=False)
    try:
        # T4: 启动日志含迁移标记
        rc, out, _ = run(ssh, f'docker logs {PROJECT_ID}-backend 2>&1 | grep -E "prompt_type_config_v1" | head -20')
        has_log = "prompt_type_config_v1" in out
        assert_test("T4 backend 启动日志含 [migrate] prompt_type_config_v1", has_log, f"out={out[:300]}")

        # 注：通过外层 bash 双引号 + 内层单引号传 SQL 时，外层 PowerShell→SSH 通道
        # 已经会吞掉一层引号；改为 sh -c \"...\" 内嵌 mysql -e '...' 直接传整段命令更稳定。

        def run_sql(sql: str):
            # 用 heredoc 风格避免引号嵌套
            cmd = (
                f"docker exec {PROJECT_ID}-db sh -c "
                f"'mysql -uroot -p\"$MYSQL_ROOT_PASSWORD\" bini_health -N -B -e \"{sql}\"' 2>&1"
            )
            return run(ssh, cmd)

        def parse_int(out: str) -> int:
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line)
            return -1

        # T5: DB 中 prompt_type_config 表有 10 条
        rc, out, _ = run_sql("SELECT COUNT(*) FROM prompt_type_config;")
        cnt = parse_int(out)
        assert_test("T5 prompt_type_config 表 >=10 条数据", cnt >= 10, f"count={cnt} out={out[:200]}")

        # T6: 报告解读组在线 2 条
        rc, out, _ = run_sql(
            "SELECT COUNT(*) FROM prompt_type_config WHERE business_group=\\\"report_interpret\\\" AND is_online=1;"
        )
        cnt = parse_int(out)
        assert_test("T6 report_interpret 业务分组下有 2 条在线类型", cnt == 2, f"count={cnt} out={out[:200]}")

        # T7: _deprecated 组 2 条
        rc, out, _ = run_sql(
            "SELECT COUNT(*) FROM prompt_type_config WHERE business_group=\\\"_deprecated\\\";"
        )
        cnt = parse_int(out)
        assert_test("T7 _deprecated 组下有 2 条已下线类型", cnt == 2, f"count={cnt} out={out[:200]}")

        # T8: 备份表 function_buttons_backup_pcv1 已创建
        rc, out, _ = run_sql(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=\\\"function_buttons_backup_pcv1\\\";"
        )
        cnt = parse_int(out)
        assert_test("T8 function_buttons_backup_pcv1 备份表已创建", cnt == 1, f"count={cnt} out={out[:200]}")

        # T9: backend 容器内 ALLOWED_BUTTON_TYPES 含 report_interpret
        rc, out, _ = run(ssh,
            f"docker exec {PROJECT_ID}-backend python -c "
            f"\"from app.schemas.function_button import ALLOWED_BUTTON_TYPES; "
            f"print('REPORT_OK' if 'report_interpret' in ALLOWED_BUTTON_TYPES else 'REPORT_FAIL'); "
            f"print(sorted(ALLOWED_BUTTON_TYPES))\" 2>&1",
        )
        assert_test("T9 ALLOWED_BUTTON_TYPES 含 report_interpret", "REPORT_OK" in out, f"out={out[:300]}")

        # T10/T11：把 python 脚本写到 backend 容器的 /tmp 内再执行（避免 -c 单行 async 语法问题）
        py_t10 = (
            "import asyncio\n"
            "from app.core.database import async_session\n"
            "from app.api.prompt_templates import _load_type_configs\n"
            "async def m():\n"
            "    async with async_session() as db:\n"
            "        cfgs = await _load_type_configs(db, include_offline=False)\n"
            "        print('TYPES=' + ','.join(c.type_key for c in cfgs))\n"
            "        print('GROUPS=' + ','.join(sorted(set(c.business_group for c in cfgs))))\n"
            "asyncio.run(m())\n"
        )
        # 写入容器
        run(ssh, f"docker exec {PROJECT_ID}-backend bash -c 'cat > /tmp/_t10.py' <<'PYEOF'\n{py_t10}\nPYEOF\n")
        # 改用 SSH 一次发送：用 base64 安全注入
        import base64
        b64 = base64.b64encode(py_t10.encode("utf-8")).decode("ascii")
        rc, out, _ = run(ssh,
            f"docker exec -w /app -e PYTHONPATH=/app {PROJECT_ID}-backend bash -c "
            f"\"echo {b64} | base64 -d > /tmp/_t10.py && python /tmp/_t10.py\" 2>&1 | tail -20",
        )
        has_offline_hidden = ("trend_analysis" not in out) and ("checkup_report," not in out)
        has_report_interpret = "checkup_report_interpret" in out
        has_group_field = "GROUPS=" in out and "report_interpret" in out
        assert_test(
            "T10 _load_type_configs 不含已下线类型 + 含 report_interpret + 含 business_group",
            has_offline_hidden and has_report_interpret and has_group_field,
            f"out={out[:500]}",
        )

        py_t11 = (
            "import asyncio,json\n"
            "from app.core.database import async_session\n"
            "from app.api.prompt_templates import list_prompt_templates\n"
            "async def m():\n"
            "    async with async_session() as db:\n"
            "        class U: pass\n"
            "        res = await list_prompt_templates(0, db, U())\n"
            "        if res:\n"
            "            d = res[0].model_dump() if hasattr(res[0],'model_dump') else dict(res[0])\n"
            "            print('FIELDS=' + ','.join(sorted(d.keys())))\n"
            "            print('FIRST_GROUP=' + str(d.get('business_group')))\n"
            "            print('FIRST_ABT=' + str(d.get('allowed_button_types')))\n"
            "        else:\n"
            "            print('EMPTY_LIST')\n"
            "asyncio.run(m())\n"
        )
        b64 = base64.b64encode(py_t11.encode("utf-8")).decode("ascii")
        rc, out, _ = run(ssh,
            f"docker exec -w /app -e PYTHONPATH=/app {PROJECT_ID}-backend bash -c "
            f"\"echo {b64} | base64 -d > /tmp/_t11.py && python /tmp/_t11.py\" 2>&1 | tail -20",
        )
        has_bg_field = "business_group" in out and "allowed_button_types" in out
        assert_test(
            "T11 GroupResponse 包含 business_group + allowed_button_types 字段",
            has_bg_field,
            f"out={out[:500]}",
        )

        # T12: /api/report-interpret/start 路由已注册（未登录返回 401/403/422）
        try:
            r = _req("POST", "/api/report-interpret/start", json={"button_id": 1, "image_urls": ["x"]})
            ok = r.status_code in (401, 403, 422)
            assert_test(
                "T12 /api/report-interpret/start 路由已注册",
                ok,
                f"status={r.status_code} body={r.text[:200]}",
            )
        except Exception as e:
            assert_test("T12 /api/report-interpret/start", False, str(e))

        # T13: /api/admin/prompt-type-config 路由注册（无 token 应 401，不是 404）
        try:
            r = _req("GET", "/api/admin/prompt-type-config")
            ok = r.status_code in (401, 403)
            assert_test(
                "T13 /api/admin/prompt-type-config 路由已注册",
                ok,
                f"status={r.status_code} body={r.text[:200]}",
            )
        except Exception as e:
            assert_test("T13 /api/admin/prompt-type-config", False, str(e))

        # T14: admin-web function-buttons 页面源码含修复代码
        rc, out, _ = run(ssh,
            f'grep -c "PRD-PROMPT-CONFIG-V1\\|filteredPromptOptions\\|去 Prompt 配置中心" '
            f'{REMOTE_DIR}/admin-web/src/app/\\(admin\\)/function-buttons/page.tsx 2>&1 || true',
        )
        # 容器内构建产物可能不易直接查；用源码文件代之
        cnt = 0
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                cnt = int(line)
                break
        assert_test(
            "T14 admin-web function-buttons 源码含 Bug 修复标记 (>=3)",
            cnt >= 3,
            f"count={cnt} out={out[:300]}",
        )

        # T15: admin-web prompt-templates 业务分组 Tab 代码已就位
        rc, out, _ = run(ssh,
            f'grep -c "BUSINESS_GROUP_LABELS\\|prompt-business-group-tabs\\|prompt-type-list" '
            f'{REMOTE_DIR}/admin-web/src/app/\\(admin\\)/prompt-templates/page.tsx 2>&1 || true',
        )
        cnt = 0
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                cnt = int(line)
                break
        assert_test(
            "T15 admin-web prompt-templates 业务分组 Tab 代码已就位 (>=2)",
            cnt >= 2,
            f"count={cnt} out={out[:300]}",
        )
    finally:
        ssh.close()

    return passed, failed


def main():
    import os
    if not os.environ.get("SKIP_DEPLOY"):
        deploy()
    passed, failed = run_tests()
    print("\n" + "=" * 60)
    print(f"测试总结：通过 {len(passed)} / 失败 {len(failed)}")
    if failed:
        print("\n失败用例：")
        for n, d in failed:
            print(f"  - {n}\n    {d[:300]}")
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
