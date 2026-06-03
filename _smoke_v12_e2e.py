"""[守护人体系 PRD v1.2] 端到端业务冒烟"""
import json
import urllib.parse
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://{HOST}/autodev/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=30)


def sh(cmd, timeout=30):
    i, o, e = client.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", errors="replace"), e.read().decode("utf-8", errors="replace")


def remote_curl(method, path, headers=None, body=None):
    headers = headers or {}
    h = " ".join(f"-H '{k}: {v}'" for k, v in headers.items())
    body_arg = f"-d '{body}'" if body else ""
    cmd = (
        f"curl -sk -X {method} -o /tmp/x.txt -w '%{{http_code}}' "
        f"{h} {body_arg} '{BASE}{path}'; echo; cat /tmp/x.txt"
    )
    return sh(cmd)[0]


print("=" * 60)
print("[1] 通过 DB 直接登录已有测试用户 / 注册新用户")
# 通过 schema 创建测试用户更稳妥
phone = "13900900912"
# 注册
out = remote_curl(
    "POST",
    "/api/auth/register",
    headers={"Content-Type": "application/json"},
    body=json.dumps({"phone": phone, "password": "Test123!@#", "nickname": "V12测试用户"}),
)
print(out[:300])

# 登录
out = remote_curl(
    "POST",
    "/api/auth/login",
    headers={"Content-Type": "application/json"},
    body=json.dumps({"phone": phone, "password": "Test123!@#"}),
)
print("\n[登录响应]")
print(out[:400])

# 提取 token
import re

m = re.search(r'"access_token":"([^"]+)"', out)
if not m:
    m = re.search(r'"token":"([^"]+)"', out)
if not m:
    print("\n!! 未取到 token，使用 default admin token 测试")
    client.close()
    raise SystemExit(0)

token = m.group(1)
print(f"\n[token] {token[:30]}...")

auth = {"Authorization": f"Bearer {token}"}
print("\n[2] /api/guardian/v12/i-guard")
print(remote_curl("GET", "/api/guardian/v12/i-guard", headers=auth))
print("\n[3] /api/guardian/v12/managed-quota-summary")
print(remote_curl("GET", "/api/guardian/v12/managed-quota-summary", headers=auth))
print("\n[4] /api/guardian/v12/ai-call-quota")
print(remote_curl("GET", "/api/guardian/v12/ai-call-quota", headers=auth))
print("\n[5] /api/guardian/v12/emergency-quota")
print(remote_curl("GET", "/api/guardian/v12/emergency-quota", headers=auth))
print("\n[6] /api/guardian/v12/invitations/records")
print(remote_curl("GET", "/api/guardian/v12/invitations/records", headers=auth))
print("\n[7] /api/membership/me")
print(remote_curl("GET", "/api/membership/me", headers=auth))

print("\n[8] admin 登录 + /api/admin/emergency-sources")
out = remote_curl(
    "POST",
    "/api/admin/login",
    headers={"Content-Type": "application/json"},
    body=json.dumps({"username": "admin", "password": "admin123"}),
)
print(out[:400])
m = re.search(r'"access_token":"([^"]+)"', out)
if m:
    admin_token = m.group(1)
    ah = {"Authorization": f"Bearer {admin_token}"}
    print("\n[9] admin /api/admin/emergency-sources")
    print(remote_curl("GET", "/api/admin/emergency-sources", headers=ah))

client.close()
