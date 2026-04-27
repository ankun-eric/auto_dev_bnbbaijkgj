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
    commands = [
        # Find gateway container
        "docker ps --format '{{.Names}}' | grep gateway | head -1",
        # Connect network (ignore errors if already connected)
        "GATEWAY=$(docker ps --format '{{.Names}}' | grep gateway | head -1) && echo \"Gateway: $GATEWAY\" && docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27_app-network $GATEWAY 2>/dev/null; docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network $GATEWAY 2>/dev/null; echo 'Network connect attempted'",
        # Reload nginx
        "GATEWAY=$(docker ps --format '{{.Names}}' | grep gateway | head -1) && docker exec $GATEWAY nginx -s reload && echo 'Nginx reloaded'",
    ]
    ssh_exec(commands)
