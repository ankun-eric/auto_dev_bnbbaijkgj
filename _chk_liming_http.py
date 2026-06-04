# -*- coding: utf-8 -*-
"""在 backend 容器内，用 user_id=2 生成 token，直接走真实 HTTP 删除接口对黎明(238)删除，
打印接口真实返回，验证线上接口到底回的是新提示还是老提示。"""
import base64
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
CT = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

REMOTE = r'''
import json, urllib.request
from app.core.security import create_access_token

# user_id=2（黎明档案的归属账号），生成访问令牌
token = create_access_token({"sub": "2"})
print("token head:", token[:20], "...")

url = "http://127.0.0.1:8000/api/family/member/238"
req = urllib.request.Request(url, method="DELETE")
req.add_header("Authorization", "Bearer " + token)
req.add_header("Content-Type", "application/json")
req.data = json.dumps({}).encode("utf-8")
try:
    resp = urllib.request.urlopen(req, timeout=30)
    code = resp.getcode()
    body = resp.read().decode("utf-8", "ignore")
except urllib.error.HTTPError as e:
    code = e.code
    body = e.read().decode("utf-8", "ignore")
print("=== HTTP STATUS:", code, "===")
print("=== BODY ===")
print(body)
'''

def run(cmd, timeout=120):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    cli.close()
    return out, err

b64 = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
cmd = (
    f"docker exec {CT} sh -c "
    f"'echo {b64} | base64 -d > /tmp/_h.py && cd /app && PYTHONPATH=/app python /tmp/_h.py'"
)
out, err = run(cmd)
print("=== STDOUT ===")
print(out)
if err.strip():
    print("=== STDERR ===")
    print(err)
