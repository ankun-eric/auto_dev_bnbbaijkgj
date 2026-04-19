"""Find h5 service name and rebuild it."""
import paramiko
import time

SERVER = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh

def run(ssh, cmd, timeout=600, show_stdout=True):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out_chunks = []
    err_chunks = []
    while True:
        if stdout.channel.recv_ready():
            data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
            out_chunks.append(data)
            if show_stdout:
                print(data, end='', flush=True)
        if stdout.channel.recv_stderr_ready():
            data = stdout.channel.recv_stderr(4096).decode('utf-8', errors='replace')
            err_chunks.append(data)
            if show_stdout:
                print(data, end='', flush=True)
        if stdout.channel.exit_status_ready() and not stdout.channel.recv_ready() and not stdout.channel.recv_stderr_ready():
            break
        time.sleep(0.05)
    # drain
    rest_out = stdout.read().decode('utf-8', errors='replace')
    rest_err = stderr.read().decode('utf-8', errors='replace')
    if show_stdout:
        if rest_out: print(rest_out, end='')
        if rest_err: print(rest_err, end='')
    out = ''.join(out_chunks) + rest_out
    err = ''.join(err_chunks) + rest_err
    code = stdout.channel.recv_exit_status()
    print(f"\n[exit={code}]")
    return out, err, code

def main():
    ssh = connect()

    # List top-level service keys in compose
    print("=== Service names in docker-compose.prod.yml ===")
    run(ssh, f"awk '/^services:/{{f=1;next}} f && /^[a-zA-Z]/{{f=0}} f && /^  [a-z0-9_-]+:/{{print}}' {REMOTE_DIR}/docker-compose.prod.yml")

    # Get container labels to find compose service name
    print("=== Inspect h5 container ===")
    run(ssh, f"docker inspect {DEPLOY_ID}-h5 --format '{{{{ index .Config.Labels \"com.docker.compose.service\" }}}} project={{{{ index .Config.Labels \"com.docker.compose.project\" }}}}'")

    ssh.close()

if __name__ == '__main__':
    main()
