"""
PRD-442 H5 端 8 位 hex（带 alpha 后缀）旧色补充清退（第三轮）
形如 #52c41a15 / #52c41a20 / #13c2c220 / #5B6CFF15 等。
"""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
H5_SRC = ROOT / 'h5-web' / 'src'

# 8位 hex 替换：保留 alpha 段，替换主色 6 位
# 旧绿 52c41a → 0EA5E9
# 旧深绿 389e0d → 0369A1
# 旧浅绿 95de64 → 7DD3FC
# 旧主青 13c2c2 → 38BDF8
# 旧深青 08979c → 0284C7
# 旧浅青 5cdbd3 → BAE6FD
# 旧紫主 5B6CFF → 0EA5E9
# 旧紫深 4A5AE8 → 0284C7
# 旧紫浅 EEF0FF → E0F2FE
# 旧紫渐变 8B5CF6 → 38BDF8
# 旧 antd 浅绿 b7eb8f → BAE6FD
# 旧 antd 浅红 ff4d4f→ 保留（语义色，DANGER 不动）

MAP_8HEX = {
    '52c41a': '0EA5E9',
    '52C41A': '0EA5E9',
    '389e0d': '0369A1',
    '389E0D': '0369A1',
    '95de64': '7DD3FC',
    '95DE64': '7DD3FC',
    '13c2c2': '38BDF8',
    '13C2C2': '38BDF8',
    '08979c': '0284C7',
    '08979C': '0284C7',
    '5cdbd3': 'BAE6FD',
    '5CDBD3': 'BAE6FD',
    '5b6cff': '0EA5E9',
    '5B6CFF': '0EA5E9',
    '4a5ae8': '0284C7',
    '4A5AE8': '0284C7',
    'eef0ff': 'E0F2FE',
    'EEF0FF': 'E0F2FE',
    '8b5cf6': '38BDF8',
    '8B5CF6': '38BDF8',
    'b7eb8f': 'BAE6FD',
    'B7EB8F': 'BAE6FD',
    '34c759': '0EA5E9',
    '34C759': '0EA5E9',
    'e8f7ee': 'E0F2FE',
    'E8F7EE': 'E0F2FE',
    '91d5a4': '7DD3FC',
    '91D5A4': '7DD3FC',
    'f0faf0': 'F0F9FF',
    'F0FAF0': 'F0F9FF',
    'e8f8f5': 'E0F2FE',
    'E8F8F5': 'E0F2FE',
}

# 单独命中：linear-gradient 内的旧绿青组合
EXTENSIONS = {'.tsx', '.ts', '.jsx', '.js', '.css', '.scss'}


def migrate_8hex(text: str) -> tuple[str, int]:
    """匹配 #XXXXXXAA（8 位 hex，AA 为 2 位 alpha）形式"""
    pattern = re.compile(r'#([0-9a-fA-F]{6})([0-9a-fA-F]{2})\b')
    def repl(m: re.Match) -> str:
        body = m.group(1)
        alpha = m.group(2)
        if body in MAP_8HEX:
            return f'#{MAP_8HEX[body]}{alpha}'
        return m.group(0)
    return pattern.subn(repl, text)


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
            new_text, n = migrate_8hex(text)
            if n:
                p.write_text(new_text, encoding='utf-8')
                rel = p.relative_to(ROOT).as_posix()
                print(f'  {rel}  ×{n}')
                total += n
                files_touched += 1
    print('-' * 60)
    print(f'第三轮 8 位 hex 清退: {total} 处替换 / {files_touched} 个文件')


if __name__ == '__main__':
    main()
