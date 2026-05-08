"""SSH helper for bug407 investigation."""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd: str, timeout: int = 60) -> str:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    cli.close()
    if err.strip():
        out += f"\n[STDERR]\n{err}"
    return out


if __name__ == "__main__":
    cmd = " && ".join(sys.argv[1:]) if len(sys.argv) > 1 else "echo hi"
    print(run(cmd, timeout=180))
