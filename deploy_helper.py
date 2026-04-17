import paramiko
import sys
import os

HOSTNAME = "newbb.test.bangbangvip.com"
USERNAME = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/"

def get_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=30)
    return client

def run_cmd(client, cmd, timeout=120):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def main():
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "echo 'No command provided'"
    client = get_client()
    try:
        out, err, code = run_cmd(client, cmd)
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)
        sys.exit(code)
    finally:
        client.close()

if __name__ == "__main__":
    main()
