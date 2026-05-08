"""查看 pytest 失败的详细信息。"""
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def ssh(cmd, timeout=600):
    print(f"[REMOTE] $ {cmd[:200]}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    client.close()
    print(out)
    print(f"[rc={rc}]")


container = f"{DEPLOY_ID}-backend"
# 全屏显示失败用例
ssh(
    f"""docker exec -w /app {container} sh -c "python -W ignore -m pytest tests/test_reschedule_dual_identity.py -p no:warnings --tb=long 2>&1 | grep -E 'FAILED|assert|AssertionError|RuntimeError|Error|response|status_code|body|appointment|reschedule|RESCHEDULE_|test_t' | head -200" """
)
