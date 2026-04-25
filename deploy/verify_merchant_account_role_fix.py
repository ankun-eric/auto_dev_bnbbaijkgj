"""[2026-04-26] 用 admin token 实测验证商家账号列表 + 员工列表接口最终效果。"""
from __future__ import annotations
import re
import sys
import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://localhost/autodev/{DEPLOY_ID}"
DB_CONT = f"{DEPLOY_ID}-db"
BACKEND_CONT = f"{DEPLOY_ID}-backend"
DB_PASS = "bini_health_2026"


def run(c, cmd, timeout=60):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out, flush=True)
    if err.strip():
        print("ERR:", err, flush=True)
    return out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PASS, timeout=30)
    try:
        # 1. 用后端容器的 Python 直接生成 admin token
        py_code = r"""
from app.core.security import create_access_token
from app.core.database import async_session
from sqlalchemy import select
from app.models.models import User, UserRole
import asyncio
async def m():
    async with async_session() as s:
        u = (await s.execute(select(User).where(User.role==UserRole.admin))).scalars().first()
        if u:
            print('USER_ID=' + str(u.id) + ' PHONE=' + (u.phone or ''))
            print('TOKEN_OUTPUT=' + create_access_token(data={'sub': str(u.id)}))
asyncio.run(m())
"""
        # 把脚本 base64 化后注入（避开 shell/heredoc 转义问题）
        import base64
        b64 = base64.b64encode(py_code.encode("utf-8")).decode()
        cmd = (
            f"docker exec {BACKEND_CONT} sh -c "
            f"\"echo {b64} | base64 -d > /app/_gen_admin_token.py && cd /app && python _gen_admin_token.py\" 2>&1"
        )
        out = run(c, cmd, timeout=30)
        m = re.search(r"TOKEN_OUTPUT=([\w\.\-]+)", out)
        if not m:
            print("!! 未拿到 token", flush=True)
            return 1
        token = m.group(1)
        print(f"[+] admin token 长度={len(token)}", flush=True)

        H = f"-H 'Authorization: Bearer {token}'"

        # 2. 调商家账号列表（默认 boss 过滤）
        print("\n=== 测试 GET /api/admin/merchant/accounts （默认应只返回老板） ===", flush=True)
        run(c, f"curl -sk {H} {BASE}/api/admin/merchant/accounts | python3 -m json.tool 2>&1 | head -120", timeout=20)

        # 3. 调测试关闭过滤
        print("\n=== 测试 GET /api/admin/merchant/accounts?role_code=all （所有商家账号） ===", flush=True)
        run(c, f"curl -sk {H} '{BASE}/api/admin/merchant/accounts?role_code=all' | python3 -m json.tool 2>&1 | head -200", timeout=20)

        # 4. 调员工列表
        print("\n=== 测试 GET /api/admin/merchant/accounts/2/staff （6399 老板下的员工） ===", flush=True)
        run(c, f"curl -sk {H} {BASE}/api/admin/merchant/accounts/2/staff | python3 -m json.tool 2>&1 | head -120", timeout=20)
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
