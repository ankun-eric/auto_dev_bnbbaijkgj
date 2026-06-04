from _ssh_helper import run
cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "sh -c 'cd /app && python -m pytest "
    "tests/test_bp_ai_v1_20260531.py::test_ai_single_success_with_fallback "
    "--tb=long 2>&1'"
)
rc, o, e = run(cmd, timeout=120)
lines = o.splitlines()
# 仅打印从 FAILURES 到结尾
start = None
for i, l in enumerate(lines):
    if "FAILURES" in l or "Error" in l or "sqlite3" in l.lower() or "Integrity" in l:
        start = max(0, i - 1)
        break
if start is None:
    start = max(0, len(lines) - 80)
print("\n".join(lines[start:start + 200]))
