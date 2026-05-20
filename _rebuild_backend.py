import paramiko, time, sys
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=120)
def sh(c,t=900):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace'),so.channel.recv_exit_status()

# 先看 backend 是否有 hot reload 还是 prod build
o,_,_=sh(f"docker inspect {DEPLOY_ID}-backend --format '{{{{.Config.Cmd}}}} | {{{{.Config.Entrypoint}}}}'")
print("backend cmd:",o.strip())
o,_,_=sh(f"docker exec {DEPLOY_ID}-backend ls /app/app/api/seed_import.py 2>&1")
print("seed_import.py 是否存在:",o.strip()[:200])
o,_,_=sh(f"docker exec {DEPLOY_ID}-backend grep -c 'seed_import' /app/app/main.py")
print("main.py 引用 seed_import 次数:",o.strip())

# 路由是否注册
o,_,_=sh(f"docker exec {DEPLOY_ID}-backend python -c \"from app.main import app; print([r.path for r in app.routes if 'seed' in r.path])\"")
print("[backend] 注册的 seed 路由:",o.strip()[:500])

# 直接看 backend 启动日志
o,_,_=sh(f"docker logs --tail 30 {DEPLOY_ID}-backend 2>&1 | tail -25")
print("--- backend logs ---");print(o)

# 通过容器内 curl 验证 8000
o,_,_=sh(f"docker exec {DEPLOY_ID}-backend sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\" http://127.0.0.1:8000/api/admin/seed-packs'")
print("backend 容器内 /api/admin/seed-packs:",o.strip())

# 通过 gateway 测一下 /api/openapi.json paths
o,_,_=sh(f"curl -s --max-time 15 '{BASE}/api/openapi.json' | python3 -c 'import sys,json;d=json.load(sys.stdin);print([p for p in d.get(\"paths\",{{}}).keys() if \"seed\" in p])'")
print("通过 gateway openapi seed 路径:",o.strip())
cli.close()
