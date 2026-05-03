"""Read the actual gateway nginx route file from host."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str) -> str:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err:
        print("[stderr]", err[:500])
    return out


run(f"cat /home/ubuntu/gateway/conf.d/{UUID}.conf 2>/dev/null")
run(f"ls /home/ubuntu/gateway/conf.d/ | grep -i {UUID[:8]}")

ssh.close()
