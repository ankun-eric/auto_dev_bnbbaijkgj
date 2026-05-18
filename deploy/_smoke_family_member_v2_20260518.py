"""[PRD-FAMILY-MEMBER-V2 2026-05-18] 服务器烟雾测试

1. 服务器容器内 pytest 验证
2. 外网 HTTPS 路由可达性
"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def run(client, cmd, timeout=300, show=True):
    if show:
        print(f"\n$ {cmd[:240]}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60)
    stdout.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-5000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-2000:], flush=True)
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # 容器内 pytest（仅本期新增 + 原有家庭成员相关）
        print("=== 容器内 pytest ===")
        cmd = (
            f"docker exec {BACKEND} python -m pytest "
            "tests/test_family_member_v2_20260518.py "
            "tests/test_family.py "
            "-q -x --tb=short 2>&1 | tail -100"
        )
        rc, out, _ = run(client, cmd, timeout=600)

        # 外网 HTTPS
        print("\n=== 外网 HTTPS ===")
        for path in ["/api/openapi.json", "/ai-home", "/health-profile"]:
            url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}{path}"
            rc, out, _ = run(client, f"curl -ks -o /dev/null -w '%{{http_code}}' -L '{url}'",
                             show=False)
            print(f"  {url} -> {out.strip()}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
