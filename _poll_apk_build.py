#!/usr/bin/env python3
"""Poll GHA workflow run until complete."""
import os, sys, time, json, subprocess

RUN_ID = "25302157758"
REPO = "ankun-eric/auto_dev_bnbbaijkgj"
MAX_MIN = 30
INTERVAL = 30

env = os.environ.copy()
env["GH_TOKEN"] = os.environ.get("GH_TOKEN", "")  # 从环境变量读取，不硬编码

start = time.time()
while True:
    elapsed = int(time.time() - start)
    if elapsed > MAX_MIN * 60:
        print(f"TIMEOUT after {elapsed}s")
        sys.exit(2)
    try:
        r = subprocess.run(
            ["gh", "run", "view", RUN_ID, "-R", REPO, "--json", "status,conclusion"],
            env=env, capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            print(f"[{elapsed}s] gh failed: {r.stderr[:200]}")
        else:
            data = json.loads(r.stdout)
            status = data.get("status")
            conclusion = data.get("conclusion")
            print(f"[{elapsed}s] status={status} conclusion={conclusion}")
            if status == "completed":
                if conclusion == "success":
                    print("BUILD_SUCCESS")
                    sys.exit(0)
                else:
                    print(f"BUILD_FAILED: {conclusion}")
                    sys.exit(1)
    except Exception as e:
        print(f"[{elapsed}s] exception: {e}")
    time.sleep(INTERVAL)
