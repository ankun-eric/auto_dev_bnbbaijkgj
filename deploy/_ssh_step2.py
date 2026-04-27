import paramiko
import sys
import time

def ssh_exec(commands, timeout=300):
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
        if exit_status != 0 and 'fatal' in err.lower():
            print(f"WARNING: Command failed, continuing...")
    
    client.close()

if __name__ == "__main__":
    proj_dir = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
    token_url = "https://ankun-eric:{GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    
    commands = [
        f"cd {proj_dir} && git remote set-url origin {token_url}",
        f"cd {proj_dir} && git config http.postBuffer 524288000",
        f"cd {proj_dir} && git fetch origin --depth=1",
        f"cd {proj_dir} && git reset --hard origin/master",
        f"cd {proj_dir} && git log -1 --oneline",
    ]
    ssh_exec(commands)
