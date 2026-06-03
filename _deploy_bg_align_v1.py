"""[PRD-GLUCOSE-CARD-ALIGN-BP-V1] 远程部署助手：连接服务器、git 拉取、重建 h5 容器、reload gateway。"""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(cmd, timeout=900):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    cli.close()
    return code, out, err


if __name__ == "__main__":
    cmd = sys.stdin.read()
    timeout = int(sys.argv[1]) if len(sys.argv) >= 2 else 900
    code, out, err = run(cmd, timeout=timeout)
    sys.stdout.write(out)
    if err:
        sys.stderr.write("\n--STDERR--\n" + err)
    sys.exit(code)
