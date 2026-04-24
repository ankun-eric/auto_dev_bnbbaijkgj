"""强制执行 products 表的 v1.0 迁移：
- ADD COLUMN marketing_badges JSON NULL
- DROP COLUMN valid_start_date
- DROP COLUMN valid_end_date
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd

DB = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
BACKEND = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"
MYSQL = f"docker exec {DB} mysql -uroot -pbini_health_2026 bini_health"

SQLS = [
    "ALTER TABLE products ADD COLUMN marketing_badges JSON NULL",
    "ALTER TABLE products DROP COLUMN valid_start_date",
    "ALTER TABLE products DROP COLUMN valid_end_date",
]

ssh = create_client()
try:
    for sql in SQLS:
        print(f'>> {sql}')
        out, err, code = run_cmd(ssh, f"{MYSQL} -e '{sql}' 2>&1", timeout=30)
        print(out)
        if err:
            print('STDERR:', err)

    print('\n=== verify ===')
    out, _, _ = run_cmd(
        ssh,
        f"{MYSQL} -e 'SELECT COLUMN_NAME FROM information_schema.columns "
        f'WHERE TABLE_SCHEMA="bini_health" AND TABLE_NAME="products" '
        f'AND (COLUMN_NAME LIKE "%valid_%_date" OR COLUMN_NAME="marketing_badges")\'',
        timeout=30,
    )
    print(out)

    print('\n=== restart backend ===')
    out, _, _ = run_cmd(ssh, f"docker restart {BACKEND}", timeout=60)
    print(out)
finally:
    ssh.close()
