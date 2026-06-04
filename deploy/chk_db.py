import pymysql

conn = pymysql.connect(
    host="gz-cdb-nniq1lmp.sql.tencentcdb.com",
    port=27082,
    user="root",
    password="xiaokang989aab",
    database="bini_health"
)
c = conn.cursor()

tables = [
    "merchant_stores",
    "merchant_profiles", 
    "merchant_store_memberships",
    "merchant_categories",
    "merchant_role_templates",
    "users",
    "staff_wechat_bindings",
]

print("=== 门店相关数据 ===")
for t in tables:
    c.execute("SELECT COUNT(*) FROM " + t)
    cnt = c.fetchone()[0]
    print(f"{t}: {cnt} rows")
    if cnt > 0:
        c.execute("SELECT * FROM " + t + " LIMIT 2")
        for r in c.fetchall():
            print(f"  sample: {r[:5]}")

conn.close()
