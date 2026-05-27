"""[PRD-GUARDIAN-V1.3.1 2026-05-27] v1.3.1 远程 API smoke 测试

通过登录 → 调用 family/list → 检查返回字段是否包含 v1.3.1 新字段。
"""

import json
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh_connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return c


def run(c, cmd, timeout=120):
    print(f"$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print(f"[stderr] {err[:500]}")
    return out, err


def main():
    print("=" * 60)
    print("[v1.3.1 SMOKE TEST] 守护人体系 v1.3.1 远程 smoke")
    print("=" * 60)

    client = ssh_connect()

    # 1) 在容器内安装 pytest 并运行单元测试（如果可能）
    print("\n[T1] 容器内 pytest 测试（如果 pytest 已安装）")
    out, _ = run(
        client,
        f"cd {REMOTE_BASE} && docker compose exec -T backend "
        f"sh -c 'pip install pytest pytest-asyncio httpx 2>/dev/null | tail -3 && "
        f"python -m pytest tests/test_guardian_system_v131.py -v 2>&1 | tail -80'",
        timeout=600,
    )

    # 2) 直接在容器内 Python 调用接口测试（无须登录，仅检查模型/导入）
    print("\n[T2] 直接验证后端代码加载 v1.3.1 字段定义")
    out, _ = run(
        client,
        f"cd {REMOTE_BASE} && docker compose exec -T backend python -c \""
        "from app.api.guardian_system_v13 import FamilyListItemV13, _LIFECYCLE_DISPLAY_LABEL, _OCCUPY_QUOTA_LIFECYCLES;"
        "fields = FamilyListItemV13.model_fields.keys();"
        "assert 'bind_status' in fields, 'bind_status missing';"
        "assert 'display_substatus_label' in fields, 'display_substatus_label missing';"
        "assert 'is_orphan' in fields, 'is_orphan missing';"
        "assert 'occupies_quota' in fields, 'occupies_quota missing';"
        "assert _LIFECYCLE_DISPLAY_LABEL['accepted'] == '建立于';"
        "assert _LIFECYCLE_DISPLAY_LABEL['rejected'] == '暂未响应';"
        "print('OK v131 fields:', list(fields));"
        "print('OK display labels:', _LIFECYCLE_DISPLAY_LABEL);"
        "print('OK occupy quota lifecycles:', _OCCUPY_QUOTA_LIFECYCLES)\"",
        timeout=60,
    )

    # 3) 检查 family_management.py 配额改造
    print("\n[T3] 验证 family_management.py 已动态读取配额")
    out, _ = run(
        client,
        f"grep -n 'dynamic_max\\|_get_max_guardians' {REMOTE_BASE}/backend/app/api/family_management.py | head -10",
    )

    # 4) HTTP 接口 smoke：未登录调用应 401
    print("\n[T4] HTTP smoke: 关键路由可达")
    run(client, f"curl -s -o /dev/null -w 'family/list 401 -> %{{http_code}}\\n' {BASE_URL}/api/guardian/v13/family/list")
    run(client, f"curl -s -o /dev/null -w 'h5/i-guard -> %{{http_code}}\\n' {BASE_URL}/h5/health-profile/i-guard")
    run(client, f"curl -s -o /dev/null -w 'h5/v13 redirect -> %{{http_code}}\\n' {BASE_URL}/h5/health-profile/v13")

    # 5) 注册一个新用户，登录获取 token，然后调用 family/list 验证字段
    print("\n[T5] 端到端：注册 → 登录 → 调用 family/list 验证返回字段")
    phone = f"139{int(time.time()) % 100000000:08d}"
    register_cmd = (
        f"curl -s -X POST {BASE_URL}/api/auth/register "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"phone\":\"{phone}\",\"password\":\"p123456\",\"nickname\":\"v131测试\"}}'"
    )
    out, _ = run(client, register_cmd)
    login_cmd = (
        f"curl -s -X POST {BASE_URL}/api/auth/login "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"phone\":\"{phone}\",\"password\":\"p123456\"}}'"
    )
    out, _ = run(client, login_cmd)
    # 提取 token
    token = None
    try:
        data = json.loads(out)
        token = data.get("access_token")
    except Exception:
        for line in out.splitlines():
            if "access_token" in line:
                print("login output:", line[:300])
                break
    if not token:
        print("[WARN] 无法获取 token，跳过 T5 末尾验证")
        client.close()
        return

    print(f"[T5] 成功登录，token 长度 {len(token)}")
    list_cmd = (
        f"curl -s {BASE_URL}/api/guardian/v13/family/list "
        f"-H 'Authorization: Bearer {token}'"
    )
    out, _ = run(client, list_cmd)
    try:
        data = json.loads(out)
        assert "bound_count" in data, "bound_count missing"
        assert "unbound_count" in data, "unbound_count missing"
        assert "quota_used" in data, "quota_used missing"
        assert "max_guardians" in data, "max_guardians missing"
        # 没有任何家人时 max_guardians 应该来自 free_member_quota
        print(f"[T5] family/list 返回字段验证通过：")
        print(f"      bound_count={data['bound_count']}, unbound_count={data['unbound_count']},")
        print(f"      quota_used={data['quota_used']}, max_guardians={data['max_guardians']},")
        print(f"      can_invite_count={data['can_invite_count']}")
        print("[T5] OK v1.3.1 接口字段完整")
    except AssertionError as e:
        print(f"[T5 FAIL] {e}")
        print("响应原文：", out[:1000])
    except Exception as e:
        print(f"[T5 ERROR] {e}")
        print("响应原文：", out[:1000])

    client.close()
    print("\n=== v1.3.1 SMOKE 完成 ===")


if __name__ == "__main__":
    main()
