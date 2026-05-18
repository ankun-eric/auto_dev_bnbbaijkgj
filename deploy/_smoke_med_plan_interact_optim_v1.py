"""[PRD-MED-PLAN-INTERACT-OPTIM-V1] 容器内 pytest 验证 + 外网冒烟"""
from __future__ import annotations
import paramiko, sys, time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def run(client, cmd, timeout=300):
    print(f"\n$ {cmd[:200]}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60)
    stdout.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-5000:])
    if err:
        print("STDERR:", err[-2000:])
    return rc, out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)
    try:
        print("=== 1. 容器内 pytest（10 用例）===")
        rc, out, _ = run(
            c,
            f"docker exec {BACKEND} bash -lc 'cd /app && python -m pytest tests/test_med_plan_interact_optim_v1_20260518.py -x -v 2>&1 | tail -80'",
            timeout=300,
        )
        print(f"pytest rc={rc}")
        if rc != 0:
            print("\n[FAIL] pytest failed")
            sys.exit(1)

        print("\n=== 2. 外网冒烟 ===")
        base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for url in [
            f"{base}/api/openapi.json",
            f"{base}/ai-home",
            f"{base}/api/health-plan/medications/check-duplicate",
            f"{base}/api/medication-plan/check-duplicate",
        ]:
            rc, out, _ = run(
                c,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}'" + (" -X POST -H 'Content-Type: application/json' -d '{}'" if "check-duplicate" in url else ""),
                timeout=30,
            )
            print(f"  {url} -> {out.strip()}")
        print("\n=== 3. 检查迁移脚本输出 ===")
        run(c, f"docker logs --tail 30 {BACKEND} 2>&1 | grep -i 'med_plan_interact_optim' | tail -10", timeout=20)
    finally:
        c.close()


if __name__ == "__main__":
    main()
