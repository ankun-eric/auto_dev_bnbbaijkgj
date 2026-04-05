import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Bangbang987"

def ssh_exec(client, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:] if len(out) > 3000 else out)
    if err:
        print(f"STDERR: {err[-2000:]}" if len(err) > 2000 else f"STDERR: {err}")
    print(f"Exit code: {exit_code}")
    return out, err, exit_code

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("Connected to server.")

    proj_dir = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

    commands = sys.argv[1:] if len(sys.argv) > 1 else []
    if not commands:
        commands = [
            f"cd {proj_dir} && docker compose -f docker-compose.prod.yml down",
            f"cd {proj_dir} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1",
            f"cd {proj_dir} && docker compose -f docker-compose.prod.yml up -d 2>&1",
            "sleep 10",
            f"cd {proj_dir} && docker compose -f docker-compose.prod.yml ps",
            f"cd {proj_dir} && docker compose -f docker-compose.prod.yml logs --tail=30",
        ]

    for cmd in commands:
        ssh_exec(client, cmd, timeout=600)

    client.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
