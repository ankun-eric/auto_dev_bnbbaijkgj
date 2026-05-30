# -*- coding: utf-8 -*-
"""
[PRD-INVITE-FAMILY-CARD-V1.1 2026-05-30] 服务器侧非UI 自动化烟雾测试

验证项（基于服务端渲染 HTML / 构建产物 JS）：
  T1. 会员中心位页面可达 (HTTP 200)
  T2. 健康档案-档案列表页可达 (HTTP 200)
  T3. h5 容器内 v1.1 代码标志存在（card_location/profile_list_top/target_action/create_profile）
  T4. 健康档案位接入新卡片标志存在（InviteFamilyCard 引入 + cardLocation='profile_list_top'）
  T5. 主标题单行 CSS（white-space:nowrap / text-overflow:ellipsis）存在于源代码
  T6. v1.0 行为零退化：会员中心位 cardLocation='member_center' 标志存在
  T7. v1.0 单元测试（39用例）+ v1.1 单元测试（29用例）全部通过

退出码：0 全过，非 0 有失败用例（监控器可识别）
"""
import json
import subprocess
import sys
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
SSH_HOST = "ubuntu@newbb.test.bangbangvip.com"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-h5"
REMOTE_ROOT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

passed = 0
failed = 0


def ok(name):
    global passed
    passed += 1
    print(f"  PASS  {name}")


def ng(name, reason):
    global failed
    failed += 1
    print(f"  FAIL  {name}\n        reason: {reason}")


def http_get(path, timeout=20):
    url = f"{BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smoke-v11"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, str(e)


def ssh_run(cmd, timeout=30):
    try:
        proc = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return -1, "", str(e)


# ───────────── T1：会员中心页面可达 ─────────────
print("[T1] 会员中心页面可达性")
code, body = http_get("/member-center")
if code == 200:
    ok("/member-center 返回 200")
else:
    ng("/member-center 返回 200", f"HTTP {code}")

# ───────────── T2：健康档案-档案列表页可达 ─────────────
print("\n[T2] 健康档案-档案列表页可达性")
code2, body2 = http_get("/health-profile/archive-list")
if code2 == 200:
    ok("/health-profile/archive-list 返回 200")
else:
    ng("/health-profile/archive-list 返回 200", f"HTTP {code2}")

# ───────────── T3：容器内源码包含 v1.1 关键标志 ─────────────
print("\n[T3] v1.1 关键代码标志（card_location / target_action）")

# Next.js 把源代码编进 standalone server，但 chunk 可能 minify。
# 这里通过宿主机服务器项目目录扫描源码（更稳）：
cards_file = f"{REMOTE_ROOT}/h5-web/src/app/member-center/components/InviteFamilyCard.tsx"
rc, out, err = ssh_run(f"grep -c 'card_location' {cards_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("InviteFamilyCard.tsx 含 card_location 字段")
else:
    ng("InviteFamilyCard.tsx 含 card_location 字段", f"grep miss: rc={rc} out={out} err={err}")

rc, out, err = ssh_run(f"grep -c 'target_action' {cards_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("InviteFamilyCard.tsx 含 target_action 字段")
else:
    ng("InviteFamilyCard.tsx 含 target_action 字段", f"grep miss: rc={rc} out={out}")

rc, out, err = ssh_run(f"grep -c 'profile_list_top' {cards_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("InviteFamilyCard.tsx 含 profile_list_top 枚举")
else:
    ng("InviteFamilyCard.tsx 含 profile_list_top 枚举", f"grep miss: rc={rc} out={out}")

rc, out, err = ssh_run(f"grep -c 'create_profile' {cards_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("InviteFamilyCard.tsx 含 create_profile 枚举")
else:
    ng("InviteFamilyCard.tsx 含 create_profile 枚举", f"grep miss: rc={rc} out={out}")

# ───────────── T4：健康档案位接入新卡片 ─────────────
print("\n[T4] 健康档案位接入新卡片 + 概览块替换")
archive_file = f"{REMOTE_ROOT}/h5-web/src/app/health-profile/archive-list/page.tsx"
rc, out, err = ssh_run(f"grep -c 'InviteFamilyCard' {archive_file}")
if rc == 0 and int(out.strip() or 0) >= 2:  # import + 使用
    ok("archive-list/page.tsx 引入并使用 InviteFamilyCard")
else:
    ng("archive-list/page.tsx 引入并使用 InviteFamilyCard", f"grep count={out.strip()}")

rc, out, err = ssh_run(f"grep -c \"cardLocation='profile_list_top'\" {archive_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("archive-list 卡片传入 cardLocation='profile_list_top'")
else:
    ng("archive-list 卡片传入 cardLocation='profile_list_top'", f"grep miss out={out}")

# 验证旧概览块已被替换（不再存在 data-testid='new-member-btn' 的"+ 新增"按钮源码块）
rc, out, err = ssh_run(f"grep -c \"new-member-btn\" {archive_file}")
new_member_count = int(out.strip() or 0)
if new_member_count == 0:
    ok("archive-list 已移除原'+新增'黄色按钮（new-member-btn data-testid）")
else:
    ng("archive-list 已移除原'+新增'黄色按钮", f"new-member-btn 残留 count={new_member_count}")

# 验证新建抽屉本体仍保留（BR-10：复用线上抽屉）
rc, out, err = ssh_run(f"grep -c 'NewMemberDrawer' {archive_file}")
if rc == 0 and int(out.strip() or 0) >= 2:
    ok("archive-list 新建家人档案抽屉组件仍保留（BR-10 复用）")
else:
    ng("archive-list 新建家人档案抽屉组件仍保留", f"grep count={out.strip()}")

# ───────────── T5：主标题单行 CSS ─────────────
print("\n[T5] 主标题强制单行 CSS（AC-20/AC-21）")
rc, out, err = ssh_run(f"grep -c 'whiteSpace.*nowrap' {cards_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("InviteFamilyCard 主标题 whiteSpace:nowrap")
else:
    ng("InviteFamilyCard 主标题 whiteSpace:nowrap", f"grep miss out={out}")

rc, out, err = ssh_run(f"grep -c 'textOverflow.*ellipsis' {cards_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("InviteFamilyCard 主标题 textOverflow:ellipsis")
else:
    ng("InviteFamilyCard 主标题 textOverflow:ellipsis", f"grep miss out={out}")

rc, out, err = ssh_run(f"grep -c 'titleFontSize' {cards_file}")
if rc == 0 and int(out.strip() or 0) >= 3:
    ok("InviteFamilyCard 主标题响应式字号（15/16pt 兜底）")
else:
    ng("InviteFamilyCard 主标题响应式字号", f"grep count={out.strip()}")

# ───────────── T6：v1.0 行为零退化 ─────────────
print("\n[T6] v1.0 会员中心位行为零退化")
member_file = f"{REMOTE_ROOT}/h5-web/src/app/member-center/page.tsx"
rc, out, err = ssh_run(f"grep -c \"cardLocation='member_center'\" {member_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("member-center 卡片传入 cardLocation='member_center'")
else:
    ng("member-center 卡片传入 cardLocation='member_center'", f"grep miss out={out}")

rc, out, err = ssh_run(f"grep -c '/health-profile/my-guardians/invite' {member_file}")
if rc == 0 and int(out.strip() or 0) > 0:
    ok("member-center 主按钮仍跳邀请流程页（AC-19）")
else:
    ng("member-center 主按钮仍跳邀请流程页", f"grep miss out={out}")

# ───────────── T7：服务器容器内执行单元测试 ─────────────
print("\n[T7] 服务器 docker 容器内执行 v1.0 + v1.1 单元测试")
v10_test = f"{REMOTE_ROOT}/h5-web/src/lib/__tests__/run_invite_card_test.mjs"
v11_test = f"{REMOTE_ROOT}/h5-web/src/lib/__tests__/run_invite_card_v11_test.mjs"

# Next.js standalone 容器有 node，但工作目录不同。先 cat 测试文件到容器内执行：
rc, out, err = ssh_run(
    f"cat {v10_test} | docker exec -i {CONTAINER} node -e \"$(cat)\" 2>&1 || "
    f"docker cp {v10_test} {CONTAINER}:/tmp/_v10_test.mjs && "
    f"docker exec {CONTAINER} node /tmp/_v10_test.mjs",
    timeout=120,
)
combined = (out or "") + (err or "")
if "39 passed, 0 failed" in combined:
    ok("v1.0 单元测试 39 用例全部通过（零退化）")
else:
    ng("v1.0 单元测试 39 用例全部通过", f"unexpected output: {combined[-500:]}")

rc, out, err = ssh_run(
    f"docker cp {v11_test} {CONTAINER}:/tmp/_v11_test.mjs && "
    f"docker exec {CONTAINER} node /tmp/_v11_test.mjs",
    timeout=120,
)
combined = (out or "") + (err or "")
if "passed=29 failed=0" in combined:
    ok("v1.1 单元测试 29 用例全部通过（AC-16~23 + RC-05~08）")
else:
    ng("v1.1 单元测试 29 用例全部通过", f"unexpected output: {combined[-500:]}")

# ───────────── 汇总 ─────────────
print("\n============================================")
print(f"[PRD-INVITE-FAMILY-CARD-V1.1 服务器烟雾测试] passed={passed}  failed={failed}")
print("============================================")
sys.exit(0 if failed == 0 else 1)
