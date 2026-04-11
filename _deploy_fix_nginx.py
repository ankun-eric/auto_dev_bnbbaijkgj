"""Deeper investigation of nginx HTTPS config and fix the 502."""
import paramiko
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
PROJECT_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def ssh_exec(ssh, cmd, timeout=60):
    print(f"\n[SSH] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    combined = out + err
    if combined.strip():
        print(combined.strip()[:5000])
    return exit_code, out.strip(), err.strip()


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected!")

    # Full nginx.conf
    print("\n===== FULL nginx.conf =====")
    ssh_exec(ssh, "docker exec gateway-nginx cat /etc/nginx/nginx.conf")

    # Check nginx error log for clues
    print("\n===== NGINX ERROR LOG (last 20) =====")
    ssh_exec(ssh, "docker exec gateway-nginx tail -20 /var/log/nginx/error.log")

    # Test with HTTP (port 80) to see if that works
    print("\n===== Test via HTTP (port 80) =====")
    ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' http://newbb.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config 2>/dev/null || echo 'http test failed'")

    # Test internally - which port does gateway-nginx listen on?
    print("\n===== Gateway nginx listening ports =====")
    ssh_exec(ssh, "docker port gateway-nginx")
    ssh_exec(ssh, "docker inspect gateway-nginx --format='{{range $p, $conf := .HostConfig.PortBindings}}{{$p}}={{(index $conf 0).HostPort}} {{end}}'")

    # Check if there's a separate proxy in front (like the host nginx)
    print("\n===== Host nginx config =====")
    ssh_exec(ssh, "ls /etc/nginx/sites-enabled/ 2>/dev/null; ls /etc/nginx/conf.d/ 2>/dev/null")
    ssh_exec(ssh, "cat /etc/nginx/sites-enabled/default 2>/dev/null | head -80")
    ssh_exec(ssh, "cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -80")

    # Check if host nginx is running
    print("\n===== Host nginx status =====")
    ssh_exec(ssh, "systemctl status nginx 2>/dev/null | head -10")
    ssh_exec(ssh, "nginx -t 2>&1 | head -5")

    ssh.close()


if __name__ == "__main__":
    main()
