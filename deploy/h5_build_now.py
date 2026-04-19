"""Rebuild h5-web service with streaming output."""
import paramiko
import time
import sys

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

def run_stream(ssh, cmd, timeout=1800):
    print(f"\n$ {cmd[:200]}\n", flush=True)
    transport = ssh.get_transport()
    chan = transport.open_session()
    chan.settimeout(timeout)
    chan.get_pty()
    chan.exec_command(cmd)
    out_buf = []
    start = time.time()
    while True:
        if chan.recv_ready():
            data = chan.recv(4096).decode('utf-8', errors='replace')
            out_buf.append(data)
            sys.stdout.write(data)
            sys.stdout.flush()
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        if time.time() - start > timeout:
            print("\n[TIMEOUT]")
            break
        time.sleep(0.1)
    code = chan.recv_exit_status()
    print(f"\n[exit={code}]", flush=True)
    return ''.join(out_buf), code

def main():
    ssh = connect()

    print("=== Rebuilding h5-web service ===")
    out, code = run_stream(ssh,
        f'cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d --build h5-web 2>&1',
        timeout=1800)

    if code != 0:
        print("!! Build failed")
        ssh.close()
        sys.exit(1)

    print("\n=== Waiting 8s for startup ===")
    time.sleep(8)

    print("\n=== Container status ===")
    run_stream(ssh, f'docker ps --format "table {{{{.Names}}}}\\t{{{{.Status}}}}" | grep {DEPLOY_ID}')

    print("\n=== H5 logs (tail 60) ===")
    run_stream(ssh, f'docker logs {DEPLOY_ID}-h5 --tail 60 2>&1')

    ssh.close()
    print("\n=== Rebuild done ===")

if __name__ == '__main__':
    main()
