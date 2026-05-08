"""Deploy bug407 backend fix to test server.

Steps:
1. SCP unified_orders.py + reschedule_notification.py to /home/ubuntu/<deploy_id>/backend/...
2. docker cp into 6b099ed3-...-backend container
3. docker restart backend container
4. wait 8s, hit /health endpoint
"""
import os
import time
import paramiko
from scp import SCPClient

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
SERVER_PROJECT = f"/home/ubuntu/{DEPLOY_ID}"
CONTAINER = f"{DEPLOY_ID}-backend"

LOCAL_FILES = [
    ("backend/app/api/unified_orders.py", "backend/app/api/unified_orders.py"),
    ("backend/app/services/reschedule_notification.py", "backend/app/services/reschedule_notification.py"),
]


def make_client():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=30, allow_agent=False, look_for_keys=False)
    return cli


def run(cli, cmd, timeout=180):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(f"$ {cmd}\n[rc={rc}]\n{out}\n{err}\n---")
    return rc, out, err


def main():
    cli = make_client()
    try:
        with SCPClient(cli.get_transport()) as scp:
            for local_rel, server_rel in LOCAL_FILES:
                local = os.path.abspath(local_rel)
                remote = f"{SERVER_PROJECT}/{server_rel}"
                # ensure parent dir exists
                run(cli, f"mkdir -p $(dirname '{remote}')")
                print(f"-> uploading {local} -> {remote}")
                scp.put(local, remote)

        # docker cp into running container
        for _, server_rel in LOCAL_FILES:
            host_path = f"{SERVER_PROJECT}/{server_rel}"
            in_container = f"/app/{server_rel.split('backend/', 1)[-1]}"
            run(cli, f"docker cp '{host_path}' {CONTAINER}:'{in_container}'")

        # restart backend
        run(cli, f"docker restart {CONTAINER}", timeout=60)

        # wait + health check
        for i in range(20):
            rc, out, _ = run(cli, f"docker exec {CONTAINER} curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/health || true")
            if "200" in out:
                print(f"backend healthy after {i+1} probes")
                break
            time.sleep(2)
        else:
            print("backend health probe never returned 200; inspect logs")
            run(cli, f"docker logs --tail 80 {CONTAINER}")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
