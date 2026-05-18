import paramiko
HOST = "newbb.test.bangbangvip.com"; PORT=22; USER="ubuntu"; PWD="Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(c, cmd, t=120):
    print(f"\n$ {cmd[:180]}")
    _, so, se = c.exec_command(cmd, timeout=t+30, get_pty=False)
    so.channel.settimeout(t+30); se.channel.settimeout(t+30)
    out = so.read().decode(); err = se.read().decode()
    rc = so.channel.recv_exit_status()
    if out.strip(): print(out[-3000:])
    if err.strip(): print("STDERR:", err[-1000:])
    return rc

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, PORT, USER, PWD, timeout=30, allow_agent=False, look_for_keys=False)
try:
    # 1) 容器内 curl 后端
    for path in [
        "/api/health-archive/ai-call/settings",
        "/api/health-archive/guardian/summary",
        "/api/health-archive/family-members/guarded-flags",
        "/api/medication-plans/hero-count?consultant_id=0",
        "/api/medication-plans/summary?consultant_id=0",
    ]:
        run(cli, f"docker exec {DID}-backend curl -sS -o /dev/null -w '%{{http_code}}\\n' http://localhost:8000{path}")
    # 2) 公网 gateway 验证
    BASE = f"https://newbb.test.bangbangvip.com/autodev/{DID}"
    for path in [
        "/api/health-archive/ai-call/settings",
        "/api/health-archive/guardian/summary",
        "/api/health-archive/family-members/guarded-flags",
        "/api/medication-plans/hero-count?consultant_id=0",
        "/h5/health-profile",
        "/h5/family-guardian-list",
    ]:
        run(cli, f"curl -sS -L -o /dev/null -w '%{{http_code}}\\n' {BASE}{path}")
    # 3) 安装并跑后端单元测试
    rc = run(cli, f"docker exec {DID}-backend pip install -q pytest pytest-asyncio httpx 2>&1 | tail -5")
    rc = run(cli, f"docker exec {DID}-backend python -m pytest tests/test_health_archive_optim_v1_20260518.py -v --no-header 2>&1 | tail -80", t=300)
finally:
    cli.close()
