#!/usr/bin/env python3
"""验证修复是否生效"""
import paramiko
import httpx
import asyncio
from jose import jwt as jose_jwt

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"
DOMAIN = f"https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
SECRET_KEY = "bini-health-secret-key-2026-very-secure"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# 1. 验证容器内代码
print("=" * 60)
print("验证1: 容器内代码是否已更新")
print("=" * 60)
try:
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15,
                   look_for_keys=False, allow_agent=False, banner_timeout=15)

    out, err = run(f"docker exec {BACKEND_CONTAINER} sh -c \"sed -n '374,384p' /app/app/api/family_management.py\"")
    print("第374-384行:")
    print(out)

    out, err = run(f"docker exec {BACKEND_CONTAINER} sh -c \"sed -n '532,544p' /app/app/api/family_management.py\"")
    print("第532-544行:")
    print(out)

finally:
    client.close()

# 2. 通过 HTTPS 测试接口
print("=" * 60)
print("验证2: HTTPS 接口测试")
print("=" * 60)

async def test_api():
    # 生成用户18的 token
    token = jose_jwt.encode(
        {"sub": "18", "exp": 1781011403},
        SECRET_KEY,
        algorithm="HS256"
    )

    async with httpx.AsyncClient(verify=False, timeout=30) as client_http:
        # 不带 token
        resp = await client_http.get(
            f"{DOMAIN}/api/family/invitation/695e3db0ab80",
            headers={"Origin": DOMAIN, "Referer": f"{DOMAIN}/family-auth"}
        )
        print(f"不带token: HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  status={data.get('status')}, invalid_reason={data.get('invalid_reason')}")

        # 带用户18 token
        resp = await client_http.get(
            f"{DOMAIN}/api/family/invitation/695e3db0ab80",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": DOMAIN,
                "Referer": f"{DOMAIN}/family-auth"
            }
        )
        print(f"带用户18 token: HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  status={data.get('status')}, invalid_reason={data.get('invalid_reason')}, merge_preview_count={len(data.get('merge_preview', []))}")
        else:
            print(f"  响应体: {resp.text[:500]}")

asyncio.run(test_api())

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
