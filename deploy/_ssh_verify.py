import paramiko
import sys

def ssh_exec(commands, timeout=60):
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
        # Check all container status
        f"cd {proj_dir} && docker compose -f docker-compose.prod.yml ps",
        # Check frontend container logs
        f"cd {proj_dir} && docker compose -f docker-compose.prod.yml logs --tail=20 h5-web",
        # Quick health check via curl
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/ 2>/dev/null || echo 'direct curl failed'",
    ]
    ssh_exec(commands)
