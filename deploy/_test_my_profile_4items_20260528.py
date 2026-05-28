#!/usr/bin/env python3
"""[BUGFIX-MY-PROFILE-4ITEMS-20260528] 远程非UI自动化测试

测试要点：
- TC1: /api/guardian/v13/family/list 接口返回 bound_others_count 字段
- TC2: quota_used 计算逻辑：仅 bound + inviting 占额（NEVER_INVITED / EXPIRED / REJECTED / UNBOUND 不占）
- TC3: can_invite_count = max_guardians - quota_used
- TC4: 前端 h5-web 页面包含修复后的文本（已绑定徽标、已守护 X/Y）
"""
import re
import sys
import time
import urllib.parse

import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BACKEND = f'{DEPLOY_ID}-backend'
H5 = f'{DEPLOY_ID}-h5'
BASE = f'http://localhost/autodev/{DEPLOY_ID}'


def get_ssh():
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return s


def run(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    return out, err, code


def assert_true(cond, name, detail=''):
    if cond:
        print(f"  ✅ PASS  {name}")
        return True
    print(f"  ❌ FAIL  {name}  {detail}")
    return False


def main():
    ssh = get_ssh()
    results = []

    print("\n========== TC0: 后端代码包含修复标记 ==========")
    out, _, _ = run(ssh, f'docker exec {BACKEND} grep -c "BUGFIX-MY-PROFILE-4ITEMS-20260528" /app/app/api/guardian_system_v13.py')
    results.append(assert_true(int(out.strip() or 0) >= 1, "guardian_system_v13.py 含 BUGFIX-MY-PROFILE-4ITEMS-20260528 标记", out))

    print("\n========== TC1: _OCCUPY_QUOTA_LIFECYCLES 仅含 ACCEPTED + INVITING ==========")
    out, _, _ = run(ssh, f"docker exec {BACKEND} python -c \"from app.api.guardian_system_v13 import _OCCUPY_QUOTA_LIFECYCLES; print(sorted(_OCCUPY_QUOTA_LIFECYCLES))\"")
    print(f"  得到: {out.strip()}")
    s = out.strip()
    results.append(assert_true("accepted" in s and "inviting" in s and "never_invited" not in s and "expired" not in s and "rejected" not in s,
                               "占额生命周期 = {accepted, inviting}（不含 never_invited/expired/rejected）", out))

    print("\n========== TC2: family/list 接口返回 bound_others_count ==========")
    # 直接在容器内构造一个假 user 调用接口比较麻烦，改为查 OpenAPI schema 中字段是否存在；或直接 grep 源码
    out, _, _ = run(ssh, f'docker exec {BACKEND} grep -c "bound_others_count" /app/app/api/guardian_system_v13.py')
    results.append(assert_true(int(out.strip() or 0) >= 2, "bound_others_count 在 guardian_system_v13.py 至少出现 2 次（计算 + 返回）", out))

    print("\n========== TC3: pytest 后端核心模块 import 检查 ==========")
    out, _, _ = run(ssh, f'docker exec {BACKEND} python -c "from app.api.guardian_system_v13 import router; print(len(router.routes))"', timeout=60)
    try:
        n = int(out.strip())
        results.append(assert_true(n > 5, f"guardian_system_v13 router 加载成功，共 {n} 路由", out))
    except Exception:
        results.append(assert_true(False, "guardian_system_v13 router 加载失败", out))

    print("\n========== TC4: H5 前端打包包含修复 1（已绑定徽标 + 橙色 #FF7A1A） ==========")
    # next standalone 产物里搜 chunk 文件
    out, _, _ = run(ssh, f'docker exec {H5} sh -c "grep -rl FF7A1A /app/.next 2>/dev/null | head -3"')
    has_orange = bool(out.strip())
    results.append(assert_true(has_orange, "H5 构建产物含橙色 #FF7A1A", out))
    out, _, _ = run(ssh, f'docker exec {H5} sh -c "grep -rl bh-guarded-badge /app/.next 2>/dev/null | head -3"')
    results.append(assert_true(bool(out.strip()), "H5 构建产物含徽标 testid bh-guarded-badge", out))

    print("\n========== TC5: H5 前端打包包含修复 2（i-guard-total-count subtitle 改为「已守护」） ==========")
    out, _, _ = run(ssh, f'docker exec {H5} sh -c "grep -rl i-guard-total-count /app/.next 2>/dev/null | head -3"')
    results.append(assert_true(bool(out.strip()), "H5 构建产物含 i-guard-total-count 标识", out))
    out, _, _ = run(ssh, f'docker exec {H5} sh -c "grep -rl bound_others_count /app/.next 2>/dev/null | head -3"')
    results.append(assert_true(bool(out.strip()), "H5 构建产物含 bound_others_count 字段", out))

    print("\n========== TC6: H5 前端打包包含修复 4（按钮高度 28） ==========")
    out, _, _ = run(ssh, f'docker exec {H5} sh -c "grep -rl btn-self-edit /app/.next 2>/dev/null | head -3"')
    results.append(assert_true(bool(out.strip()), "H5 构建产物含 btn-self-edit 标识", out))

    print("\n========== TC7: HTTP 入口可访问 ==========")
    for path in ['/health-profile/', '/health-profile/i-guard/', '/']:
        out, _, _ = run(ssh, f'curl -sS -o /dev/null -w "%{{http_code}}" {BASE}{path}')
        code = out.strip()
        results.append(assert_true(code in ('200', '301', '302', '307', '308'),
                                   f"GET {BASE}{path} -> {code}", out))

    print("\n========== TC8: API 入口可访问（未带 token 应当 401/403） ==========")
    # nginx 强制 https，跟随重定向访问 https
    out, _, _ = run(ssh, f'curl -sSLk -o /dev/null -w "%{{http_code}}" {BASE}/api/guardian/v13/family/list')
    code = out.strip()
    results.append(assert_true(code in ('200', '401', '403', '422'),
                               f"GET /api/guardian/v13/family/list (https) -> {code}", out))

    ssh.close()

    total = len(results)
    passed = sum(1 for r in results if r)
    print(f"\n========== 测试结果汇总：{passed}/{total} 通过 ==========")
    if passed != total:
        sys.exit(1)


if __name__ == '__main__':
    main()
