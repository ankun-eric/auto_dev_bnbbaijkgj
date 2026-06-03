"""[PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 会员中心『付费态蓝紫主题』部署脚本

变更范围：
- backend/app/api/member_center_v2.py  新增 /api/member/quota-usage 端点
- backend/tests/test_member_purple_theme_v1_20260530.py  新增 8 个 pytest
- h5-web/src/app/member-center/page.tsx  重写主页（蓝紫渐变 Banner / 配额卡 / 状态条 / CTA）
- h5-web/src/app/member-center/theme-purple.ts  纯函数视觉资产
- h5-web/src/app/member-center/components/MonthlyQuotaCard.tsx  新增「本月配额」卡组件
- h5-web/src/app/member-center/components/BenefitsCompareTable.tsx  对比表色系切换为蓝紫
- h5-web/src/lib/__tests__/run_member_purple_theme_test.mjs  新增 49 个前端纯函数用例

部署流程：
1) tar 打包 h5-web + backend
2) SFTP 上传
3) 远程解压（备份旧目录）
4) 后端 docker cp + restart（仅替换 member_center_v2.py + 新测试）
5) h5 docker compose build + up -d
6) HTTPS smoke test + 远程 pytest
"""
import os
import tarfile
import time
from _ssh_helper import run, put_file, DEPLOY_ID

REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
TS = time.strftime("%Y%m%d_%H%M%S")

LOCAL_H5 = os.path.abspath("h5-web")
LOCAL_BE = os.path.abspath("backend")
TAR_H5 = os.path.abspath("_member_purple_h5.tar.gz")
TAR_BE = os.path.abspath("_member_purple_be.tar.gz")

EXCLUDE_DIRS = {"node_modules", ".next", "out", "dist", "__pycache__", ".pytest_cache", ".turbo", ".cache", ".venv", "venv"}
EXCLUDE_SUFFIX = (".log", ".pyc")


def _flt(ti):
    name = os.path.basename(ti.name)
    if name in EXCLUDE_DIRS:
        return None
    if name.endswith(EXCLUDE_SUFFIX):
        return None
    return ti


# ─── 1) 打包 ───
print(f"[1] Pack h5-web -> {TAR_H5}")
with tarfile.open(TAR_H5, "w:gz") as tf:
    tf.add(LOCAL_H5, arcname="h5-web", filter=_flt)
print(f"    size={os.path.getsize(TAR_H5)}")

print(f"[1] Pack backend -> {TAR_BE}")
with tarfile.open(TAR_BE, "w:gz") as tf:
    tf.add(LOCAL_BE, arcname="backend", filter=_flt)
print(f"    size={os.path.getsize(TAR_BE)}")

# ─── 2) 上传 ───
REMOTE_TAR_H5 = f"{REMOTE_BASE}/_member_purple_h5.tar.gz"
REMOTE_TAR_BE = f"{REMOTE_BASE}/_member_purple_be.tar.gz"
print(f"[2] Upload h5 -> {REMOTE_TAR_H5}")
put_file(TAR_H5, REMOTE_TAR_H5)
print(f"[2] Upload be -> {REMOTE_TAR_BE}")
put_file(TAR_BE, REMOTE_TAR_BE)

# ─── 3) 解压 + 校验关键文件 ───
print("[3] Extract on server")
script = f"""
set -e
cd {REMOTE_BASE}
[ -d h5-web.bak_{TS} ] && rm -rf h5-web.bak_{TS} || true
mv h5-web h5-web.bak_{TS} || true
tar -xzf _member_purple_h5.tar.gz
[ -d backend.bak_{TS} ] && rm -rf backend.bak_{TS} || true
mv backend backend.bak_{TS} || true
tar -xzf _member_purple_be.tar.gz
echo '--- key file checks ---'
grep -n 'PRD-MEMBER-PURPLE-THEME-V1' h5-web/src/app/member-center/page.tsx | head -3
grep -n 'PRD-MEMBER-PURPLE-THEME-V1' h5-web/src/app/member-center/theme-purple.ts | head -3
grep -n 'PRD-MEMBER-PURPLE-THEME-V1' h5-web/src/app/member-center/components/MonthlyQuotaCard.tsx | head -3
grep -n 'PRD-MEMBER-PURPLE-THEME-V1' h5-web/src/lib/__tests__/run_member_purple_theme_test.mjs | head -3
grep -n 'PRD-MEMBER-PURPLE-THEME-V1' backend/app/api/member_center_v2.py | head -3
grep -n 'quota-usage' backend/app/api/member_center_v2.py | head -3
echo OK
"""
rc, out, err = run(script, timeout=180)
print(out)
if err.strip():
    print("ERR:", err)

# ─── 4) 后端：docker cp 关键文件 + 测试文件 + restart ───
print("[4] Backend hot-replace (docker cp + restart)")
be_script = f"""
set -e
cd {REMOTE_BASE}
docker cp backend/app/api/member_center_v2.py {DEPLOY_ID}-backend:/app/app/api/member_center_v2.py
docker cp backend/tests/test_member_purple_theme_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/test_member_purple_theme_v1_20260530.py 2>/dev/null || \\
  docker exec {DEPLOY_ID}-backend mkdir -p /app/tests
docker cp backend/tests/test_member_purple_theme_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/test_member_purple_theme_v1_20260530.py
docker compose restart backend 2>&1 | tail -10
sleep 4
docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}-backend
"""
rc, out, err = run(be_script, timeout=180)
print(out)
if err.strip():
    print("ERR:", err)

# ─── 5) h5 build + up ───
print("[5] h5-web docker compose build + up (3-6 min)")
build_script = (
    f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -30 && echo BUILD_DONE && "
    f"docker compose up -d h5-web 2>&1 | tail -10"
)
rc, out, err = run(build_script, timeout=900)
print(out)
if err.strip():
    print("ERR:", err)
print(f"[5] RC={rc}")

# ─── 6) HTTPS smoke + 远程 pytest ───
print("[6] HTTPS smoke")
time.sleep(8)
URLS = [
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/",
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/member-center",
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile",
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health",
]
for u in URLS:
    rc, out, err = run(f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' '{u}'", timeout=30)
    print(f"  {u} -> {out.strip()}")

# 检查 H5 chunk 是否含主题关键字
print("[6] H5 chunk grep for purple-theme markers")
rc, out, err = run(
    f"docker exec {DEPLOY_ID}-h5 sh -lc \"grep -lr '5B6CFF\\|paid_normal\\|MonthlyQuotaCard' /app/.next 2>/dev/null | head -5\"",
    timeout=60,
)
print(out)

print("[6] Remote pytest (member purple theme)")
rc, out, err = run(
    f"docker exec {DEPLOY_ID}-backend sh -lc 'cd /app && python -m pytest tests/test_member_purple_theme_v1_20260530.py -v 2>&1 | tail -40'",
    timeout=180,
)
print(out)
if err.strip():
    print("ERR:", err)

# 回归：邀请家人 v1 + 邀请家人 v1.1 + 会员中心对齐测试
print("[6] Remote pytest (regression: invite_family_card + member_center_aligned)")
rc, out, err = run(
    f"docker exec {DEPLOY_ID}-backend sh -lc 'cd /app && python -m pytest "
    f"tests/test_invite_family_card_v1_20260530.py "
    f"tests/test_member_center_prd_v1_aligned.py "
    f"-v 2>&1 | tail -50'",
    timeout=240,
)
print(out)
if err.strip():
    print("ERR:", err)

# 前端：在 h5 容器中跑纯函数测试
print("[6] h5 unit tests (in-container)")
rc, out, err = run(
    f"docker exec {DEPLOY_ID}-h5 sh -lc 'cd /app && node /tmp/run_member_purple_theme_test.mjs 2>/dev/null || true'",
    timeout=30,
)
# h5 容器没有源码目录，复制后再跑
rc, out, err = run(
    f"docker cp h5-web/src/lib/__tests__/run_member_purple_theme_test.mjs {DEPLOY_ID}-h5:/tmp/run_member_purple_theme_test.mjs && "
    f"docker cp h5-web/src/lib/__tests__/run_invite_card_test.mjs {DEPLOY_ID}-h5:/tmp/run_invite_card_test.mjs && "
    f"docker cp h5-web/src/lib/__tests__/run_invite_card_v11_test.mjs {DEPLOY_ID}-h5:/tmp/run_invite_card_v11_test.mjs && "
    f"docker exec {DEPLOY_ID}-h5 sh -lc 'cd /tmp && node run_member_purple_theme_test.mjs && node run_invite_card_test.mjs && node run_invite_card_v11_test.mjs' 2>&1 | tail -40",
    timeout=120,
    get_pty=False,
)
# 上一行先 cd 到 REMOTE_BASE
rc2, out2, err2 = run(
    f"cd {REMOTE_BASE} && docker cp h5-web/src/lib/__tests__/run_member_purple_theme_test.mjs {DEPLOY_ID}-h5:/tmp/run_member_purple_theme_test.mjs && "
    f"docker exec {DEPLOY_ID}-h5 sh -lc 'cd /tmp && node run_member_purple_theme_test.mjs'",
    timeout=120,
)
print(out2)
if err2.strip():
    print("ERR:", err2)

print("DONE")
