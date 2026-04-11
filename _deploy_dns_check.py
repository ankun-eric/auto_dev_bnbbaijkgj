"""Check DNS resolution to understand the 502 on production domain."""
import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"


def ssh_exec(ssh, cmd, timeout=15):
    print(f"\n[SSH] {cmd}")
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        combined = out + err
        if combined.strip():
            print(combined.strip()[:2000])
        return out.strip()
    except Exception as e:
        print(f"  Error: {e}")
        return ""


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)

    # DNS resolution
    ssh_exec(ssh, "dig +short newbb.test.bangbangvip.com 2>/dev/null || nslookup newbb.test.bangbangvip.com 2>/dev/null | tail -5")
    ssh_exec(ssh, "dig +short newbb.bangbangvip.com 2>/dev/null || nslookup newbb.bangbangvip.com 2>/dev/null | tail -5")
    ssh_exec(ssh, "hostname -I")

    # Check if newbb.bangbangvip.com points to a CDN or different IP
    ssh_exec(ssh, "curl -sI https://newbb.bangbangvip.com/ 2>/dev/null | head -10")

    ssh.close()


if __name__ == "__main__":
    main()
