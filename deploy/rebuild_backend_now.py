"""重建 backend 镜像并重启 backend 容器，应用新代码。"""
import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(c, cmd, timeout=900):
    print(f"\n$ {cmd[:200]}")
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    code = so.channel.recv_exit_status()
    if out: print(out[-2000:])
    if err: print("[err]", err[-1000:])
    print(f"[exit {code}]")
    return code


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)

run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -30", timeout=900)
run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend 2>&1 | tail -20", timeout=180)
time.sleep(15)
run(c, "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -n '@router.get' /app/app/api/products.py")
run(c, "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -n '_build_logo_url' /app/app/api/admin.py")
run(c, "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c '_migrate_product_categories_hierarchy' /app/app/main.py")
print("\n=== 验证接口 ===")
import urllib.request, ssl
ctx = ssl.create_default_context()
base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
for p in ["/api/products/hot-recommendations?limit=6", "/api/products/categories", "/api/settings/logo"]:
    try:
        with urllib.request.urlopen(base + p, timeout=15, context=ctx) as r:
            body = r.read().decode("utf-8", "replace")[:200]
            print(f"  {r.status}  {p}  -> {body}")
    except Exception as e:
        print(f"  ERR {p}  -> {e}")
c.close()
