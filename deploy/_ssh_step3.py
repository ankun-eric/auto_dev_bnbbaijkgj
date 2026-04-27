import paramiko
import sys
import time

def ssh_exec(commands, timeout=600):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)
    
    for cmd in commands:
        print(f"\n>>> {cmd}")
        sys.stdout.flush()
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out.rstrip())
        if err:
            print(f"[STDERR] {err.rstrip()}")
        print(f"[exit: {exit_status}]")
        sys.stdout.flush()
    
    client.close()

if __name__ == "__main__":
    proj_dir = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
    
    commands = [
        # Check docker-compose services
        f"cd {proj_dir} && cat docker-compose.prod.yml | grep -E '(services:|^  [a-z])'",
        # Check current running containers
        f"cd {proj_dir} && docker compose -f docker-compose.prod.yml ps",
    ]
    ssh_exec(commands)
