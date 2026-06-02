"""验证关键页面可达性。"""
import sys
sys.path.insert(0, ".")
from deploy._sshlib import run

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

PATHS = [
    "/health-profile/my-guardians",
    "/health-profile/my-guardians/invite",
    "/family-guardian-list",
    "/api/reverse-guardian/guardian-count",  # 需要登录，返回 401 即视为可达
    "/api/docs",
]

for p in PATHS:
    url = BASE + p
    cmd = f"curl -s -o /dev/null -w '%{{http_code}}' '{url}'"
    code, out, err = run(cmd, timeout=20)
    print(f"{p:60s} -> HTTP {out.strip() or '?'}")
