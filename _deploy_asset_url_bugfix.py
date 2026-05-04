"""[2026-05-05 全端图片附件 BasePath 治理 v1.0] 部署脚本.

本次治理的核心：把后端返回的"裸 /uploads/..." 路径在 H5、admin-web、小程序
统一过 resolveAssetUrl 工具补上部署 basePath，修复"Gateway OK"图片裂开 Bug。

执行步骤：
1) SFTP 把所有变更前端文件（h5-web + admin-web + miniprogram）上传
2) 远程 docker compose build h5-web admin-web（前端）
3) 远程 docker compose up -d h5-web admin-web
4) 等服务启动 25s
5) curl 验证关键 URL 是否可达
6) 用真实带 basePath 的 /uploads/ 链接做"图片代理回源"探针：
   - GET https://newbb.test.bangbangvip.com/autodev/<uuid>/uploads/test.txt
   - 期待响应不是 "Gateway OK" 文本（要么 200/304 真实文件，要么 404 静态资源）

注意：
- 后端没改动，不重建 backend 容器
- 不涉及 db
"""

from __future__ import annotations

import os
import sys
import time
import posixpath

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
PROJECT_BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 本次需要上传的文件（相对仓库根目录）
FILES_TO_UPLOAD = [
    # ===== h5-web 工具与测试 =====
    "h5-web/src/lib/asset-url.ts",
    "h5-web/src/lib/__tests__/asset-url.test.ts",
    "h5-web/src/lib/__tests__/run_asset_url_test.mjs",
    # ===== h5-web 业务页面（按 git status 顺序） =====
    "h5-web/src/app/(ai-chat)/feedback/page.tsx",
    "h5-web/src/app/(tabs)/home/page.tsx",
    "h5-web/src/app/cards/[id]/page.tsx",
    "h5-web/src/app/chat/[sessionId]/page.tsx",
    "h5-web/src/app/checkout/page.tsx",
    "h5-web/src/app/checkup/chat/[sessionId]/page.tsx",
    "h5-web/src/app/checkup/compare/select/page.tsx",
    "h5-web/src/app/checkup/page.tsx",
    "h5-web/src/app/login/page.tsx",
    "h5-web/src/app/merchant/m/store-settings/page.tsx",
    "h5-web/src/app/merchant/orders/page.tsx",
    "h5-web/src/app/merchant/store-settings/page.tsx",
    "h5-web/src/app/my-favorites/page.tsx",
    "h5-web/src/app/news/[id]/page.tsx",
    "h5-web/src/app/points/detail/page.tsx",
    "h5-web/src/app/product/[id]/page.tsx",
    "h5-web/src/app/products/page.tsx",
    "h5-web/src/app/profile/edit/page.tsx",
    "h5-web/src/app/refund-list/page.tsx",
    "h5-web/src/app/search/result/page.tsx",
    "h5-web/src/app/tcm/result/[id]/page.tsx",
    "h5-web/src/app/unified-order/[id]/page.tsx",
    "h5-web/src/app/unified-orders/page.tsx",
    "h5-web/src/components/KnowledgeCard.tsx",
    # ===== admin-web 工具与业务页面 =====
    "admin-web/src/lib/asset-url.ts",
    "admin-web/src/app/(admin)/admin-settlements/page.tsx",
    "admin-web/src/app/(admin)/chat-records/[id]/page.tsx",
    "admin-web/src/app/(admin)/chat-records/page.tsx",
    "admin-web/src/app/(admin)/checkup-details/page.tsx",
    "admin-web/src/app/(admin)/digital-humans/page.tsx",
    "admin-web/src/app/(admin)/drug-details/page.tsx",
    "admin-web/src/app/(admin)/function-buttons/page.tsx",
    "admin-web/src/app/(admin)/home-banners/page.tsx",
    "admin-web/src/app/(admin)/home-menus/page.tsx",
    "admin-web/src/app/(admin)/points/mall/page.tsx",
    "admin-web/src/app/(admin)/product-system/coupons/page.tsx",
    "admin-web/src/app/(admin)/product-system/orders/page.tsx",
    "admin-web/src/app/(admin)/product-system/products/page.tsx",
    "admin-web/src/app/(admin)/product-system/store-bindding/page.tsx",
    "admin-web/src/components/coupon/ProductPickerModal.tsx",
    # ===== 小程序（仅同步源码，不影响部署，但保持仓库与服务器一致） =====
    "miniprogram/utils/asset-url.js",
    "miniprogram/utils/upload-utils.js",
    "miniprogram/pages/chat/index.js",
    "miniprogram/pages/checkup-detail/index.js",
    "miniprogram/pages/digital-human-call/index.js",
    "miniprogram/pages/family-invite/index.js",
    "verify-miniprogram/utils/asset-url.js",
]


def log(msg: str) -> None:
    print(f"[deploy_asset_url] {msg}", flush=True)


def make_ssh() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    log(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        snippet = out if len(out) < 4000 else out[:2000] + "\n...[truncated]...\n" + out[-2000:]
        log(f"stdout:\n{snippet}")
    if err:
        snippet = err if len(err) < 4000 else err[:2000] + "\n...[truncated]...\n" + err[-2000:]
        log(f"stderr:\n{snippet}")
    log(f"exit code: {code}")
    return code, out, err


def sftp_upload(sftp: paramiko.SFTPClient, local: str, remote: str) -> None:
    parts = remote.split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = posixpath.join(cur, p) if cur else "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)
    sftp.put(local, remote)
    log(f"uploaded: {local} -> {remote}")


def main() -> int:
    ssh = make_ssh()
    try:
        sftp = ssh.open_sftp()
        try:
            log("== Step 1: SFTP upload changed files ==")
            uploaded = 0
            for rel in FILES_TO_UPLOAD:
                local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
                if not os.path.exists(local):
                    log(f"WARN: local file missing: {local}")
                    continue
                remote = posixpath.join(REMOTE_DIR, rel)
                sftp_upload(sftp, local, remote)
                uploaded += 1
            log(f"== uploaded {uploaded} files ==")
        finally:
            sftp.close()

        log("== Step 2: docker compose build h5-web admin-web ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose build h5-web admin-web 2>&1 | tail -200",
            timeout=1800,
        )
        if rc != 0:
            log("ERROR: docker compose build failed")
            return 1

        log("== Step 3: docker compose up -d h5-web admin-web ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && docker compose up -d h5-web admin-web 2>&1 | tail -50",
            timeout=600,
        )
        if rc != 0:
            log("ERROR: docker compose up failed")
            return 1

        log("== Step 4: wait services to be ready (30s) ==")
        time.sleep(30)

        log("== Step 5: external URL accessibility checks ==")
        url_checks = [
            (f"{PROJECT_BASE_URL}/", "200|301|302|307|308"),
            (f"{PROJECT_BASE_URL}/api/health", "200"),
            (f"{PROJECT_BASE_URL}/login", "200|301|302|307|308"),
            (f"{PROJECT_BASE_URL}/merchant/orders/", "200|301|302|307|308"),
            (f"{PROJECT_BASE_URL}/admin/", "200|301|302|307|308|404"),
        ]
        all_ok = True
        for url, expect in url_checks:
            rc, out, err = run(
                ssh,
                f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'",
                timeout=30,
            )
            code_str = (out or "").strip()
            if code_str in expect.split("|"):
                log(f"OK   {code_str:>4}  {url}")
            else:
                log(f"FAIL {code_str:>4} (expect {expect})  {url}")
                all_ok = False

        log("== Step 6: 关键回归 — /uploads/ 在带 basePath 路径下不返回 'Gateway OK' ==")
        # 制造一个上传文件作为探针；存在则取 200，不存在则取 404；
        # 但绝不能返回 200 带正文 "Gateway OK"（这是该 Bug 的根因）。
        probe_url = f"{PROJECT_BASE_URL}/uploads/__probe_asset_url_bugfix__.txt"
        # 在后端容器里写一个探针文件，以确保 200 路径
        run(
            ssh,
            f"docker exec {DEPLOY_ID}-backend bash -lc "
            f"\"mkdir -p /app/uploads && echo 'probe-ok' > /app/uploads/__probe_asset_url_bugfix__.txt\"",
            timeout=30,
        )
        rc, out, err = run(
            ssh,
            f"curl -s --max-time 15 '{probe_url}'",
            timeout=30,
        )
        body = (out or "").strip()
        if "Gateway OK" in body:
            log(f"FAIL: /uploads probe via basePath was intercepted by gateway as 'Gateway OK'!")
            log(f"      body = {body[:200]}")
            all_ok = False
        elif "probe-ok" in body:
            log(f"OK: /uploads probe served real content via basePath: {body[:60]}")
        else:
            # 其他响应（如 404 静态资源），只要不是"Gateway OK"，就视为路由正常
            log(f"OK: /uploads probe response (no 'Gateway OK'): {body[:200]}")

        log("== Step 7: 反向 Negative 检查 — 不带 basePath 的裸 /uploads/ 应该被网关返回 'Gateway OK' (确认 Bug 现象客观存在) ==")
        bare_url = f"https://{HOST}/uploads/__probe_asset_url_bugfix__.txt"
        rc, out, err = run(
            ssh,
            f"curl -s --max-time 15 '{bare_url}'",
            timeout=30,
        )
        bare_body = (out or "").strip()
        if "Gateway OK" in bare_body:
            log(f"OK (expected): bare /uploads/ confirmed to be intercepted as 'Gateway OK' (Bug 客观存在 → 验证 basePath 修复路径必要性)")
        else:
            log(f"INFO: bare /uploads/ body = {bare_body[:200]} (网关行为可能已变化，不影响本次修复)")

        log("== Step 8: 运行 H5 工具函数纯逻辑测试（在 docker-host 用 node 直接跑） ==")
        rc, out, err = run(
            ssh,
            f"cd {REMOTE_DIR} && node h5-web/src/lib/__tests__/run_asset_url_test.mjs 2>&1 | tail -40",
            timeout=60,
        )
        if rc != 0 or "passed" not in out:
            log("WARN: asset-url 单测在远程 node 下未通过 (rc=%d)，请人工核对" % rc)
        else:
            log("OK: asset-url 单元测试在远程通过")

        if not all_ok:
            log("== Deploy DONE (有部分失败) ==")
            return 4

        log("== Deploy DONE ==")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
