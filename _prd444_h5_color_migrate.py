"""
PRD-442 里程碑 2 · H5 端旧色板 → 「晴空诊室」天蓝品牌色全量迁移脚本

替换映射（基于 design-tokens.json 单一真相源）：
  #52c41a / #52C41A  →  #0EA5E9   (brand-500，主色 / 旧 antd-mobile 绿主色)
  #389e0d / #389E0D  →  #0369A1   (brand-700，深色态/激活态)
  #13c2c2 / #13C2C2  →  #38BDF8   (brand-400，次主色/渐变末端)
  #08979c / #08979C  →  #0284C7   (brand-600)
  #5cdbd3 / #5CDBD3  →  #BAE6FD   (brand-200，浅次)
  #95de64 / #95DE64  →  #7DD3FC   (brand-300，浅主)
  #34C759 / #34c759  →  #0EA5E9   (旧 iOS 绿 → 天蓝主)
  #5B6CFF / #5b6cff  →  #0EA5E9   (旧紫主 → 天蓝主)
  #4A5AE8 / #4a5ae8  →  #0284C7   (旧紫 hover → 天蓝深)
  #EEF0FF / #eef0ff  →  #E0F2FE   (旧紫浅底 → 天蓝浅底)
  #8B5CF6 / #8b5cf6  →  #38BDF8   (旧紫渐变末端 → 天蓝)
  E8F7EE             →  E0F2FE   (旧浅绿底 → 天蓝浅底)
  91d5a4             →  7DD3FC   (旧禁用绿 → 浅天蓝)

作用范围：h5-web/src 下所有 .tsx / .ts / .css / .scss 文件
排除：
  - h5-web/src/lib/theme.ts (已手工统一)
  - h5-web/src/app/globals.css (已手工统一)
  - h5-web/src/components/GreenNavBar.tsx (已手工统一)
  - h5-web/src/app/layout.tsx (已手工统一)
"""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
H5_SRC = ROOT / 'h5-web' / 'src'

# 已手工处理的文件，跳过
SKIP_FILES = {
    (H5_SRC / 'lib' / 'theme.ts').resolve(),
    (H5_SRC / 'app' / 'globals.css').resolve(),
    (H5_SRC / 'components' / 'GreenNavBar.tsx').resolve(),
    (H5_SRC / 'app' / 'layout.tsx').resolve(),
}

# 颜色映射（按长 → 短，避免短串误伤）
# 注意：使用大小写不敏感正则
COLOR_MAPPING = [
    # 紫色系（先替换 6 位 hex，避免误伤）
    (r'#5B6CFF\b', '#0EA5E9'),
    (r'#5b6cff\b', '#0EA5E9'),
    (r'#4A5AE8\b', '#0284C7'),
    (r'#4a5ae8\b', '#0284C7'),
    (r'#EEF0FF\b', '#E0F2FE'),
    (r'#eef0ff\b', '#E0F2FE'),
    (r'#8B5CF6\b', '#38BDF8'),
    (r'#8b5cf6\b', '#38BDF8'),

    # 旧 iOS 绿 / theme-color
    (r'#34C759\b', '#0EA5E9'),
    (r'#34c759\b', '#0EA5E9'),

    # 主品牌绿
    (r'#52C41A\b', '#0EA5E9'),
    (r'#52c41a\b', '#0EA5E9'),

    # 深绿
    (r'#389E0D\b', '#0369A1'),
    (r'#389e0d\b', '#0369A1'),

    # 浅绿
    (r'#95DE64\b', '#7DD3FC'),
    (r'#95de64\b', '#7DD3FC'),

    # 主青
    (r'#13C2C2\b', '#38BDF8'),
    (r'#13c2c2\b', '#38BDF8'),

    # 深青
    (r'#08979C\b', '#0284C7'),
    (r'#08979c\b', '#0284C7'),

    # 浅青
    (r'#5CDBD3\b', '#BAE6FD'),
    (r'#5cdbd3\b', '#BAE6FD'),

    # 浅绿底（站点常用）
    (r'#E8F7EE\b', '#E0F2FE'),
    (r'#e8f7ee\b', '#E0F2FE'),

    # 旧禁用绿 → 浅天蓝
    (r'#91D5A4\b', '#7DD3FC'),
    (r'#91d5a4\b', '#7DD3FC'),

    # 浅黄绿 alias（部分页面用 #f6ffed 作为绿底，这里映射到天蓝最浅 brand-50）
    (r'#F6FFED\b', '#F0F9FF'),
    (r'#f6ffed\b', '#F0F9FF'),
]

# 品牌词替换：宾尼小康/宾尼诊所/宾尼健康 → 晴空诊室
BRAND_WORD_MAPPING = [
    ('宾尼小康', '晴空诊室'),
    ('宾尼诊所', '晴空诊室'),
    ('宾尼健康', '晴空诊室'),
]

EXTENSIONS = {'.tsx', '.ts', '.jsx', '.js', '.css', '.scss', '.sass', '.less'}


def should_process(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in EXTENSIONS:
        return False
    if path.resolve() in SKIP_FILES:
        return False
    return True


def migrate_file(path: Path) -> tuple[int, int]:
    """返回 (color_replacements, brand_replacements)"""
    try:
        original = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return 0, 0
    text = original
    color_count = 0
    brand_count = 0

    for pattern, repl in COLOR_MAPPING:
        text, n = re.subn(pattern, repl, text)
        color_count += n

    for old, new in BRAND_WORD_MAPPING:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            brand_count += n

    if text != original:
        path.write_text(text, encoding='utf-8')
    return color_count, brand_count


def main() -> None:
    total_color = 0
    total_brand = 0
    touched_files: list[tuple[str, int, int]] = []
    for root, _dirs, files in os.walk(H5_SRC):
        for fname in files:
            p = Path(root) / fname
            if not should_process(p):
                continue
            c, b = migrate_file(p)
            if c or b:
                rel = p.relative_to(ROOT).as_posix()
                touched_files.append((rel, c, b))
                total_color += c
                total_brand += b
    print('=' * 60)
    print(f'PRD-442 H5 端旧色板/品牌词全量迁移完成')
    print('=' * 60)
    print(f'累计色值替换: {total_color}')
    print(f'累计品牌词替换: {total_brand}')
    print(f'触达文件数: {len(touched_files)}')
    print('-' * 60)
    for rel, c, b in touched_files:
        print(f'  {rel}  色值×{c}  品牌词×{b}')


if __name__ == '__main__':
    main()
