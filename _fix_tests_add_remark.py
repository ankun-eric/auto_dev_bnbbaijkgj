"""一次性给所有现有 home_safety 测试中的 devices/bind 调用补充 remark 字段。
[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29]
"""
import os
import re
import sys

ROOT = os.path.dirname(__file__)
TESTS_DIR = os.path.join(ROOT, "backend", "tests")

TARGETS = [
    "test_home_safety_v1.py",
    "test_home_safety_v2.py",
    "test_home_safety_v2_revision.py",
    "test_home_safety_gwid_ephone_v1.py",
    "test_home_safety_callback_datatype_v1.py",
    "test_my_devices_v1_20260521.py",
]

# 匹配整个 json={ ... } 中包含 device_sn 但不含 remark 的体
# 这里使用 emergency_phone 行作为锚点：在该行后插入 remark
ANCHOR_PAT = re.compile(
    r'("emergency_phone"\s*:\s*"[^"]+"\s*,?)([^\}]*?\})',
    re.DOTALL,
)


def patch_text(text: str) -> tuple[str, int]:
    n = 0
    out_parts = []
    i = 0
    while True:
        m = ANCHOR_PAT.search(text, i)
        if not m:
            out_parts.append(text[i:])
            break
        whole = m.group(0)
        # 检查这一整段中是否已经包含 "remark"
        if '"remark"' in whole:
            out_parts.append(text[i:m.end()])
            i = m.end()
            continue
        # 仅修改 devices/bind 调用相关的代码（向上找最近 50 字符是否提到 bind）
        ctx_start = max(0, m.start() - 200)
        ctx = text[ctx_start:m.start()]
        if "/devices/bind" not in ctx and "_bind(" not in ctx:
            out_parts.append(text[i:m.end()])
            i = m.end()
            continue
        # 在 emergency_phone 的逗号后追加 remark
        ep = m.group(1)
        rest = m.group(2)
        if not ep.rstrip().endswith(","):
            ep = ep.rstrip() + ", "
        injection = ep + ' "remark": "测试备注",'
        out_parts.append(text[i:m.start()] + injection + rest)
        n += 1
        i = m.end()
    return "".join(out_parts), n


total = 0
for fn in TARGETS:
    p = os.path.join(TESTS_DIR, fn)
    if not os.path.isfile(p):
        print(f"SKIP missing: {p}")
        continue
    with open(p, "r", encoding="utf-8") as f:
        s = f.read()
    new_s, n = patch_text(s)
    if n > 0:
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_s)
        print(f"{fn}: patched {n} bind calls")
        total += n
    else:
        print(f"{fn}: no change")

print(f"TOTAL: {total}")
