#!/usr/bin/env python3
"""验证修复 - 用实际存在的邀请码"""
import httpx
import asyncio
from jose import jwt as jose_jwt

DOMAIN = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
SECRET_KEY = "bini-health-secret-key-2026-very-secure"

async def test_api():
    # 用户18的 token
    token18 = jose_jwt.encode(
        {"sub": "18", "exp": 1781011403},
        SECRET_KEY,
        algorithm="HS256"
    )
    # 用户2的 token
    token2 = jose_jwt.encode(
        {"sub": "2", "exp": 1781011403},
        SECRET_KEY,
        algorithm="HS256"
    )

    # 用实际存在的 pending 邀请码测试
    # 之前查到: d6a9561054404a1b9860422fe5128fb2 (inviter=2, member=258, pending)
    invite_code = "d6a9561054404a1b9860422fe5128fb2"

    headers_base = {
        "Origin": DOMAIN,
        "Referer": f"{DOMAIN}/family-auth"
    }

    async with httpx.AsyncClient(verify=False, timeout=30) as c:
        # 测试1: 不带 token
        resp = await c.get(f"{DOMAIN}/api/family/invitation/{invite_code}", headers=headers_base)
        print(f"测试1 不带token: HTTP {resp.status_code}")
        if resp.status_code == 200:
            d = resp.json()
            print(f"  status={d.get('status')}, invalid_reason={d.get('invalid_reason')}")

        # 测试2: 带用户18 token（被邀请人，会触发合并预览）
        resp = await c.get(
            f"{DOMAIN}/api/family/invitation/{invite_code}",
            headers={**headers_base, "Authorization": f"Bearer {token18}"}
        )
        print(f"\n测试2 用户18 token (被邀请人): HTTP {resp.status_code}")
        if resp.status_code == 200:
            d = resp.json()
            print(f"  status={d.get('status')}, invalid_reason={d.get('invalid_reason')}")
            print(f"  merge_preview 条数: {len(d.get('merge_preview', []))}")
            print(f"  is_self_invite={d.get('is_self_invite')}")
        else:
            print(f"  错误: {resp.text[:300]}")

        # 测试3: 带用户2 token（邀请人，跳过合并预览）
        resp = await c.get(
            f"{DOMAIN}/api/family/invitation/{invite_code}",
            headers={**headers_base, "Authorization": f"Bearer {token2}"}
        )
        print(f"\n测试3 用户2 token (邀请人): HTTP {resp.status_code}")
        if resp.status_code == 200:
            d = resp.json()
            print(f"  status={d.get('status')}, invalid_reason={d.get('invalid_reason')}")
            print(f"  is_self_invite={d.get('is_self_invite')}")

asyncio.run(test_api())
