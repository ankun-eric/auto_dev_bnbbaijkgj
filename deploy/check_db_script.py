import sys
sys.path.insert(0, "/app")
from sqlalchemy import create_engine, text
import os

db_url = os.environ.get("DATABASE_URL", "mysql+aiomysql://root:xiaokang989aab@gz-cdb-nniq1lmp.sql.tencentcdb.com:27082/bini_health")
db_url = db_url.replace("mysql+aiomysql://", "mysql+pymysql://")
engine = create_engine(db_url)
with engine.connect() as conn:
    rows = conn.execute(text("SELECT id, username, phone, role, is_active FROM users LIMIT 10")).fetchall()
    for r in rows:
        print(r)
    count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    print(f"Total users: {count}")
engine.dispose()
