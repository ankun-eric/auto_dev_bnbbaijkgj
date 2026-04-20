"""Deploy home-3bugs fix to newbb.test server.

Execute in sequence:
 1. git fetch / reset on server
 2. docker compose up -d --build --no-deps for h5, backend, admin-web
 3. verify containers running
 4. ensure gateway connected to project network
 5. reload gateway nginx
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from _ssh_home3bugs import get_client, run

PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
NETWORK = "6b099ed3-7175-4a78-91f4-44570c84ed27-network"

COMMANDS = [
    f"cd {PROJECT_DIR} && pwd",
    f"cd {PROJECT_DIR} && git fetch origin 2>&1 | tail -20",
    f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 | tail -5",
    f"cd {PROJECT_DIR} && git clean -fd 2>&1 | tail -10",
    f"cd {PROJECT_DIR} && git log -1 --oneline",
    f"cd {PROJECT_DIR} && ls docker-compose.prod.yml gateway-routes.conf 2>&1",
    # Build and bring up containers. Use sudo -S in case.
    f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --build --no-deps h5 backend admin-web 2>&1 | tail -60",
]


def main():
    ssh = get_client()
    try:
        for c in COMMANDS:
            run(ssh, c, timeout=900)
        print("=== Waiting 20s for containers ===")
        import time
        time.sleep(20)
        run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1")
        # ensure gateway container connects to network
        run(ssh, "docker ps --format '{{.Names}}' | grep -i gateway | head -3")
        run(ssh, f"GW=$(docker ps --format '{{{{.Names}}}}' | grep -i gateway | head -1); echo \"gateway=$GW\"; docker network connect {NETWORK} $GW 2>&1 || true")
        run(ssh, f"GW=$(docker ps --format '{{{{.Names}}}}' | grep -i gateway | head -1); docker exec $GW nginx -t 2>&1")
        run(ssh, f"GW=$(docker ps --format '{{{{.Names}}}}' | grep -i gateway | head -1); docker exec $GW nginx -s reload 2>&1")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
