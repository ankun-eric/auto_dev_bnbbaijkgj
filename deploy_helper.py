import paramiko
import os
import sys
import time

SERVER = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Bangbang987'

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=15)
    return ssh

def run_cmd(ssh, cmd, timeout=300):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def setup_key():
    ssh = get_ssh()
    print("SSH connected OK")
    pub_key_path = os.path.join(os.environ['USERPROFILE'], '.ssh', 'id_rsa.pub')
    with open(pub_key_path, 'r') as f:
        pub_key = f.read().strip()
    run_cmd(ssh, 'mkdir -p ~/.ssh && chmod 700 ~/.ssh')
    time.sleep(0.3)
    check_cmd = f'grep -c "{pub_key[:60]}" ~/.ssh/authorized_keys 2>/dev/null || echo 0'
    out, _, _ = run_cmd(ssh, check_cmd)
    if out.strip() == '0':
        run_cmd(ssh, f'echo "{pub_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys')
        print("KEY_ADDED")
    else:
        print("KEY_EXISTS")
    ssh.close()

def remote_exec(cmd, timeout=300):
    ssh = get_ssh()
    out, err, code = run_cmd(ssh, cmd, timeout)
    ssh.close()
    return out, err, code

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'setup_key'
    if action == 'setup_key':
        setup_key()
    elif action == 'exec':
        cmd = sys.argv[2]
        out, err, code = remote_exec(cmd, timeout=600)
        if out:
            print(out, end='')
        if err:
            print(err, end='', file=sys.stderr)
        sys.exit(code)
