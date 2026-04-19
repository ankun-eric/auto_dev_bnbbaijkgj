"""第 N 期 5 BUG + 1 改造 — 全量部署到正式服务器。

涉及变更：
- backend: tcm.py（BUG①）、admin.py（BUG②）、coupons_admin（BUG③，已存在）、
            products.py + models.py + main.py（改造④ + BUG⑤）
- admin-web: product-system/coupons/page.tsx（BUG③）
- h5-web: (tabs)/services/page.tsx（改造④）
- gateway: gateway-routes.conf（BUG②/③）
- docker-compose.prod.yml（BUG②：STATIC_BASE_URL）
"""
import os
import io
import sys
import time
import tarfile
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_DIR = "/home/ubuntu/gateway"
GATEWAY_CONF = f"{GATEWAY_DIR}/conf.d/{DEPLOY_ID}.conf"

CHANGED_FILES = [
    "backend/app/api/tcm.py",
    "backend/app/api/admin.py",
    "backend/app/api/products.py",
    "backend/app/api/coupons_admin.py",
    "backend/app/main.py",
    "backend/app/models/models.py",
    "backend/tests/test_period_n_bugfix.py",
    "admin-web/src/app/(admin)/product-system/coupons/page.tsx",
    "h5-web/src/app/(tabs)/services/page.tsx",
    "docker-compose.prod.yml",
    "gateway-routes.conf",
]


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=900, check=False, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out[-3000:])
        if err:
            print(f"[stderr] {err[-1500:]}")
        print(f"[exit {code}]")
    if check and code != 0:
        raise RuntimeError(f"FAIL ({code}): {cmd}")
    return out, err, code


def make_tarball(local_root, files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(local_root, rel.replace("/", os.sep))
            if os.path.exists(full):
                tar.add(full, arcname=rel)
            else:
                print(f"  [warn] missing: {rel}")
    buf.seek(0)
    return buf.getvalue()


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    # 1. 同步源代码
    print("\n=== Step 1: 同步源代码 ===")
    tar_bytes = make_tarball(local_root, CHANGED_FILES)
    remote_tar = f"/tmp/{DEPLOY_ID}-period-n.tar.gz"
    sftp = c.open_sftp()
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_bytes)
    sftp.close()
    print(f"  uploaded {len(tar_bytes)} bytes")
    run(c, f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}", check=True)

    # 验证关键文件
    run(c, f"grep -c 'parent_category_id' {PROJECT_DIR}/backend/app/api/products.py")
    run(c, f"grep -c '_build_logo_url' {PROJECT_DIR}/backend/app/api/admin.py")
    run(c, f"grep -c '_migrate_product_categories_hierarchy' {PROJECT_DIR}/backend/app/main.py")
    run(c, f"grep -c 'FulfillmentBadge' {PROJECT_DIR}/h5-web/src/app/\\(tabs\\)/services/page.tsx")

    # 2. 重新构建（backend Python 代码挂载，next.js 需要重建）
    print("\n=== Step 2: docker compose build ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web h5-web 2>&1 | tail -50",
        timeout=1500, check=True)

    print("\n=== Step 3: 重启所有服务（含 backend 应用新代码 + STATIC_BASE_URL）===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate 2>&1 | tail -30",
        timeout=240, check=True)

    print("\n=== Step 4: 等待容器就绪 ===")
    time.sleep(20)
    for i in range(15):
        out, _, _ = run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'", quiet=True)
        ok = out.count("Up ") >= 4 and "Restarting" not in out
        print(f"  [check {i+1}] containers Up={out.count('Up ')}")
        if ok:
            break
        time.sleep(8)

    # 5. gateway 网络 & 配置
    print("\n=== Step 5: gateway 网络 ===")
    run(c, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")

    print("\n=== Step 6: 更新 gateway conf.d ===")
    run(c, f"cp {GATEWAY_CONF} {GATEWAY_CONF}.bak.$(date +%Y%m%d%H%M%S) 2>&1 || true")
    out, _, _ = run(c, f"cat {GATEWAY_CONF}", quiet=True)

    def extract_balanced_block(text, location_path):
        idx = text.find(f"location {location_path}")
        if idx == -1:
            return None
        brace_start = text.find("{", idx)
        if brace_start == -1:
            return None
        depth = 0
        i = brace_start
        while i < len(text):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[idx:i+1]
            i += 1
        return None

    extra_blocks = []
    for path in [f"/autodev/{DEPLOY_ID}/downloads/", f"/autodev/{DEPLOY_ID}/apk/"]:
        blk = extract_balanced_block(out, path)
        if blk:
            extra_blocks.append(f"# Preserved: {path}\n{blk}")

    local_routes_path = os.path.join(local_root, "gateway-routes.conf")
    with open(local_routes_path, "r", encoding="utf-8") as f:
        local_routes = f.read()
    final_conf = local_routes.rstrip()
    if extra_blocks:
        final_conf += "\n\n# ===== Preserved static locations =====\n" + "\n\n".join(extra_blocks) + "\n"
    else:
        final_conf += "\n"

    sftp = c.open_sftp()
    with sftp.open(GATEWAY_CONF, "w") as f:
        f.write(final_conf)
    sftp.close()

    print("\n=== Step 7: nginx -t & reload ===")
    out, err, code = run(c, "docker exec gateway nginx -t 2>&1")
    if code != 0:
        print("nginx -t FAILED, restoring backup")
        run(c, f"ls -t {GATEWAY_CONF}.bak.* | head -1 | xargs -I{{}} cp {{}} {GATEWAY_CONF}")
        sys.exit(1)
    run(c, "docker exec gateway nginx -s reload 2>&1")
    time.sleep(3)

    print("\n=== Step 8: 最终容器状态 ===")
    run(c, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 9: 链接可达性快检 ===")
    base = f"https://{DOMAIN}/autodev/{DEPLOY_ID}"
    for path in ["/", "/admin/login", "/api/products/categories", "/api/products/hot-recommendations?limit=6"]:
        run(c, f"curl -s -o /dev/null -w '%{{http_code}}  {path}\\n' '{base}{path}'")

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
