"""[2026-04-25] 商家 PC 后台登录 401 Bug 修复 - 端到端验证脚本。

流程：
1. 在服务器侧（容器内）直接用 DB 创建/启用一个商家账号，确保具备
   AccountIdentity(merchant_owner) + MerchantStoreMembership 的完整链路。
2. 用该账号调用 /api/merchant/auth/login 拿 token。
3. 立即带 token 调 /api/merchant/v1/dashboard/metrics，断言：
   - token 解码未抛 JWTClaimsError（Bug 修复前本步骤会返回 401 "无效的认证凭证"）
   - 接口返回 200 或 3xx，且响应体不是 {"detail":"无效的认证凭证"}
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
BACKEND_CT = f"{DEPLOY_ID}-backend"

TEST_PHONE = "13900000425"
TEST_PASSWORD = "Test@2026!"


SETUP_SCRIPT = f'''
import asyncio
import sys
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.models import (
    User, AccountIdentity, IdentityType,
    MerchantProfile, MerchantStore, MerchantStoreMembership, MerchantMemberRole,
)


async def ensure_test_merchant():
    async with async_session() as db:
        res = await db.execute(select(User).where(User.phone == "{TEST_PHONE}"))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                phone="{TEST_PHONE}",
                nickname="PC-JWT-TEST",
                password_hash=get_password_hash("{TEST_PASSWORD}"),
                status="active",
            )
            db.add(user)
            await db.flush()
        else:
            user.password_hash = get_password_hash("{TEST_PASSWORD}")
            user.status = "active"
            await db.flush()

        # 身份表：merchant_owner
        res = await db.execute(
            select(AccountIdentity).where(
                AccountIdentity.user_id == user.id,
                AccountIdentity.identity_type == IdentityType.merchant_owner,
            )
        )
        identity = res.scalar_one_or_none()
        if not identity:
            db.add(AccountIdentity(
                user_id=user.id,
                identity_type=IdentityType.merchant_owner,
                status="active",
            ))
            await db.flush()
        else:
            identity.status = "active"
            await db.flush()

        # 商家档案
        res = await db.execute(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
        profile = res.scalar_one_or_none()
        if not profile:
            profile = MerchantProfile(
                user_id=user.id,
                nickname="PC登录验证商家",
            )
            db.add(profile)
            await db.flush()

        # 门店（通过 membership 关联用户与门店；门店无 merchant_id 外键）
        res = await db.execute(
            select(MerchantStore).where(MerchantStore.store_code == "PCJWT001")
        )
        store = res.scalar_one_or_none()
        if not store:
            store = MerchantStore(
                store_name="PC登录验证门店",
                store_code="PCJWT001",
                contact_phone="{TEST_PHONE}",
                status="active",
            )
            db.add(store)
            await db.flush()

        # 成员关系
        res = await db.execute(
            select(MerchantStoreMembership).where(
                MerchantStoreMembership.user_id == user.id,
                MerchantStoreMembership.store_id == store.id,
            )
        )
        ms = res.scalar_one_or_none()
        if not ms:
            db.add(MerchantStoreMembership(
                user_id=user.id,
                store_id=store.id,
                member_role=MerchantMemberRole.owner,
                status="active",
            ))
        else:
            ms.status = "active"

        await db.commit()
        print("ready user_id=", user.id, " store_id=", store.id)


asyncio.run(ensure_test_merchant())
'''


def _ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return c


def _run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(f"$ {cmd}")
    if out.strip():
        print(out[:3000])
    if err.strip():
        print("stderr:", err[:1500])
    print(f"exit={code}\n")
    return code, out, err


def main() -> int:
    c = _ssh()
    try:
        print("== 1) 准备商家测试账号（容器内 Python 脚本）==")
        remote_script = f"/tmp/setup_merchant_jwt_test_{int(time.time())}.py"
        sftp = c.open_sftp()
        with sftp.open(remote_script, "w") as f:
            f.write(SETUP_SCRIPT)
        sftp.close()
        _run(c, f"docker cp {remote_script} {BACKEND_CT}:/tmp/setup.py", timeout=30)
        code, out, err = _run(
            c,
            f"docker exec {BACKEND_CT} python /tmp/setup.py 2>&1",
            timeout=60,
        )
        if code != 0 or "ready user_id=" not in out:
            print("[FAIL] 测试账号准备失败")
            return 2

        print("== 2) 调用 PC 登录接口 ==")
        login_payload = json.dumps({"phone": TEST_PHONE, "password": TEST_PASSWORD})
        code, out, err = _run(
            c,
            f"curl -sk -o /tmp/login.json -w 'code=%{{http_code}}\\n' "
            f"-H 'Content-Type: application/json' -d '{login_payload}' "
            f"{BASE_URL}/api/merchant/auth/login && cat /tmp/login.json && echo",
            timeout=30,
        )
        if "code=200" not in out:
            print("[FAIL] 登录未返回 200：", out)
            return 3

        # 提取 access_token
        _, body_out, _ = _run(c, "cat /tmp/login.json", timeout=10)
        try:
            body = json.loads(body_out.strip())
        except json.JSONDecodeError:
            print("[FAIL] 登录响应体不是合法 JSON")
            return 4
        token = body.get("access_token")
        if not token:
            print("[FAIL] 登录响应缺少 access_token：", body)
            return 5
        print(f"[ok] 拿到 token，长度={len(token)}")

        print("== 3) 用 token 调用 dashboard 接口（核心回归点）==")
        code, out, err = _run(
            c,
            f"curl -sk -o /tmp/dash.json -w 'code=%{{http_code}}\\n' "
            f"-H 'Authorization: Bearer {token}' "
            f"{BASE_URL}/api/merchant/v1/dashboard/metrics && cat /tmp/dash.json && echo",
            timeout=30,
        )
        if "code=200" not in out:
            print("[FAIL] dashboard 接口未返回 200，可能仍有 401：", out)
            return 6
        if "无效的认证凭证" in out:
            print("[FAIL] dashboard 接口仍报 '无效的认证凭证'（Bug 未修复）：", out)
            return 7

        print("[PASS] 商家 PC 后台登录 401 Bug 已修复：登录→dashboard 全链路鉴权通过。")

        print("== 4) 负面用例：短信验证码 8888 路径 ==")
        sms_payload = json.dumps({"phone": TEST_PHONE, "sms_code": "8888"})
        code, out, err = _run(
            c,
            f"curl -sk -o /tmp/login_sms.json -w 'code=%{{http_code}}\\n' "
            f"-H 'Content-Type: application/json' -d '{sms_payload}' "
            f"{BASE_URL}/api/merchant/auth/login && cat /tmp/login_sms.json && echo",
            timeout=30,
        )
        if "code=200" not in out:
            print("[WARN] 短信万能码登录非 200（但不是本次核心回归点）")

        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
