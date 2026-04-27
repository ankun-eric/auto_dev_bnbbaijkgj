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
    base = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
    commands = [
        # Follow redirects for h5 frontend
        f"curl -sL -o /dev/null -w '%{{http_code}}' '{base}/h5/ai-home'",
        # Also check with trailing slash
        f"curl -sL -o /dev/null -w '%{{http_code}}' '{base}/h5/ai-home/'",
        # Check backend API health
        f"curl -sL -o /dev/null -w '%{{http_code}}' '{base}/api/health'",
        # Check that the h5 page has content
        f"curl -sL '{base}/h5/ai-home/' 2>/dev/null | head -5",
    ]
    ssh_exec(commands)
