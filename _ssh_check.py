import paramiko
import sys

def ssh_exec(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Bangbang987', timeout=15)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

if __name__ == '__main__':
    cmd = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'echo hello'
    out, err = ssh_exec(cmd)
    if out:
        print(out)
    if err:
        print("STDERR:", err)
