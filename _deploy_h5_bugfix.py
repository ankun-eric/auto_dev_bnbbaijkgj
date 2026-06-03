"""[BUGFIX archive-list 404 2026-05-30] 重新构建 h5 镜像（同步前端兜底改动）"""
import os, tarfile, time
from _ssh_helper import run, put_file, DEPLOY_ID

REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_H5 = os.path.abspath("h5-web")
TAR_LOCAL = os.path.abspath("_bugfix_h5_archive.tar.gz")

EXCLUDE_DIRS = {"node_modules", ".next", "out", "dist", "__pycache__", ".pytest_cache", ".turbo", ".cache"}
EXCLUDE_SUFFIX = (".log",)

def _flt(ti):
    name = os.path.basename(ti.name)
    if name in EXCLUDE_DIRS:
        return None
    if name.endswith(EXCLUDE_SUFFIX):
        return None
    return ti

print("[1] Pack h5-web ->", TAR_LOCAL)
with tarfile.open(TAR_LOCAL, "w:gz") as tf:
    tf.add(LOCAL_H5, arcname="h5-web", filter=_flt)
print("    size:", os.path.getsize(TAR_LOCAL))

REMOTE_TAR = f"{REMOTE_BASE}/_bugfix_h5_archive.tar.gz"
print("[2] Upload ->", REMOTE_TAR)
put_file(TAR_LOCAL, REMOTE_TAR)

ts = time.strftime("%Y%m%d_%H%M%S")
print("[3] Backup + extract")
script = f"""
set -e
cd {REMOTE_BASE}
if [ -d h5-web.bak_{ts} ]; then rm -rf h5-web.bak_{ts}; fi
mv h5-web h5-web.bak_{ts} || true
tar -xzf _bugfix_h5_archive.tar.gz
ls h5-web/src/app/health-profile/archive-list/page.tsx
grep -c '档案数据接口暂不可用' h5-web/src/app/health-profile/archive-list/page.tsx
echo OK
"""
rc, out, err = run(script, timeout=120)
print(out)
if err: print("ERR:", err)

print("[4] docker compose build h5-web (this may take a few minutes)")
rc, out, err = run(
    f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -30 && echo BUILD_DONE && docker compose up -d h5-web 2>&1",
    timeout=900,
)
print(out)
if err: print("ERR:", err)
print("RC=", rc)

print("[5] Verify")
time.sleep(5)
verify = [
    f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}-h5",
    f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile/archive-list'",
]
for c in verify:
    print("---"); print("CMD:", c[:160])
    rc, out, err = run(c, timeout=60)
    print(out)
    if err: print("ERR:", err)
    print("RC=", rc)
