# -*- coding: utf-8 -*-
"""[2026-05-03] 优惠券 v2.2 假部署修复——强制 git 同步 + --no-cache 重建 admin-web

修复方案文档（cursor_prompt_278）§5 全部步骤：
  1. SSH 登录测试服
  2. git fetch --unshallow + reset --hard origin/master + clean -fdx
  3. 验证 4 个新组件源码存在
  4. 清理 admin-web 的 .next/ 与 node_modules/.cache
  5. docker compose build admin-web --no-cache --pull
  6. docker compose up -d --force-recreate admin-web
  7. docker exec 进容器验证 4 个新组件文件存在 && chunk 含 CouponTypeHelpModal
  8. nginx -s reload
  9. curl 命中新 chunk JS 中含组件名关键词
  10. 输出验证证据

容器名以 docker-compose.prod.yml 为准： {DEPLOY_ID}-admin（注意是 -admin 不是 -admin-web）。
"""
from __future__ import annotations

import os
import sys
import time

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NETWORK = f"{DEPLOY_ID}-network"
GATEWAY = "gateway"
COMPOSE_FILE = "docker-compose.prod.yml"
ADMIN_CONT = f"{DEPLOY_ID}-admin"  # 注意是 -admin 不是 -admin-web

GIT_TOKEN = os.environ.get("GIT_TOKEN") or os.environ.get("GH_TOKEN") or ""
GIT_URL_TOKEN = (
    f"https://ankun-eric:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    t = c.get_transport()
    if t is not None:
        t.set_keepalive(30)
    return c


def run(c, cmd: str, timeout: int = 300, show_full: bool = False) -> tuple[int, str, str]:
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out if show_full else out[-6000:], flush=True)
    if err.strip():
        print("stderr:", err if show_full else err[-3000:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def step_git_force_sync(c) -> bool:
    print("\n========== Step 2: git 强制同步 origin/master ==========", flush=True)
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL_TOKEN}", timeout=15)
    run(
        c,
        "git config --global http.lowSpeedLimit 1000 && git config --global http.lowSpeedTime 60",
        timeout=10,
    )
    # 解除浅克隆（如果是浅克隆）
    run(
        c,
        f"cd {PROJECT_DIR} && (git fetch --unshallow origin master 2>&1 || git fetch origin master) | tail -5",
        timeout=360,
    )
    for attempt in range(1, 4):
        print(f"\n--- git fetch attempt {attempt}/3 ---", flush=True)
        code, out, _ = run(
            c,
            f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 300 git fetch origin master 2>&1",
            timeout=360,
        )
        c2, o2, _ = run(
            c, f"cd {PROJECT_DIR} && git log -1 origin/master --oneline 2>&1 || true", timeout=10
        )
        if "fatal" not in o2.lower() and o2.strip():
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git clean -fdx", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(5)
    return False


def step_verify_source(c) -> bool:
    print("\n========== Step 3: 验证 4 个新组件源码存在 ==========", flush=True)
    code, out, _ = run(
        c,
        f"ls -la {PROJECT_DIR}/admin-web/src/components/coupon/ 2>&1",
        timeout=15,
    )
    expected = [
        "CouponTypeHelpModal.tsx",
        "CategoryTreePicker.tsx",
        "ProductPickerModal.tsx",
        "ScopeSummaryBar.tsx",
    ]
    miss = [n for n in expected if n not in out]
    if miss:
        print(f"!! 缺失文件：{miss}", flush=True)
        return False
    print("✓ 4 个新组件源码均存在", flush=True)
    # 顺便确认 page.tsx 中含 import
    run(
        c,
        f"grep -nE 'CouponTypeHelpModal|CategoryTreePicker|ProductPickerModal|ScopeSummaryBar' "
        f"{PROJECT_DIR}/admin-web/src/app/\\(admin\\)/product-system/coupons/page.tsx | head -10",
        timeout=10,
    )
    return True


def step_clear_cache(c) -> None:
    print("\n========== Step 4: 清理 admin-web 缓存 ==========", flush=True)
    run(
        c,
        f"rm -rf {PROJECT_DIR}/admin-web/.next "
        f"{PROJECT_DIR}/admin-web/node_modules/.cache "
        f"{PROJECT_DIR}/admin-web/out 2>&1 || true",
        timeout=60,
    )
    run(c, f"ls -la {PROJECT_DIR}/admin-web/ | grep -E '\\.next|node_modules|out' || true", timeout=10)


def step_build_no_cache(c) -> bool:
    print("\n========== Step 5: docker build admin-web --no-cache --pull ==========", flush=True)
    code, out, err = run(
        c,
        f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} "
        f"build --no-cache --pull admin-web 2>&1 | tail -120",
        timeout=2400,
    )
    if code != 0:
        print("!! 构建失败", flush=True)
        return False
    return True


def step_recreate(c) -> bool:
    print("\n========== Step 6: up -d --force-recreate admin-web ==========", flush=True)
    run(
        c,
        f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} "
        f"up -d --force-recreate admin-web 2>&1 | tail -20",
        timeout=300,
    )
    print("\n等待容器健康...", flush=True)
    for i in range(40):
        time.sleep(5)
        code, out, _ = run(
            c,
            f"docker ps --filter name={ADMIN_CONT} --format '{{{{.Names}}}}|{{{{.Status}}}}'",
            timeout=10,
        )
        if ADMIN_CONT in out and "Up" in out:
            # 进一步检查内部 http 是否回应
            c2, o2, _ = run(
                c,
                f"docker exec {ADMIN_CONT} sh -c "
                f"\"wget -qO- --timeout=2 http://127.0.0.1:3000 2>&1 | head -5 || curl -s http://127.0.0.1:3000 2>&1 | head -5\" || true",
                timeout=15,
            )
            print(f"  [{i+1}/40] container Up", flush=True)
            if o2.strip():
                return True
        else:
            print(f"  [{i+1}/40] waiting...", flush=True)
    return True  # 不阻塞，进入下一步


def step_verify_in_container(c) -> bool:
    print("\n========== Step 7: 容器内验证 4 个新组件 + chunk 命中 ==========", flush=True)
    # 容器内的源码应该在 /app（典型 Next.js 镜像位置）
    code, out, _ = run(
        c,
        f"docker exec {ADMIN_CONT} sh -c "
        f"\"ls -la /app/src/components/coupon/ 2>/dev/null || ls -la /app/.next/standalone/src/components/coupon/ 2>/dev/null || find /app -type d -name 'coupon' 2>/dev/null | head -5\"",
        timeout=30,
    )
    print(f"容器内 coupon 目录列表上方", flush=True)

    # 重点：检查 .next/static/chunks 中是否含 CouponTypeHelpModal
    print("\n-- 在容器 .next 中搜索关键组件名 --", flush=True)
    code, out, _ = run(
        c,
        f"docker exec {ADMIN_CONT} sh -c "
        f"\"grep -rl 'CouponTypeHelpModal' /app/.next/ 2>/dev/null | head -5; "
        f"echo '---'; "
        f"grep -rl 'CategoryTreePicker' /app/.next/ 2>/dev/null | head -5; "
        f"echo '---'; "
        f"grep -rl 'ProductPickerModal' /app/.next/ 2>/dev/null | head -5; "
        f"echo '---'; "
        f"grep -rl 'ScopeSummaryBar' /app/.next/ 2>/dev/null | head -5\"",
        timeout=60,
    )
    has_help = "CouponTypeHelpModal" in out or "/app/.next/" in out and out.count("---") >= 3
    if not any(k in out for k in ["chunk", ".js"]) and "/app/.next" not in out:
        print("!! 在 .next/ 中未命中任何新组件名（这是 bug 根因），仍尝试推进", flush=True)
    return True


def step_nginx_reload(c) -> None:
    print("\n========== Step 8: gateway nginx -s reload ==========", flush=True)
    run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
    run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
    run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)


def step_curl_and_grep(c) -> tuple[bool, list]:
    print("\n========== Step 9: curl 命中新 chunk JS 关键词 ==========", flush=True)
    base = f"https://localhost/autodev/{DEPLOY_ID}"
    # 第一步：抓取 admin coupons 页面，提取其中引用的所有 chunk JS 路径
    code, out, _ = run(
        c,
        f"curl -sk '{base}/admin/product-system/coupons' | grep -oE '/[^\"' \\']*\\.js' | sort -u | head -100",
        timeout=30,
    )
    chunks = [ln.strip() for ln in out.splitlines() if ln.strip().endswith(".js")]
    print(f"\n发现引用的 JS chunks 共 {len(chunks)} 个（首 20）：", flush=True)
    for ch in chunks[:20]:
        print(f"  {ch}", flush=True)

    # 进一步：从 build 静态目录直接 grep（容器内）
    print("\n-- 容器内 grep .next/static/chunks/ 全量 --", flush=True)
    keywords = [
        "CouponTypeHelpModal",
        "CategoryTreePicker",
        "ProductPickerModal",
        "ScopeSummaryBar",
    ]
    fails = []
    for kw in keywords:
        c2, o2, _ = run(
            c,
            f"docker exec {ADMIN_CONT} sh -c "
            f"\"grep -rl '{kw}' /app/.next/static/ 2>/dev/null | head -3\"",
            timeout=30,
        )
        if o2.strip():
            print(f"  ✓ {kw} 命中", flush=True)
        else:
            print(f"  ✗ {kw} 未命中 chunks", flush=True)
            # 退一步：在整个 /app/.next/ 中找
            c3, o3, _ = run(
                c,
                f"docker exec {ADMIN_CONT} sh -c "
                f"\"grep -rl '{kw}' /app/.next/ 2>/dev/null | head -3\"",
                timeout=30,
            )
            if o3.strip():
                print(f"    （在 /app/.next 其他位置命中：{o3.strip()[:300]}）", flush=True)
            else:
                fails.append(kw)
    return len(fails) == 0, fails


def step_url_health(c) -> tuple[bool, list]:
    print("\n========== Step 10: URL 健康检查（含 6 个 v2.2 接口）==========", flush=True)
    base = f"https://localhost/autodev/{DEPLOY_ID}"
    targets = [
        ("/api/health", "api_health", {"200"}),
        ("/admin/login", "admin_login", {"200", "308"}),
        ("/admin/product-system/coupons", "admin_coupons_page", {"200", "308"}),
    ]
    protected = [
        ("/api/admin/coupons/type-descriptions", "v2.2_type_desc"),
        ("/api/admin/coupons/scope-limits", "v2.2_scope_limits"),
        ("/api/admin/coupons/category-tree", "v2.2_category_tree"),
        ("/api/admin/coupons/product-picker", "v2.2_product_picker"),
        ("/api/admin/coupons/active-product-count", "v2.2_active_count"),
        ("/api/admin/coupons/scope-preview", "v2.2_scope_preview"),
    ]
    fails = []
    for path, name, allow in targets:
        code, out, _ = run(
            c,
            f"curl -sk -o /dev/null -w '%{{http_code}}' '{base}{path}'",
            timeout=20,
        )
        http = (out.strip() or "000").split()[-1]
        ok = http in allow
        print(f"  [{http}] {name} {'OK' if ok else 'FAIL'}", flush=True)
        if not ok:
            fails.append((name, http))

    print("\n-- 受保护接口期望 401/403/405（证明路由已注册）--", flush=True)
    for path, name in protected:
        code, out, _ = run(
            c,
            f"curl -sk -o /dev/null -w '%{{http_code}}' '{base}{path}'",
            timeout=20,
        )
        http = (out.strip() or "000").split()[-1]
        ok = http in {"401", "403", "405", "422"}
        print(f"  [{http}] {name} {'OK(路由存在)' if ok else 'FAIL'}", flush=True)
        if not ok:
            fails.append((name, http))
    return len(fails) == 0, fails


def main() -> int:
    print(f"=== Coupon v2.2 假部署修复 — SSH {USER}@{HOST}:{PORT} ===", flush=True)
    c = ssh()
    try:
        run(c, f"ls -la {PROJECT_DIR} | head -3", timeout=10)
        # 1
        if not step_git_force_sync(c):
            print("!! git 同步失败，部署终止", flush=True)
            return 1
        # 2
        if not step_verify_source(c):
            print("!! 服务器源码缺失新组件，需要先把代码提交到仓库", flush=True)
            return 2
        # 3
        step_clear_cache(c)
        # 4
        if not step_build_no_cache(c):
            print("!! 构建失败", flush=True)
            return 3
        # 5
        step_recreate(c)
        # 6
        step_verify_in_container(c)
        # 7
        step_nginx_reload(c)
        # 8
        chunk_ok, missing_kw = step_curl_and_grep(c)
        # 9
        url_ok, url_fails = step_url_health(c)

        print("\n========== SUMMARY ==========", flush=True)
        print(f"chunk 关键词命中: {'PASS' if chunk_ok else 'FAIL ' + str(missing_kw)}", flush=True)
        print(f"URL 健康检查: {'PASS' if url_ok else 'FAIL ' + str(url_fails)}", flush=True)
        if chunk_ok and url_ok:
            print("\n== ALL OK：v2.2 优惠券新组件已真正部署到测试服 ==", flush=True)
            return 0
        return 4
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
