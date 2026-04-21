"""
Remote deploy script for order-bugfix (commit 208e390).
- SSH into server /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
- git fetch/reset
- docker compose build backend admin-web h5-web
- up -d
- connect gateway to network + reload nginx
- print container status
"""
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NETWORK = f"{DEPLOY_ID}-network"


def step(ssh, title, cmd, timeout=300, show_out=True, show_err=True):
    print("=" * 80)
    print(f"[STEP] {title}")
    print(f"[CMD ] {cmd}")
    t0 = time.time()
    out, err, code = run_cmd(ssh, cmd, timeout=timeout)
    dt = time.time() - t0
    print(f"[EXIT] {code}  ({dt:.1f}s)")
    if show_out and out:
        print("[STDOUT]")
        print(out)
    if show_err and err:
        print("[STDERR]")
        print(err)
    return out, err, code


def main():
    print(f"[deploy] connecting to server...")
    ssh = create_client()
    print(f"[deploy] connected.")

    # a) + b) git fetch + reset
    step(ssh,
         "a+b: Git fetch + reset to origin/master",
         f"cd {PROJ_DIR} && git fetch origin && git reset --hard origin/master && git log -1 --oneline",
         timeout=180)

    # c) docker compose build - long timeout
    out, err, code = step(ssh,
                          "c: docker compose build backend admin-web h5-web",
                          f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build backend admin-web h5-web 2>&1",
                          timeout=900)
    if code != 0:
        print("[ERROR] build failed. Aborting.")
        ssh.close()
        sys.exit(2)

    # d) up -d
    step(ssh,
         "d: docker compose up -d backend admin-web h5-web",
         f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d backend admin-web h5-web 2>&1",
         timeout=180)

    # e) wait for containers
    print("\n[deploy] waiting up to 60s for containers to stabilize...")
    for i in range(6):
        time.sleep(10)
        out, err, code = run_cmd(ssh,
                                 f"docker ps --filter 'name={DEPLOY_ID}' --format '{{{{.Names}}}}\t{{{{.Status}}}}'",
                                 timeout=30)
        print(f"[wait {(i+1)*10}s]")
        print(out)

    # f) gateway container detect + connect network
    out, err, code = run_cmd(ssh,
                             'docker ps --format "{{.Names}}" | grep -i gateway',
                             timeout=30)
    gw_name = out.strip().split("\n")[0] if out.strip() else ""
    print(f"\n[deploy] gateway container: {gw_name!r}")
    if gw_name:
        step(ssh,
             f"f: connect gateway to {NETWORK}",
             f"docker network connect {NETWORK} {gw_name} 2>&1 || true",
             timeout=30)
        # g) reload nginx
        step(ssh,
             "g: gateway nginx reload",
             f"docker exec {gw_name} nginx -s reload 2>&1",
             timeout=30)
    else:
        print("[WARN] gateway container not found")

    # h) final status
    step(ssh,
         "h: final container status",
         f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}'",
         timeout=30)

    # Bonus: show current git commit on server
    step(ssh,
         "verify: current git commit",
         f"cd {PROJ_DIR} && git log -1 --oneline",
         timeout=30)

    ssh.close()
    print("[deploy] done.")


if __name__ == "__main__":
    main()
