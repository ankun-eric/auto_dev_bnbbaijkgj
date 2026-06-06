import re
import os

content = open('backend/app/models/models.py', encoding='utf-8').read()

blocks = re.split(r'\n(?=class \w+)', content)
for block in blocks:
    tn = re.search(r'__tablename__\s*=\s*"(.+?)"', block)
    dts = re.findall(r'(\w+)\s*=\s*Column\([^)]*DateTime[^)]*\)', block, re.DOTALL)
    if tn and dts:
        print(f'{tn.group(1)}: {dts}')
