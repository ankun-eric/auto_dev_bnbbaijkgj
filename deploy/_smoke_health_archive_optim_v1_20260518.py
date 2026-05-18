"""[PRD-HEALTH-ARCHIVE-OPTIM-V1] 非UI自动化 smoke：
1) 在容器内跑 pytest test_health_archive_optim_v1_20260518.py
2) 拉网关上的接口连通性
"""
import paramiko, sys, time

HOST = "newbb.test.bangbangvip.com"; PORT=22; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"

def run(c, cmd, t=600, ignore=False):
    print(f"\n$ {cmd[:200]}")
    _, so, se = c.exec_command(cmd, timeout=t+60, get_pty=False)
    so.channel.settimeout(t+60); se.channel.settimeout(t+60)
    out = so.read().decode("utf-8", errors="replace")
    err = se.read().decode("utf-8", errors="replace")
    rc = so.channel.recv_exit_status()
    if out.strip(): print(out[-4000:])
    if err.strip(): print("STDERR:", err[-1500:])
    if rc != 0 and not ignore:
        raise RuntimeError(f"failed rc={rc}")
    return rc, out, err

def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, PORT, USER, PWD, timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # 1) pytest in container
        run(cli, f"docker exec {DEPLOY_ID}-backend python -m pytest tests/test_health_archive_optim_v1_20260518.py -v --no-header 2>&1 | tail -100", t=600, ignore=True)
        # 2) curl 关键路由
        for path in [
            "/api/health-archive/ai-call/settings",
            "/api/health-archive/guardian/summary",
            "/api/health-archive/family-members/guarded-flags",
            "/api/medication-plans/hero-count?consultant_id=0",
            "/api/medication-plans/summary?consultant_id=0",
        ]:
            run(cli, f"curl -sS -o /dev/null -w '%{{http_code}}\\n' http://localhost:8000{path}", t=20, ignore=True)
        # 3) h5 路由
        for path in [
            f"/autodev/{DEPLOY_ID}/h5/health-profile",
            f"/autodev/{DEPLOY_ID}/h5/family-guardian-list",
        ]:
            run(cli, f"curl -sS -o /dev/null -w '%{{http_code}}\\n' https://newbb.test.bangbangvip.com{path}", t=30, ignore=True)
    finally:
        cli.close()

if __name__ == "__main__":
    main()
