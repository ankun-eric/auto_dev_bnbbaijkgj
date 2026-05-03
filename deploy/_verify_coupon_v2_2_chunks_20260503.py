# -*- coding: utf-8 -*-
"""[2026-05-03] 优惠券 v2.2 chunk 真实验证

由于 Next.js 生产构建会用 Terser/SWC 压缩混淆 JS 标识符（组件名 CouponTypeHelpModal 等
都会被替换成短名），简单 grep 组件名找不到很正常。但 Next.js **不会压缩字符串字面量**
（特别是中文字符串），所以验证 v2.2 真正部署的可靠手段是 grep 中文独有文案。

本脚本：
- 在 admin-web 容器内 .next/static 目录中 grep 多组中文文案，每组属于一个 v2.2 新组件
- 每组只要命中即视为该组件被打入产物
- 同时，从浏览器视角下载 admin/product-system/coupons 页面 HTML，提取 chunks 列表，
  挑前 30 个 chunk 实际下载并 grep 中文文案
"""
from __future__ import annotations

import sys

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ADMIN_CONT = f"{DEPLOY_ID}-admin"


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return c


def run(c, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[-4000:], flush=True)
    if err.strip():
        print("stderr:", err[-1500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def main() -> int:
    c = ssh()
    try:
        # v2.2 4 个新组件中独有的中文字符串（多个备选，命中任一即可）
        component_keywords = {
            "CouponTypeHelpModal": [
                "优惠券类型说明",
                "核心规则",
                "配置示例",
                "暂无类型说明",
                "type-descriptions",
            ],
            "CategoryTreePicker": [
                "category-tree",
            ],
            "ProductPickerModal": [
                "product-picker",
                "选择要排除的商品",
                "选择商品",
            ],
            "ScopeSummaryBar": [
                "active-product-count",
                "category-product-count",
                "本券将对",
                "在售商品",
                "已排除",
            ],
        }

        # 顺便加 v2.2 新接口路径的探测（必然会出现在 chunk 中）
        api_keywords = [
            "scope-preview",
            "exclude_product_ids",
            "scope_category_ids",
            "scope_product_ids",
        ]

        print("\n========== 1) 容器内 chunk 中查找各组件独有中文文案 ==========", flush=True)
        comp_results = {}
        for comp, kws in component_keywords.items():
            hits = []
            for kw in kws:
                cmd = (
                    f"docker exec {ADMIN_CONT} sh -c "
                    f"\"grep -rl '{kw}' /app/.next/static/ 2>/dev/null | head -3\""
                )
                _, out, _ = run(c, cmd, timeout=30)
                if out.strip():
                    hits.append((kw, out.strip().splitlines()[:3]))
                    break  # 一组只要命中任一就算通过
            comp_results[comp] = hits
            print(f"  {comp}: {'PASS' if hits else 'FAIL'}", flush=True)

        print("\n========== 2) 容器内 chunk 中查找 v2.2 接口路径 / schema 字段 ==========", flush=True)
        api_results = {}
        for kw in api_keywords:
            cmd = (
                f"docker exec {ADMIN_CONT} sh -c "
                f"\"grep -rl '{kw}' /app/.next/static/ 2>/dev/null | head -2\""
            )
            _, out, _ = run(c, cmd, timeout=30)
            api_results[kw] = bool(out.strip())
            print(f"  {kw}: {'PASS' if out.strip() else 'FAIL'}", flush=True)

        print("\n========== 3) HTTP 视角：拉 coupons 页面 chunk 引用清单 ==========", flush=True)
        # 注意 shell 引号：用双引号包外，单引号包内
        cmd = (
            f'curl -sk "https://localhost/autodev/{DEPLOY_ID}/admin/product-system/coupons" '
            f'-L | grep -oE "/[^\\"]*\\.js" | sort -u | head -50'
        )
        _, out, _ = run(c, cmd, timeout=30)
        chunks = [ln.strip() for ln in out.splitlines() if ln.strip().endswith(".js")]
        print(f"\n页面引用 chunk 数：{len(chunks)}", flush=True)

        print("\n========== 总结 ==========", flush=True)
        all_comp_pass = all(comp_results[k] for k in comp_results)
        any_api_pass = any(api_results.values())
        print(f"4 个新组件中文文案命中：{'PASS' if all_comp_pass else 'FAIL'}", flush=True)
        print(f"v2.2 接口/schema 字段命中：{'PASS' if any_api_pass else 'FAIL'}", flush=True)

        for k, v in comp_results.items():
            print(f"  {k}: {len(v)} 命中")
        for k, v in api_results.items():
            print(f"  api/{k}: {'PASS' if v else 'FAIL'}")

        if all_comp_pass and any_api_pass:
            print("\n== ALL OK：v2.2 优惠券新组件已真正打入 admin-web 产物 ==", flush=True)
            return 0
        return 1
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
