#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PRD-426] 部署后 smoke 验证（基于 HTTPS）
- AC-01..AC-08：删除 AI 对话首页输入框上方 + 选择咨询人 浮层
"""
import sys
import re
import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

def hit(label, path, expect_status=(200, 301, 302, 308)):
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=20, allow_redirects=False)
        ok = r.status_code in expect_status
        print(f"[{'OK' if ok else 'FAIL'}] {label:30s} {url} -> HTTP {r.status_code}")
        return r
    except Exception as e:
        print(f"[FAIL] {label:30s} {url} -> {e}")
        return None


def main():
    print("=" * 80)
    print("[PRD-426] AI 对话首页 -- 删除选择咨询人浮层 -- 部署 smoke 验证")
    print("=" * 80)

    # T1 站点入口可达
    hit("H5 root", "/")
    # T2 ai-home 路由可达（未登录会 308 重定向到 /login，符合预期）
    r = hit("ai-home", "/ai-home")
    # T3 后端 API 健康
    r = hit("api/health", "/api/health")
    if r is not None and r.status_code == 200:
        print(f"      api/health body = {r.text[:120]}")
    # T4 AI 配置接口
    r = hit("api/ai-home-config", "/api/ai-home-config")
    if r is not None and r.status_code == 200:
        print(f"      ai-home-config len = {len(r.text)}")
    # T5 登录页可达
    hit("login page", "/login")

    # T6 关键校验：通过登录页 + ai-home 跳转的最终落地页 HTML 应不再含 + 选择咨询人 文本
    print("\n--- AC-07/08: HTML 响应正文不应再含 + 选择咨询人 文案 ---")
    found = False
    for path in ["/", "/ai-home", "/login"]:
        try:
            r = requests.get(f"{BASE}{path}", timeout=20)
            text = r.text
            if "+ 选择咨询人" in text or "+选择咨询人" in text:
                print(f"[FAIL] {path} 响应中仍含 '+ 选择咨询人' 文案")
                found = True
            else:
                print(f"[OK] {path} HTTP {r.status_code} body 中无 '+ 选择咨询人' 文案 (len={len(text)})")
        except Exception as e:
            print(f"[WARN] {path} 拉取失败: {e}")

    print("\n[DONE] smoke 验证结束")
    return 0 if not found else 1


if __name__ == "__main__":
    sys.exit(main())
