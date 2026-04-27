import paramiko
import sys
import time

def ssh_exec(commands, timeout=120):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)
    
    for cmd in commands:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out.rstrip())
        if err:
            print(f"[STDERR] {err.rstrip()}")
        print(f"[exit: {exit_status}]")
    
    client.close()

if __name__ == "__main__":
    commands = [
        "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ && git fetch origin",
        "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ && git reset --hard origin/master",
        "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ && git clean -fd",
        "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ && git log -1 --oneline",
    ]
    ssh_exec(commands)
