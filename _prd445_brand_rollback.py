"""
PRD-445 · 「晴空诊室」→「宾尼小康」全域品牌名回滚脚本
- 替换规则（按顺序执行）：
    1. "晴空诊室" → "宾尼小康"
    2. 剩余的"晴空"（如"晴空蓝"）→ "宾尼"
- 处理范围：限定在影响盘点清单中列出的文件类型
- 文件名重命名：含"晴空"的两个 user_docs 手册文件名也要改
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INCLUDE_EXT = {
    '.tsx', '.ts', '.jsx', '.js',
    '.css', '.scss', '.sass', '.less', '.wxss',
    '.json', '.md', '.html', '.htm',
    '.dart', '.py', '.txt', '.mdc',
    '.yml', '.yaml',
}

EXCLUDE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.next', 'dist', 'build',
    '_apk_download_363', '_apk_download_367', 'apk_download', 'apk_downloads',
    'ipa_download', '_prd442_android_dl', '_prd443_android_dl',
    '.pytest_cache', '.tools', 'verify-miniprogram',
    'build_artifacts', '_deploy_tmp', 'deploy', 'mem',
    'ui_design_outputs', 'uploads',
}

REPLACEMENTS = [
    ('晴空诊室', '宾尼小康'),
    ('晴空', '宾尼'),
]

RENAME_FILES = [
    ('user_docs/H5端晴空诊室品牌色全量落地_PRD442_里程碑2_用户体验手册.md',
     'user_docs/H5端宾尼小康品牌色全量落地_PRD442_里程碑2_用户体验手册.md'),
    ('user_docs/菜单模式_晴空诊室风格_PRD442_用户体验手册.md',
     'user_docs/菜单模式_宾尼小康风格_PRD442_用户体验手册.md'),
]


def should_skip_dir(d: Path) -> bool:
    return d.name in EXCLUDE_DIRS


def should_process_file(p: Path) -> bool:
    if p.suffix.lower() not in INCLUDE_EXT:
        return False
    if p.name == os.path.basename(__file__):
        return False
    return True


def replace_in_file(p: Path) -> int:
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        return 0
    if '晴空' not in text:
        return 0
    new_text = text
    total = 0
    for old, new in REPLACEMENTS:
        cnt = new_text.count(old)
        if cnt:
            new_text = new_text.replace(old, new)
            total += cnt
    if new_text != text:
        p.write_text(new_text, encoding='utf-8')
    return total


def walk_and_replace():
    grand_total = 0
    files_changed = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if not should_process_file(p):
                continue
            n = replace_in_file(p)
            if n > 0:
                grand_total += n
                files_changed += 1
                rel = p.relative_to(ROOT)
                print(f"[REPLACED {n:>3}] {rel}")
    print(f"\n== 共修改 {files_changed} 个文件，替换 {grand_total} 处 ==")


def rename_files():
    for src, dst in RENAME_FILES:
        sp = ROOT / src
        dp = ROOT / dst
        if sp.exists():
            sp.rename(dp)
            print(f"[RENAMED] {src} -> {dst}")


if __name__ == '__main__':
    walk_and_replace()
    rename_files()
    print("Done.")
