"""[BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30]
H5 端档案列表/会员中心 6 项 UI 优化部署脚本。
- 不改后端，仅打包 h5-web
- 上传 -> 解压 -> docker compose build h5 -> up -d -> 烟测
"""
import os, tarfile, time
from _ssh_helper import run, put_file, DEPLOY_ID

REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_H5 = os.path.abspath("h5-web")
TAR_LOCAL = os.path.abspath("_archive_list_ui_optim_h5.tar.gz")

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

REMOTE_TAR = f"{REMOTE_BASE}/_archive_list_ui_optim_h5.tar.gz"
print("[2] Upload ->", REMOTE_TAR)
put_file(TAR_LOCAL, REMOTE_TAR)

ts = time.strftime("%Y%m%d_%H%M%S")
print("[3] Backup + extract")
script = f"""
set -e
cd {REMOTE_BASE}
if [ -d h5-web.bak_{ts} ]; then rm -rf h5-web.bak_{ts}; fi
mv h5-web h5-web.bak_{ts} || true
tar -xzf _archive_list_ui_optim_h5.tar.gz
echo '--- key file checks ---'
grep -n 'BUG-FIX-ARCHIVE-LIST-UI-OPTIM' h5-web/src/app/health-profile/archive-list/page.tsx | head -5
grep -n 'BUG-FIX-ARCHIVE-LIST-UI-OPTIM' h5-web/src/app/health-profile/page.tsx | head -3
grep -n 'BUG-FIX-ARCHIVE-LIST-UI-OPTIM' h5-web/src/app/member-center/components/InviteFamilyCard.tsx | head -3
echo OK
"""
rc, out, err = run(script, timeout=180)
print(out)
if err:
    print("ERR:", err)

print("[4] docker compose build h5-web (may take 3-6 minutes)")
rc, out, err = run(
    f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -40 && echo BUILD_DONE && docker compose up -d h5-web 2>&1 | tail -10",
    timeout=900,
)
print(out)
if err:
    print("ERR:", err)
print("RC=", rc)

print("[5] Verify (wait 8s for container ready)")
time.sleep(8)
verify = [
    f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}-h5",
    f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/'",
    f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile'",
    f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile/archive-list'",
    f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/member-center'",
]
for c in verify:
    print("---")
    print("CMD:", c[:160])
    rc, out, err = run(c, timeout=60)
    print(out.strip())
    if err:
        print("ERR:", err.strip())
print("DONE")
