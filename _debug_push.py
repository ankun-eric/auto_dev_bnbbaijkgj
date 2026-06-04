"""调试 push_upstream 的实际返回"""
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE=f"/home/ubuntu/{DEPLOY_ID}"

def run(c, cmd, t=300):
    print(f"$ {cmd}"); _, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace"); err = e.read().decode("utf-8", "replace")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

cmd = (
    f"cd {REMOTE_BASE} && docker compose exec -T backend python -c \""
    "import asyncio, httpx\n"
    "from unittest.mock import patch\n"
    "from app.main import app\n"
    "from app.api.home_safety_v1 import _real_push_upstream\n"
    "\n"
    "class _FakeResp:\n"
    "    status_code = 200\n"
    "    text = '{\\\"code\\\":200,\\\"message\\\":\\\"success\\\"}'\n"
    "    def json(self):\n"
    "        return {'code':200,'message':'success'}\n"
    "\n"
    "async def fake_post(*a, **kw): return _FakeResp()\n"
    "\n"
    "async def main():\n"
    "    with patch.object(httpx.AsyncClient, 'post', fake_post):\n"
    "        r = await _real_push_upstream('http://x.com/api', 'tk', 'd', 'https://cb.com')\n"
    "        print('RESULT=', r)\n"
    "\n"
    "asyncio.run(main())\""
)
run(c, cmd, t=120)
c.close()
