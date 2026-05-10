"""
PRD-442 H5 端 rgb/rgba 旧绿色变体补充清退（第二轮）
- rgba(82,196,26,*)  → rgba(56,189,248,*)   (旧绿 → brand-400 天蓝)
- rgb(82,196,26)     → rgb(56,189,248)
- rgba(19,194,194,*) → rgba(56,189,248,*)   (旧青 → brand-400)
- rgb(19,194,194)    → rgb(56,189,248)
- rgba(91,108,255,*) → rgba(14,165,233,*)   (旧紫 → brand-500)
"""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
H5_SRC = ROOT / 'h5-web' / 'src'

PATTERNS = [
    (re.compile(r'rgba\(\s*82,\s*196,\s*26\s*'), 'rgba(56,189,248'),
    (re.compile(r'rgb\(\s*82,\s*196,\s*26\s*\)'), 'rgb(56,189,248)'),
    (re.compile(r'rgba\(\s*19,\s*194,\s*194\s*'), 'rgba(56,189,248'),
    (re.compile(r'rgb\(\s*19,\s*194,\s*194\s*\)'), 'rgb(56,189,248)'),
    (re.compile(r'rgba\(\s*91,\s*108,\s*255\s*'), 'rgba(14,165,233'),
    (re.compile(r'rgb\(\s*91,\s*108,\s*255\s*\)'), 'rgb(14,165,233)'),
]

EXTENSIONS = {'.tsx', '.ts', '.jsx', '.js', '.css', '.scss'}


def main() -> None:
    total = 0
    files_touched = 0
    for root, _dirs, files in os.walk(H5_SRC):
        for fname in files:
            p = Path(root) / fname
            if p.suffix.lower() not in EXTENSIONS:
                continue
            try:
                text = p.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            original = text
            count = 0
            for pat, repl in PATTERNS:
                text, n = pat.subn(repl, text)
                count += n
            if text != original:
                p.write_text(text, encoding='utf-8')
                rel = p.relative_to(ROOT).as_posix()
                print(f'  {rel}  ×{count}')
                total += count
                files_touched += 1
    print('-' * 60)
    print(f'第二轮 rgb/rgba 清退: {total} 处替换 / {files_touched} 个文件')


if __name__ == '__main__':
    main()
