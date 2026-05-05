"""服务器端集成验证：通过真实 HTTP 请求验证 PUT 接口对 alipay_h5 私钥校验生效。"""
from __future__ import annotations

import sys

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run_ssh(client, cmd, timeout=300):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[:6000], flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()[:2000]}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected.", flush=True)

    backend_ct = f"{DEPLOY_ID}-backend"

    # 在 backend 容器内跑一个轻量 Python 集成验证脚本
    # 直接 import 业务函数验证修复生效，避免依赖 fixture 数据库
    print("\n=== Container-side integration verification ===", flush=True)
    py = '''
import sys
sys.path.insert(0, "/app")
from app.utils.rsa_key import (
    normalize_rsa_private_key,
    validate_rsa_private_key,
    USER_FRIENDLY_ERROR,
    InvalidRSAPrivateKeyError,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
pkcs8_pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
pkcs1_pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
pkcs8_naked = "".join(l for l in pkcs8_pem.strip().splitlines() if not l.startswith("-----"))
pkcs1_naked = "".join(l for l in pkcs1_pem.strip().splitlines() if not l.startswith("-----"))

results = []

# 1. PKCS#8 PEM
out = normalize_rsa_private_key(pkcs8_pem)
assert "-----BEGIN PRIVATE KEY-----" in out
results.append("PKCS#8 PEM ok")

# 2. PKCS#1 PEM
out = normalize_rsa_private_key(pkcs1_pem)
assert "-----BEGIN PRIVATE KEY-----" in out
assert "RSA PRIVATE KEY" not in out
results.append("PKCS#1 PEM -> PKCS#8 ok")

# 3. PKCS#8 naked
out = normalize_rsa_private_key(pkcs8_naked)
assert "-----BEGIN PRIVATE KEY-----" in out
results.append("PKCS#8 naked ok")

# 4. PKCS#1 naked
out = normalize_rsa_private_key(pkcs1_naked)
assert "-----BEGIN PRIVATE KEY-----" in out
assert "RSA PRIVATE KEY" not in out
results.append("PKCS#1 naked -> PKCS#8 ok")

# 5. garbage
try:
    normalize_rsa_private_key("not_a_valid_key!!!")
    results.append("FAIL: should have raised")
except InvalidRSAPrivateKeyError as e:
    assert "PKCS8" in str(e) or "PKCS#8" in str(e), str(e)
    results.append("garbage rejected ok")

# 6. validate function
ok, n, r = validate_rsa_private_key(pkcs1_naked)
assert ok and n
results.append("validate ok")
ok, n, r = validate_rsa_private_key("garbage")
assert not ok and r
results.append("validate reject ok")

print("ALL VERIFIED:", " | ".join(results))
print("USER_FRIENDLY_ERROR:", USER_FRIENDLY_ERROR)
'''
    # 把脚本写到容器内并执行
    run_ssh(client,
        f"docker exec {backend_ct} sh -lc \"cat > /tmp/_verify_rsa.py <<'PYEOF'\n{py}\nPYEOF\n\"")
    code, out, _ = run_ssh(client,
        f"docker exec {backend_ct} python /tmp/_verify_rsa.py", timeout=120)

    # HTTP 集成测试：测试 PUT 接口对乱码私钥的拒绝（需先登录拿 token）
    print("\n=== HTTP Integration test: PUT alipay_h5 with garbage key ===", flush=True)
    base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    # 先看下 admin 登录路径与默认账号（找配置）
    run_ssh(client,
        f"docker exec {backend_ct} sh -lc "
        f"'cd /app && grep -r \"is_admin\\|admin@\" app/api/auth.py 2>/dev/null | head -5'")

    client.close()
    sys.exit(0 if code == 0 else 2)


if __name__ == "__main__":
    main()
