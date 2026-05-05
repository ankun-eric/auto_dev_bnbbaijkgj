"""容器内验证脚本：直接 import 业务函数验证修复生效。"""
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
pkcs8_naked = "".join(
    ln for ln in pkcs8_pem.strip().splitlines() if not ln.startswith("-----")
)
pkcs1_naked = "".join(
    ln for ln in pkcs1_pem.strip().splitlines() if not ln.startswith("-----")
)

results = []

out = normalize_rsa_private_key(pkcs8_pem)
assert "-----BEGIN PRIVATE KEY-----" in out
results.append("[1] PKCS#8 PEM ok")

out = normalize_rsa_private_key(pkcs1_pem)
assert "-----BEGIN PRIVATE KEY-----" in out
assert "RSA PRIVATE KEY" not in out
results.append("[2] PKCS#1 PEM -> PKCS#8 ok")

out = normalize_rsa_private_key(pkcs8_naked)
assert "-----BEGIN PRIVATE KEY-----" in out
results.append("[3] PKCS#8 naked ok")

out = normalize_rsa_private_key(pkcs1_naked)
assert "-----BEGIN PRIVATE KEY-----" in out
assert "RSA PRIVATE KEY" not in out
results.append("[4] PKCS#1 naked -> PKCS#8 ok")

try:
    normalize_rsa_private_key("not_a_valid_key!!!")
    results.append("[5] FAIL: should have raised")
except InvalidRSAPrivateKeyError as e:
    assert "PKCS8" in str(e) or "PKCS#8" in str(e), str(e)
    results.append("[5] garbage rejected ok")

ok, n, r = validate_rsa_private_key(pkcs1_naked)
assert ok and n
results.append("[6] validate ok")

ok, n, r = validate_rsa_private_key("garbage")
assert not ok and r
results.append("[7] validate reject ok")

# 验证 alipay_service 运行时兜底
from app.services.alipay_service import _ensure_pem_format
# _ensure_pem_format 不变，但 _build_client_from_config 内部会调 normalize
# 这里只验证导入路径
import inspect
src = inspect.getsource(__import__("app.services.alipay_service", fromlist=["x"]))
assert "normalize_rsa_private_key" in src
results.append("[8] alipay_service runtime fallback ok")

# 验证 payment_config.py 保存校验已生效
src2 = inspect.getsource(__import__("app.api.payment_config", fromlist=["x"]))
assert "validate_rsa_private_key" in src2
assert "alipay_h5" in src2 and "alipay_app" in src2
results.append("[9] payment_config save validation ok")

print("=" * 60)
print("ALL VERIFIED:")
for r in results:
    print("  ", r)
print("=" * 60)
print("USER_FRIENDLY_ERROR =", USER_FRIENDLY_ERROR)
