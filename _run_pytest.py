"""Install pytest-asyncio and run timezone test."""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=180):
    _, o, e = cli.exec_command(cmd, timeout=timeout)
    return o.read().decode(errors="replace"), e.read().decode(errors="replace")

print("=== install pytest-asyncio ===")
out, _ = run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend pip install pytest-asyncio 2>&1 | tail -10", 180)
print(out)

print("\n=== run pytest test_timezone_global_20260517.py ===")
out, _ = run(
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend sh -c "
    "'cd /app && python -m pytest tests/test_timezone_global_20260517.py -v --no-header -p no:cacheprovider 2>&1' | tail -100",
    timeout=300,
)
print(out)

cli.close()
