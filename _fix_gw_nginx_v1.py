"""Bugfix: 修复 gateway-nginx 6b099ed3 项目的 proxy_pass 变量+URI 拼接失效问题。"""
import sys, time
sys.path.insert(0, ".")
from _ssh_helper import run, put_file

REMOTE_CONF = "/home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf"
LOCAL_FIXED = ".chat_output/ef56d73f-4e9f-4266-8b7a-317affb61f2f/6b099ed3-fixed.conf"
TS = time.strftime("%Y%m%d_%H%M%S")
BAK = f"{REMOTE_CONF}.bak_bugfix_{TS}"


def step(title, cmd, timeout=120):
    print(f"\n=== {title} ===")
    print(f"$ {cmd}")
    rc, out, err = run(cmd, timeout=timeout)
    if out:
        print(out.rstrip())
    if err:
        print("[stderr]", err.rstrip())
    print(f"[rc={rc}]")
    return rc, out, err


# 1) 宿主机备份
step("备份当前配置", f"cp {REMOTE_CONF} {BAK} && ls -la {BAK}")

# 2) 上传修复后的配置（临时路径）
tmp_remote = f"/tmp/6b099ed3-fixed-{TS}.conf"
print(f"\n=== 上传修复后的配置 → {tmp_remote} ===")
put_file(LOCAL_FIXED, tmp_remote)
print("uploaded")

# 3) 覆盖到 conf.d
step("覆盖到 conf.d", f"cp {tmp_remote} {REMOTE_CONF} && md5sum {REMOTE_CONF}")

# 4) nginx -t 校验
rc, out, err = step("nginx -t 校验", "docker exec gateway-nginx nginx -t")
if rc != 0:
    print("\n[FATAL] nginx -t 失败，回滚！")
    step("回滚", f"cp {BAK} {REMOTE_CONF}")
    sys.exit(1)

# 5) nginx reload
step("nginx -s reload", "docker exec gateway-nginx nginx -s reload")

# 6) 等 1 秒
time.sleep(1)

# 7) 验证关键路径
print("\n\n========== 验证 ==========\n")
base = "http://127.0.0.1/"
checks = [
    ("openapi.json (后端)", f"{base}/openapi.json"),
    ("api/ 根 (后端)", f"{base}/api/"),
    ("docs (后端 swagger)", f"{base}/docs"),
    ("admin 登录页 (前端)", f"{base}/admin/login"),
    ("h5 根 (前端)", f"{base}/"),
]
for name, url in checks:
    step(name, f"curl -s -o /dev/null -w 'HTTP %{{http_code}}  size=%{{size_download}}  time=%{{time_total}}s\\n' {url}", timeout=30)
