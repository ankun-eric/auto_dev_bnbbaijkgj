import sys
sys.path.insert(0, "deploy")
from _sshlib import run, DEPLOY_ID

c = "6b099ed3-7175-4a78-91f4-44570c84ed27-h5"
cmd = (
    f"docker exec {c} sh -lc "
    f"'grep -rl hp-invite-now-dialog /app/.next 2>/dev/null | head -3; "
    f"echo ===btn===; grep -rl hp-invite-now-btn /app/.next 2>/dev/null | head -3'"
)
code, out, err = run(cmd, timeout=60)
print("EXIT", code)
print(out)
if err:
    print("ERR", err[-800:])
