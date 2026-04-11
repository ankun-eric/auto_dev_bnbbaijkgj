"""Final verification using both test and production URLs."""
import paramiko
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Bangbang987"
PROJECT_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


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
    print("Connected!\n")

    # Check nginx server_name and add newbb.bangbangvip.com
    print("===== Current nginx server_name =====")
    ssh_exec(ssh, "docker exec gateway-nginx grep 'server_name' /etc/nginx/nginx.conf")

    # Add newbb.bangbangvip.com to the server_name
    print("\n===== Adding newbb.bangbangvip.com to server_name =====")
    ssh_exec(ssh, """docker exec gateway-nginx sh -c "sed -i 's/server_name newbb.test.bangbangvip.com;/server_name newbb.test.bangbangvip.com newbb.bangbangvip.com;/g' /etc/nginx/nginx.conf" """)
    ssh_exec(ssh, "docker exec gateway-nginx nginx -t")
    ssh_exec(ssh, "docker exec gateway-nginx nginx -s reload")
    time.sleep(2)

    # Verify the config change
    ssh_exec(ssh, "docker exec gateway-nginx grep 'server_name' /etc/nginx/nginx.conf")

    # Test production URL again
    print("\n===== Test production URL after fix =====")
    rc, api_resp, _ = ssh_exec(ssh, f"curl -s https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config")
    rc, h5_code, _ = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/")

    # Test the test URL too
    print("\n===== Test URL verification =====")
    rc, api_test, _ = ssh_exec(ssh, f"curl -s https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config -k")
    rc, h5_test, _ = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/ -k")

    # Container status
    print("\n===== Container Status =====")
    rc, containers, _ = ssh_exec(ssh, f"docker ps --filter 'name={PROJECT_ID}'")

    ssh.close()

    print("\n\n" + "=" * 60)
    print("FINAL DEPLOYMENT STATUS")
    print("=" * 60)

    print(f"\n--- Container Status ---")
    print(containers)

    print(f"\n--- API Response (via test domain) ---")
    print(api_test)

    print(f"\n--- API Response (via production domain) ---")
    print(api_resp if api_resp else "N/A or 502")

    print(f"\n--- H5 Web Status ---")
    print(f"  Test domain (newbb.test...): HTTP {h5_test}")
    print(f"  Prod domain (newbb...):      HTTP {h5_code}")

    api_ok = "search_placeholder" in (api_test or api_resp or "")
    h5_ok = h5_test in ("200", "301", "302") or h5_code in ("200", "301", "302")

    print(f"\n--- Summary ---")
    print(f"Backend API: {'OK' if api_ok else 'FAILED'}")
    print(f"H5 Web:      {'OK' if h5_ok else 'FAILED'}")
    print(f"\nAccessible URLs:")
    print(f"  API:  https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config")
    print(f"  H5:   https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/")
    if "search_placeholder" in (api_resp or ""):
        print(f"  API (prod): https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/api/home-config")
        print(f"  H5 (prod):  https://newbb.bangbangvip.com/autodev/{PROJECT_ID}/")


if __name__ == "__main__":
    main()
