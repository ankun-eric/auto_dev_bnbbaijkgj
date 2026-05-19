"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 容器内最终清理：手动 DELETE 残留的 3 条非 font_* KV"""
import os
from sqlalchemy import create_engine, text

url = (
    os.environ.get("DATABASE_URL", "")
    .replace("+aiomysql", "+pymysql")
    .replace("+asyncmy", "+pymysql")
)
e = create_engine(url)
with e.connect() as c:
    r = c.execute(text(
        "DELETE FROM system_configs "
        "WHERE config_key LIKE 'home_%' AND config_key NOT LIKE 'home_font_%'"
    ))
    c.commit()
    print("DELETE rowcount:", r.rowcount)

    remain = c.execute(text(
        "SELECT COUNT(*) FROM system_configs "
        "WHERE config_key LIKE 'home_%' AND config_key NOT LIKE 'home_font_%'"
    )).scalar()
    print("Remaining non-font home_* KV (expect=0):", remain)
