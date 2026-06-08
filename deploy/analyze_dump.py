import re, sys

with open(r'C:\buf\db_bak\bini_health_backup_20260607_144728.sql', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find all table names mentioned in INSERT statements
pattern = r"INSERT INTO `(\w+)`"
inserts = re.findall(pattern, content)
tables = list(dict.fromkeys(inserts))
print(f"共 {len(tables)} 个表有 INSERT 数据:")
for t in tables:
    count = inserts.count(t)
    print(f"  {t} ({count} 条 INSERT)")

# Sample first INSERT for each table
print("\n" + "=" * 60)
print("各表首个 INSERT 语句 (前 250 字符)")
print("=" * 60)
for t in tables:
    idx = content.find(f"INSERT INTO `{t}`")
    if idx >= 0:
        end = min(idx + 250, len(content))
        print(f"\n--- {t} ---")
        print(content[idx:end])
        print()
