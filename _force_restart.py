import paramiko, time
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE = f"/home/ubuntu/{DEPLOY_ID}"

cmds = [
    # 检查上传文件是否包含新路径
    f"grep -n 'api/home_safety/callback' {REMOTE}/backend/app/api/home_safety_v1.py | head -5",
    # 拷贝到容器内确保正确
    f"docker cp {REMOTE}/backend/app/api/home_safety_v1.py {DEPLOY_ID}-backend:/app/app/api/home_safety_v1.py",
    f"docker exec {DEPLOY_ID}-backend find /app -name '__pycache__' -path '*home_safety*' -exec rm -rf {{}} + 2>/dev/null || true",
    f"docker compose -f {REMOTE}/docker-compose.yml restart backend",
]
for cmd in cmds:
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("[err]", err[:500])

time.sleep(8)
# 验证
cmd = (
    f"docker exec {DEPLOY_ID}-backend python -c \""
    "from app.main import app; import json; "
    "print(json.dumps([r.path for r in app.routes if 'home_safety' in str(getattr(r,'path',''))], ensure_ascii=False))\""
)
print(f"$ {cmd}")
_, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode("utf-8", errors="replace"))
c.close()
