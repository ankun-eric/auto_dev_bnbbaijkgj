import sys, paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(cmd, timeout=120):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    cli.close()
    return out, err

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo hi"
    out, err = run(cmd)
    print("=== STDOUT ===")
    print(out)
    if err.strip():
        print("=== STDERR ===")
        print(err)
