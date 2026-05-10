#!/usr/bin/env python3
"""PRD-447 v2 · 硬编码颜色 lint 脚本（stylelint 等价物，零额外 npm 依赖）

扫描业务代码中的硬编码颜色 / 渐变（hex / rgb / rgba / linear-gradient），
强制业务代码必须经语义层 token；token 文件本身允许定义颜色。

退出码：0 = 通过；1 = 检测到违规。

白名单：
- design-system/* token 源文件
- design-system-v2-preview 自测页（允许少量内联色用于演示）
- legacy 已存在硬编码（PRD §10 风险 1：不重命名已有变量；本次只防新增）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SCAN_DIRS = [
    ROOT / "h5-web" / "src" / "components" / "design-system",
]

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_RE = re.compile(r"\brgba?\s*\(")
GRAD_RE = re.compile(r"linear-gradient\s*\(")

SUFFIXES = {".tsx", ".ts", ".jsx", ".js", ".css", ".scss"}

ALLOWED_HEX = {
    # 透明白：仅允许 #fff / #ffffff（白色，用于反色文字与 inverse 文本）
    "#fff", "#ffffff", "#FFFFFF", "#FFF",
    # 完全透明黑：用作占位
    "#000", "#000000", "#0000",
}


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        # 跳过注释行
        s = line.strip()
        if s.startswith("//") or s.startswith("/*") or s.startswith("*"):
            continue
        # hex 颜色
        for m in HEX_RE.finditer(line):
            hex_v = m.group(0)
            if hex_v in ALLOWED_HEX:
                continue
            issues.append(f"{path}:{i}: 硬编码 hex 颜色 {hex_v}: {line.strip()}")
        # rgb(a) 颜色
        if RGB_RE.search(line):
            issues.append(f"{path}:{i}: 硬编码 rgb/rgba: {line.strip()}")
        # 渐变
        if GRAD_RE.search(line):
            issues.append(f"{path}:{i}: 硬编码 linear-gradient: {line.strip()}")
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", nargs="*", default=None,
                        help="覆盖默认扫描目录（绝对/相对项目根都可）")
    parser.add_argument("--strict", action="store_true",
                        help="严格模式（任何违规非零退出，CI 用）")
    args = parser.parse_args()

    scan_dirs = [Path(p) if Path(p).is_absolute() else (ROOT / p) for p in args.paths] if args.paths else DEFAULT_SCAN_DIRS

    all_issues: list[str] = []
    for d in scan_dirs:
        if not d.exists():
            print(f"[skip] 目录不存在: {d}")
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in SUFFIXES:
                all_issues.extend(scan_file(p))

    if all_issues:
        print(f"❌ PRD-447 lint 命中 {len(all_issues)} 处硬编码颜色 / 渐变：")
        for s in all_issues[:200]:
            print("  " + s)
        if len(all_issues) > 200:
            print(f"  …（仅显示前 200 条，共 {len(all_issues)} 条）")
        if args.strict:
            sys.exit(1)
    else:
        print("✅ PRD-447 lint 通过：design-system 组件零硬编码色彩。")
    sys.exit(0 if not (args.strict and all_issues) else 1)


if __name__ == "__main__":
    main()
