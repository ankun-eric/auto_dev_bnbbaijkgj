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
        # Check via internal docker network
        "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 wget -q -O - http://localhost:3001/ | head -20",
        # Check via gateway (public URL simulation)
        "curl -s -o /dev/null -w '%{http_code}' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5/ 2>/dev/null || echo 'N/A'",
        "curl -s -o /dev/null -w '%{http_code}' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5/ai-home 2>/dev/null || echo 'N/A'",
    ]
    ssh_exec(commands)
