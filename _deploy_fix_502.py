"""Fix 502: reload gateway nginx, ensure container network, and re-verify."""
import paramiko
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
PROJECT_DIR = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
PROJECT_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def ssh_exec(ssh, cmd, timeout=60):
    print(f"\n[SSH] {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    combined = out + err
    if combined.strip():
        print(combined.strip()[:3000])
    return exit_code, out.strip(), err.strip()


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected!")

    # Check which network the docker-compose uses
    print("\n===== Check docker-compose network name =====")
    ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml config --services")

    # The compose file defines 'app-network' which maps to an external name
    # After docker compose up, the network is named: <project>_<network> or <project>-<network>
    # Backend is on: 3b7b999d-...-network
    # Gateway is on both: 3b7b999d-...-network AND 3b7b999d-..._bini-network

    # Make sure the new containers are connected to the gateway's networks
    print("\n===== Ensure backend connected to correct network =====")
    # The gateway can reach internally (we proved this), so the issue is likely DNS caching
    # Restart/reload the gateway nginx
    print("\n===== Restart gateway nginx =====")
    ssh_exec(ssh, "docker exec gateway-nginx nginx -s reload")

    # Also check the nginx config in detail
    print("\n===== Full nginx config for project =====")
    ssh_exec(ssh, f"docker exec gateway-nginx cat /etc/nginx/conf.d/{PROJECT_ID}.conf")

    # Wait a moment
    time.sleep(3)

    # Test again
    print("\n===== Test API after nginx reload =====")
    rc, api_out, _ = ssh_exec(ssh, f"curl -s {BASE_URL}/api/home-config")

    print("\n===== Test H5 after nginx reload =====")
    rc, h5_out, _ = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/")

    if "502" in api_out or "502" in h5_out:
        print("\n===== Still 502. Checking resolver and DNS =====")
        # Check the nginx resolver config
        ssh_exec(ssh, "docker exec gateway-nginx cat /etc/nginx/nginx.conf | head -40")

        # Try connecting containers to gateway network manually
        print("\n===== Reconnecting containers to gateway network =====")
        # Disconnect old stale connections and reconnect
        for svc in ["backend", "h5"]:
            container = f"{PROJECT_ID}-{svc}"
            # Try to connect to the bini-network (older network name)
            ssh_exec(ssh, f"docker network connect {PROJECT_ID}_bini-network {container} 2>/dev/null; echo 'done'")

        # Reload nginx again
        ssh_exec(ssh, "docker exec gateway-nginx nginx -s reload")
        time.sleep(3)

        # Final test
        print("\n===== Final test =====")
        rc, api_out, _ = ssh_exec(ssh, f"curl -s {BASE_URL}/api/home-config")
        rc, h5_code, _ = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/")
        print(f"\nAPI response: {api_out[:500]}")
        print(f"H5 status: {h5_code}")

    # Container status
    print("\n===== Container Status =====")
    rc, containers, _ = ssh_exec(ssh, f"docker ps --filter 'name={PROJECT_ID}'")

    ssh.close()

    print("\n\n===== SUMMARY =====")
    if "502" not in api_out and api_out:
        print(f"Backend API: OK")
        print(f"API Response: {api_out[:500]}")
    else:
        print(f"Backend API: STILL 502")

    if h5_out not in ("502",) and h5_code not in ("502",):
        print(f"H5 Web: OK")
    else:
        print(f"H5 Web: STILL 502")


if __name__ == "__main__":
    main()
