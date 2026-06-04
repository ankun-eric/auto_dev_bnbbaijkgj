import sys
sys.path.insert(0, "deploy")
from _sshlib import run

c = "6b099ed3-7175-4a78-91f4-44570c84ed27-h5"
cmd = (
    f"docker exec {c} sh -lc "
    f"'echo ===family-invite ref===; grep -rl family-invite /app/.next/static/chunks/app/health-profile/archive-list 2>/dev/null | head -3; "
    f"echo ===old testid 邀请码 InviteCode===; grep -rl InviteCode /app/.next/static/chunks/app/health-profile/archive-list 2>/dev/null | head -3'"
)
code, out, err = run(cmd, timeout=60)
print("EXIT", code)
print(out)
if err:
    print("ERR", err[-800:])
