import paramiko
import sys

def ssh_exec(host, cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, username='ubuntu', password='Bangbang987', timeout=10)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode()
        err = stderr.read().decode()
        ssh.close()
        return out, err
    except Exception as e:
        return '', str(e)

if __name__ == '__main__':
    host = sys.argv[1]
    cmd = ' '.join(sys.argv[2:])
    out, err = ssh_exec(host, cmd)
    if out:
        print(out)
    if err:
        print("STDERR:", err)
