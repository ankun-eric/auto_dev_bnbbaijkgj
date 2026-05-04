#!/usr/bin/env python3
"""Poll GitHub Actions run until completion."""
import json
import subprocess
import sys
import time

RUN_ID = "25299847542"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
MAX_WAIT_SEC = 30 * 60
INTERVAL = 30


def gh_json(args, retries=3):
    delay = 10
    last_err = ""
    for attempt in range(retries):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return json.loads(r.stdout)
            last_err = r.stderr
        except Exception as e:
            last_err = str(e)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"gh failed: {last_err}")


def main():
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        if elapsed > MAX_WAIT_SEC:
            print(f"TIMEOUT after {elapsed}s")
            sys.exit(2)
        try:
            data = gh_json([
                "gh", "run", "view", RUN_ID,
                "--repo", REPO,
                "--json", "status,conclusion,displayTitle,url",
            ])
        except Exception as e:
            print(f"[{elapsed}s] poll error: {e}")
            time.sleep(INTERVAL)
            continue
        status = data.get("status", "?")
        conclusion = data.get("conclusion", "")
        print(f"[{elapsed}s] status={status} conclusion={conclusion}", flush=True)
        if status == "completed":
            if conclusion == "success":
                print("BUILD SUCCESS")
                sys.exit(0)
            else:
                print(f"BUILD FAILED: {conclusion}")
                sys.exit(1)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
