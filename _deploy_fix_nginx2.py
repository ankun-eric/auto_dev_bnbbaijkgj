"""Check host-level nginx and DNS for newbb.bangbangvip.com vs newbb.test."""
import paramiko
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
PROJECT_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def ssh_exec(ssh, cmd, timeout=30):
    print(f"\n[SSH] {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        combined = out + err
        if combined.strip():
            print(combined.strip()[:3000])
        return exit_code, out.strip(), err.strip()
    except Exception as e:
        print(f"  Error: {e}")
        return 1, "", str(e)


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected!")

    # Check if there's a host-level nginx
    print("\n===== HOST NGINX =====")
    ssh_exec(ssh, "which nginx 2>/dev/null; systemctl is-active nginx 2>/dev/null || echo 'no host nginx'")

    # Check gateway-nginx port bindings
    print("\n===== GATEWAY PORT BINDINGS =====")
    ssh_exec(ssh, "docker port gateway-nginx")

    # Check if the gateway listens on 443 or if there's another layer
    print("\n===== LISTENING ON 443 and 80 =====")
    ssh_exec(ssh, "ss -tlnp | grep -E ':443|:80'")

    # Try the test URL
    print("\n===== Test with test subdomain =====")
    ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config -k")

    # Test the production URL
    print("\n===== Test production URL =====")
    ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config")

    # Check gateway-nginx error logs (last 5 lines)
    print("\n===== Gateway nginx error log (last 5) =====")
    ssh_exec(ssh, "docker logs gateway-nginx --tail 5 2>&1")

    # Check if gateway is accessible on this host directly
    print("\n===== Direct test to localhost gateway =====")
    ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:80/autodev/{PROJECT_ID}/api/home-config")
    ssh_exec(ssh, f"curl -s http://localhost:80/autodev/{PROJECT_ID}/api/home-config")

    ssh.close()


if __name__ == "__main__":
    main()
