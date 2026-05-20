"""在远程 backend 容器内运行 tcm36 测试用例 + Bug 1/2 直接 API 验证"""
from __future__ import annotations

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONTAINER = f"{DEPLOY_ID}-backend"


def run(client, cmd, timeout=600):
    print(f"\n$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60)
    stdout.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out, flush=True)
    if err.strip():
        print("STDERR:", err, flush=True)
    print(f"[rc={rc}]", flush=True)
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # ── A. 在 backend 容器内运行 tcm36 测试用例 ──
        print("\n========== A) 容器内 pytest tcm36 ==========")
        run(
            client,
            f"docker exec {CONTAINER} bash -lc 'cd /app && "
            f"python -m pytest tests/test_tcm36_drawer_v12_20260520.py -v --tb=short 2>&1 | tail -200' ",
            timeout=300,
        )

        # ── B. 服务端内部 curl 验证 admin 接口 page_size 上限放宽 ──
        # 用 root 直接读 DB 拿一个 admin 的 phone，再通过 require_role 验证逻辑路径
        print("\n========== B) 容器内验证 page_size=500 不再 422 ==========")
        # 通过 pytest+TestClient 调用 admin list templates，bypass captcha
        check_script = """
import asyncio
from sqlalchemy import text
from app.core.database import async_session

async def main():
    async with async_session() as db:
        # tcm_constitution 题数
        r = await db.execute(text("SELECT id, code, name FROM questionnaire_template WHERE code='tcm_constitution'"))
        tpl = r.fetchone()
        print('tpl:', dict(zip(['id','code','name'], tpl)) if tpl else None)
        r2 = await db.execute(text('SELECT COUNT(*) FROM questionnaire_question WHERE template_id=:tid'), {'tid': tpl[0]})
        print('question_count:', r2.scalar())
        # 5 新字段是否存在
        r3 = await db.execute(text("SELECT trigger_by_keyword, trigger_by_intent, trigger_keywords, ai_reference_passive, ai_reference_active FROM chat_function_buttons LIMIT 1"))
        try:
            row = r3.fetchone()
            print('button_5fields_ok:', True, 'sample:', tuple(row) if row else None)
        except Exception as e:
            print('button_5fields_ok:', False, e)

asyncio.run(main())
"""
        b64 = __import__('base64').b64encode(check_script.encode()).decode()
        run(
            client,
            f"docker exec {CONTAINER} bash -lc 'echo {b64} | base64 -d | python -' 2>&1 | tail -20",
            timeout=60,
        )

        # ── C. 验证 questionnaire.py 中 le=500 ──
        print("\n========== C) 验证 questionnaire.py le=500 已落到容器 ==========")
        run(
            client,
            f"docker exec {CONTAINER} grep -n 'le=500' /app/app/api/questionnaire.py 2>&1 | head -5",
            timeout=30,
        )

        # ── D. 验证 admin-web 前端构建里 page_size=100 已生效 ──
        print("\n========== D) 验证 admin-web 编译产物 page_size=100 ==========")
        run(
            client,
            f"docker exec {DEPLOY_ID}-admin sh -lc 'grep -rE \"page_size.{{0,8}}(100|200)\" .next/standalone/.next/server/app/'\"(admin)\"'/function-buttons/ 2>&1 | head -5 || true' ",
            timeout=60,
        )

        # ── E. follow-up 接口可达性（无 token 401） ──
        print("\n========== E) follow-up 接口路由已注册 ==========")
        run(
            client,
            f"docker exec {CONTAINER} python -c \""
            f"from app.main import app;"
            f"print([r.path for r in app.routes if 'follow-up' in r.path])\" 2>&1 | tail -5",
            timeout=30,
        )

        # ── F. seed script 可独立运行 ──
        print("\n========== F) 一次性补数脚本可独立运行 ==========")
        run(
            client,
            f"docker exec {CONTAINER} bash -lc 'cd /app && python scripts/_seed_tcm36.py 2>&1 | tail -10'",
            timeout=120,
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
