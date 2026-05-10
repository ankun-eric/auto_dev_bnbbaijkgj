"""[PRD-455 V7] 服务器侧非 UI 自动化测试

通过 SSH + docker exec + grep 直接在服务器上 Next.js 已构建的 .next 静态产物中
检索 PRD V7 各项功能要点的关键文案 / data-testid，确认改动已实际编译生效。

每个用例 = 一个 grep 表达式 + 期望命中文件数 ≥ 1。

输出最后一行：[SUMMARY] passed=X failed=Y
"""
from __future__ import annotations

import sys
from typing import List, Tuple

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
H5_CONTAINER = f"{DEPLOY_ID}-h5"

# 各 PRD 功能要点的关键标识。Sidebar 在 ai-home 页面里被引用，
# 编译后会被打到 (ai-chat)/ai-home/page-*.js 静态 chunk 里。
TEST_CASES: List[Tuple[str, str]] = [
    # F-01 顶栏（无 × 关闭键）—— 抽屉根容器 testid
    ("F-01 顶栏 testid bh-sidebar-top", "bh-sidebar-top"),
    # F-02 铃铛
    ("F-02 铃铛 icon testid", "bh-icon-bell"),
    # F-03 二维码（会员码）
    ("F-03 会员码 icon testid", "bh-icon-qrcode"),
    # F-04 齿轮（设置）
    ("F-04 设置 icon testid", "bh-icon-settings"),
    # F-05 ID 胶囊
    ("F-05 ID 胶囊 testid", "bh-id-capsule"),
    # F-06 资产行 4 并列
    ("F-06 积分", "bh-asset-points"),
    ("F-06 优惠券", "bh-asset-coupons"),
    ("F-06 订单", "bh-asset-orders"),
    ("F-06 收藏", "bh-asset-favorites"),
    # F-07 健康档案 + 我的设备
    ("F-07 健康档案入口", "bh-entry-health-archive"),
    ("F-07 我的设备入口", "bh-entry-devices"),
    ("F-07 文案 家人健康管理", "家人健康管理"),
    ("F-07 文案 硬件设备管理", "硬件设备管理"),
    # F-08 历史对话区块
    ("F-08 历史对话标题区", "bh-history-section-header"),
    ("F-08 管理按钮", "bh-history-manage-btn"),
    # F-09 时间分组
    ("F-09 最近 7 天分组", "最近 7 天"),
    ("F-09 最近 30 天分组", "最近 30 天"),
    # F-10 历史条目 + 置顶标签
    ("F-10 单条历史 testid", "bh-history-item"),
    ("F-10 置顶标签", "bh-pin-tag"),
    # F-11 ⋯ 按钮 + 左滑
    ("F-11 ⋯ 按钮", "bh-history-more-btn"),
    ("F-11 左滑置顶", "bh-swipe-pin"),
    ("F-11 左滑删除", "bh-swipe-delete"),
    # F-12 管理态
    ("F-12 管理态条 testid", "bh-manage-bar"),
    ("F-12 全选按钮", "bh-manage-select-all"),
    ("F-12 删除按钮", "bh-manage-delete"),
    # F-13 配色（方案 A 通透天空 主色 + 渐变端点）
    ("F-13 渐变起点 #F0F9FF", "F0F9FF"),
    ("F-13 渐变终点 #DBEAFE", "DBEAFE"),
    # F-14 抽屉宽度 85%（CSS 写法在 JSX 里以 width: '85%' 出现）
    ("F-14 抽屉宽度 85%", "85%"),
    # 抽屉根 testid
    ("Drawer root testid", "bh-sidebar-root"),
    ("Drawer mask testid", "bh-sidebar-mask"),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def docker_grep(cli: paramiko.SSHClient, pattern: str) -> int:
    """在容器 .next 目录里 grep 指定字符串，返回命中文件数。"""
    # 使用 -F 字面量匹配，不解析正则
    cmd = (
        f"docker exec {H5_CONTAINER} sh -c "
        f"\"grep -rlF -- '{pattern}' /app/.next 2>/dev/null | wc -l\""
    )
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    try:
        return int(out.split()[0]) if out else 0
    except Exception:
        return 0


def main() -> int:
    cli = ssh_connect()
    try:
        passed = 0
        failed: List[Tuple[str, str]] = []
        for name, pattern in TEST_CASES:
            cnt = docker_grep(cli, pattern)
            ok = cnt >= 1
            tag = "PASS" if ok else "FAIL"
            print(f"[{tag}] {name:40s} pattern={pattern!r:35s} hit_files={cnt}")
            if ok:
                passed += 1
            else:
                failed.append((name, pattern))
        total = len(TEST_CASES)
        print()
        print(f"[SUMMARY] passed={passed}/{total} failed={len(failed)}")
        if failed:
            print("[FAIL DETAIL]")
            for n, p in failed:
                print(f"  - {n}: {p}")
        return 0 if not failed else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
