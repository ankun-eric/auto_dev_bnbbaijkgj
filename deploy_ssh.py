import paramiko
import sys
import time

SERVER = "newbb.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"

def ssh_exec(command, timeout=600):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    
    print(f">>> {command}")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    
    if out.strip():
        print(out)
    if err.strip():
        print(f"STDERR: {err}")
    print(f"Exit code: {exit_code}")
    print("---")
    
    ssh.close()
    return exit_code, out, err

if __name__ == "__main__":
    command = " ".join(sys.argv[1:])
    if command:
        ssh_exec(command)
