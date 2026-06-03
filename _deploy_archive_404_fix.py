"""[BUGFIX archive-list 404 2026-05-30] 同步 backend 源码到远程并重新构建 backend 镜像 + 重启容器
关键文件：
- backend/app/api/family_member_v2.py
- backend/app/main.py
"""
import os, tarfile, time
from _ssh_helper import run, put_file, DEPLOY_ID

REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

# 1) 打包 backend（排除测试/缓存/数据/构建产物）
LOCAL_BACKEND = os.path.abspath("backend")
TAR_LOCAL = os.path.abspath("_bugfix_backend_archive.tar.gz")

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "node_modules", "dist", "build", ".tox", ".coverage"}
EXCLUDE_SUFFIX = (".pyc", ".pyo")

def _flt(ti):
    name = os.path.basename(ti.name)
    if name in EXCLUDE_DIRS:
        return None
    if name.endswith(EXCLUDE_SUFFIX):
        return None
    return ti

print("[1] Packing backend ->", TAR_LOCAL)
with tarfile.open(TAR_LOCAL, "w:gz") as tf:
    tf.add(LOCAL_BACKEND, arcname="backend", filter=_flt)
print("    size:", os.path.getsize(TAR_LOCAL))

# 2) 上传到服务器
REMOTE_TAR = f"{REMOTE_BASE}/_bugfix_backend_archive.tar.gz"
print("[2] Uploading -> ", REMOTE_TAR)
put_file(TAR_LOCAL, REMOTE_TAR)

# 3) 服务器解包覆盖（备份原 backend）
print("[3] Backup + extract")
ts = time.strftime("%Y%m%d_%H%M%S")
script = f"""
set -e
cd {REMOTE_BASE}
if [ -d backend.bak_{ts} ]; then rm -rf backend.bak_{ts}; fi
mv backend backend.bak_{ts} || true
tar -xzf _bugfix_backend_archive.tar.gz
ls -la backend/app/api/family_member_v2.py
grep -n 'family_member_v2' backend/app/main.py | head -5
echo OK
"""
rc, out, err = run(script, timeout=180)
print(out)
if err: print("ERR:", err)
print("RC=", rc)
if rc != 0:
    raise SystemExit(1)

# 4) 重建 backend 镜像并重启
print("[4] docker compose build & up")
rc, out, err = run(
    f"cd {REMOTE_BASE} && docker compose build backend 2>&1 | tail -60 && echo BUILD_DONE && docker compose up -d backend 2>&1",
    timeout=600,
)
print(out)
if err: print("ERR:", err)
print("RC=", rc)

# 5) 健康检查 + 路由验证
print("[5] Health & routes verify")
time.sleep(5)
verify_cmds = [
    f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}-backend",
    f"docker exec {DEPLOY_ID}-backend python -c \"from app.main import app; ps=[r.path for r in app.routes if hasattr(r,'path') and 'family/member' in r.path]; print('\\n'.join(ps))\" 2>&1 | tail -20",
    f"curl -s -o /tmp/r.txt -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/family/member/state/list' && head -c 300 /tmp/r.txt && echo",
]
for c in verify_cmds:
    print("---"); print("CMD:", c[:160])
    rc, out, err = run(c, timeout=60)
    print(out)
    if err: print("ERR:", err)
    print("RC=", rc)
