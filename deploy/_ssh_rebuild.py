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
        # Rebuild h5-web container only
        f"cd {proj_dir} && docker compose -f docker-compose.prod.yml build --no-cache h5-web",
        # Restart only h5-web
        f"cd {proj_dir} && docker compose -f docker-compose.prod.yml up -d h5-web",
        # Wait and check status
        f"sleep 10 && cd {proj_dir} && docker compose -f docker-compose.prod.yml ps",
    ]
    ssh_exec(commands)
