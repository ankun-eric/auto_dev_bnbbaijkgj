import paramiko

DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Bangbang987', timeout=30)

cmds = [
    f"cp {REMOTE_DIR}/gateway-routes.conf /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf",
    "docker exec gateway-nginx nginx -t",
    "docker exec gateway-nginx nginx -s reload",
    f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health",
    f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/",
    f"curl -s -o /dev/null -w '%{{http_code}}' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/",
]
for cmd in cmds:
    print(f'\n>>> {cmd}')
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip())
    if err.strip(): print(f"[STDERR] {err.strip()}")
    print(f"[EXIT] {code}")

c.close()
print("\n=== Gateway update complete ===")
