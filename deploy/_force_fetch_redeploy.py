"""Force fetch latest from origin and rebuild."""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DD = f"/home/ubuntu/{DEPLOY_ID}"
import os
# 从环境变量读取 GitHub PAT，避免硬编码 secret 被 push protection 拒绝
_GH_TOKEN = os.environ.get("GH_TOKEN", "<REDACTED_GH_TOKEN>")
GIT_URL = f"https://ankun-eric:{_GH_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"


def run(c, cmd, timeout=900):
    print(f"\n$ {cmd[:250]}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out.strip():
        print(out[-4000:])
    if err.strip():
        print("ERR:", err[-1500:])
    print(f"[exit={rc}]")
    return rc, out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PWD, look_for_keys=False, allow_agent=False, timeout=30)
    try:
        # 1. Inspect remote URL
        run(c, f"cd {DD} && git remote -v")
        # 2. Show origin master ref (server-side)
        run(c, f"cd {DD} && git ls-remote origin master 2>&1 | head -3")
        # 3. Force update remote URL with token (in case credentials stale)
        run(c, f"cd {DD} && git remote set-url origin '{GIT_URL}'")
        # 4. Hard fetch all
        run(c, f"cd {DD} && git fetch --all --prune 2>&1 | tail -10")
        run(c, f"cd {DD} && git ls-remote origin master 2>&1 | head -3")
        # 5. Show branches
        run(c, f"cd {DD} && git branch -a 2>&1 | head -10")
        run(c, f"cd {DD} && git log origin/master --oneline | head -3")
        # 6. Reset
        run(c, f"cd {DD} && git reset --hard origin/master 2>&1 | tail -3")
        run(c, f"cd {DD} && git log -1 --oneline")
        # 7. Verify file
        run(c, f"ls -la {DD}/backend/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py 2>&1")
        # 8. Rebuild only backend (faster, h5 doesn't need it again)
        run(c, f"cd {DD} && BC=$(git log -1 --format='%H') && echo \"BUILD_COMMIT=$BC\" > .env.build && grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null || true; cat .env.build >> .env.tmp; mv .env.tmp .env; tail -3 .env")
        run(c, f"cd {DD} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -8", timeout=900)
        run(c, f"cd {DD} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -8", timeout=1500)
        run(c, f"cd {DD} && docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend h5-web 2>&1 | tail -10")
        run(c, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")
        time.sleep(8)
        # Verify file in container
        run(c, f"docker exec {DEPLOY_ID}-backend ls /app/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py 2>&1")
        # SSL check
        run(c, f"docker exec gateway nginx -t 2>&1 && docker exec gateway nginx -s reload 2>&1")
        time.sleep(2)
        run(c, f"curl -Is https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ 2>&1 | head -3")
        run(c, f"curl -s https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health 2>&1")
    finally:
        c.close()


if __name__ == "__main__":
    main()
