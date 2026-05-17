"""Probe backend container for timezone test file and available routes."""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=60):
    _, o, e = cli.exec_command(cmd, timeout=timeout)
    return o.read().decode(errors="replace"), e.read().decode(errors="replace")

print("=== check timezone test exists ===")
out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/tests/ | grep -E 'timezone|20260517'")
print(out or err)

print("\n=== pip install pytest (try) and run test ===")
out, err = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend pip install pytest 2>&1 | tail -10", timeout=120)
print(out)

print("\n=== run pytest ===")
out, err = run(
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend sh -c "
    "'cd /app && python -m pytest tests/test_timezone_global_20260517.py -v 2>&1' | tail -80",
    timeout=180,
)
print(out)

cli.close()
