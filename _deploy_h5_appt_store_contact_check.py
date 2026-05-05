"""Quick check of remote layout for H5 deployment."""
import paramiko, sys, time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd, timeout=120):
    print(f">>> {cmd}", flush=True)
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    buf = []
    while True:
        if chan.recv_ready():
            d = chan.recv(8192).decode('utf-8','replace'); sys.stdout.write(d); buf.append(d)
        if chan.recv_stderr_ready():
            d = chan.recv_stderr(8192).decode('utf-8','replace'); sys.stdout.write(d); buf.append(d)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"\n[exit={code}]")
    return code, ''.join(buf)

run(f'ls -la /home/ubuntu/{PROJECT_ID} 2>/dev/null | head -20')
run(f'ls -la /home/ubuntu/autodev/{PROJECT_ID} 2>/dev/null | head -20')
run(f'docker ps --format "{{{{.Names}}}}\t{{{{.Status}}}}" | grep {PROJECT_ID} || echo "no containers"')
run(f'cd /home/ubuntu/{PROJECT_ID} && ls docker-compose*.yml 2>/dev/null')
run(f'cd /home/ubuntu/{PROJECT_ID} && docker compose ps --services 2>/dev/null')

ssh.close()
