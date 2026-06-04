import pymysql

conn = pymysql.connect(
    host="gz-cdb-nniq1lmp.sql.tencentcdb.com",
    port=27082,
    user="root",
    password="xiaokang989aab",
    database="bini_health"
)
c = conn.cursor()

# Show columns
c.execute("SHOW COLUMNS FROM merchant_stores")
cols = [r[0] for r in c.fetchall()]
print("=== 门店表字段 ===")
print(cols)

# Show data
c.execute("SELECT * FROM merchant_stores")
rows = c.fetchall()
print(f"\n=== merchant_stores ({len(rows)} rows) ===")
for i, row in enumerate(rows):
    print(f"\n--- 门店 {i+1} ---")
    for j, col in enumerate(cols):
        val = row[j]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        print(f"  {col}: {val}")

# Also show merchant_profiles
c.execute("SELECT * FROM merchant_profiles")
profiles = c.fetchall()
print(f"\n=== merchant_profiles ({len(profiles)} rows) ===")
c.execute("SHOW COLUMNS FROM merchant_profiles")
pcols = [r[0] for r in c.fetchall()]
for i, row in enumerate(profiles):
    print(f"\n--- 商家档案 {i+1} ---")
    for j, col in enumerate(pcols):
        val = row[j]
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        if col in ('avatar_url', 'business_license_url'):
            val = str(val)[:80] if val else 'None'
        print(f"  {col}: {val}")

conn.close()
