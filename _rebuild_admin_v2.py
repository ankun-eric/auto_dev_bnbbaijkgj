"""rebuild admin-web image and smoke test the new APIs."""
import paramiko, time
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASSWORD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_BASE=f'/home/ubuntu/{DEPLOY_ID}'
BASE_URL=f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

print("=== rebuild admin-web ===")
cmd = f"cd {REMOTE_BASE} && docker compose up -d --build admin-web 2>&1 | tail -30"
print("$", cmd)
_, o, _ = c.exec_command(cmd, timeout=900)
print(o.read().decode("utf-8","replace"))

time.sleep(8)

print("=== smoke api: list callback_log (期望 401) ===")
cmd = f"curl -s -o /dev/null -w '%{{http_code}}' '{BASE_URL}/api/admin/home_safety/callback_log'"
_, o, _ = c.exec_command(cmd, timeout=30); print("HTTP", o.read().decode().strip())

print("=== smoke api: precheck (期望 401) ===")
cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -X POST '{BASE_URL}/api/admin/home_safety/callback_config/precheck'"
_, o, _ = c.exec_command(cmd, timeout=30); print("HTTP", o.read().decode().strip())

print("=== smoke api: callback alarm (期望 200) ===")
cmd = (
    f"curl -s -X POST '{BASE_URL}/api/home_safety/callback/alarm' "
    "-H 'Content-Type: application/json' "
    """-d '{"dataType":"__precheck__","msgId":"smoke-001","param":{}}'"""
)
_, o, _ = c.exec_command(cmd, timeout=30); print(o.read().decode("utf-8","replace"))

print("=== smoke admin-web home (期望 200) ===")
cmd = f"curl -s -o /dev/null -w '%{{http_code}}' '{BASE_URL}/admin/home-safety'"
_, o, _ = c.exec_command(cmd, timeout=30); print("HTTP", o.read().decode().strip())

c.close()
print("DONE")
