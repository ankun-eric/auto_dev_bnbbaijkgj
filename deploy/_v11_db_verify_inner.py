"""[PRD-LEGACY-HOME-CLEANUP-V1.1] 容器内验证脚本（在 backend 容器内执行）"""
import os
from sqlalchemy import create_engine, text

url = (
    os.environ.get("DATABASE_URL", "")
    .replace("+aiomysql", "+pymysql")
    .replace("+asyncmy", "+pymysql")
)
e = create_engine(url)
with e.connect() as c:
    r1 = c.execute(text("SELECT COUNT(*) FROM app_settings WHERE `key`='page_style'")).scalar()
    r2 = c.execute(text("SELECT COUNT(*) FROM system_configs WHERE config_key LIKE 'home_%' AND config_key NOT LIKE 'home_font_%'")).scalar()
    r3 = c.execute(text("SELECT COUNT(*) FROM system_configs WHERE config_key LIKE 'home_font_%'")).scalar()
    r4 = c.execute(text("SHOW TABLES LIKE 'banner_migration_log_20260519'")).fetchone()
    r5 = c.execute(text("SELECT `value` FROM app_settings WHERE `key`='_migration_done.prd_legacy_home_cleanup_v11'")).scalar()
    r6 = c.execute(text("SELECT COUNT(*) FROM home_banners WHERE link_url='/home'")).scalar()
    r7 = c.execute(text("SELECT COUNT(*) FROM home_banners WHERE link_url='/ai-home'")).scalar()
    r8 = c.execute(text(
        "SELECT COUNT(*) FROM home_banners "
        "WHERE (link_url LIKE '/home/menu/%' OR link_url LIKE '/menu-mode/%') AND is_visible=TRUE"
    )).scalar()
    print("A page_style KV count (expect=0):", r1)
    print("B home_* non-font KV count (expect=0):", r2)
    print("C home_font_* KV count (expect>=5):", r3)
    print("D banner_migration_log_20260519 table:", r4)
    print("E migration flag:", r5)
    print("F banners with link_url=/home (expect=0):", r6)
    print("G banners with link_url=/ai-home:", r7)
    print("H visible banners pointing to legacy path (expect=0):", r8)
    rows = c.execute(text(
        "SELECT config_key, config_value FROM system_configs "
        "WHERE config_key LIKE 'home_%' AND config_key NOT LIKE 'home_font_%'"
    )).fetchall()
    print("I residual non-font home_* KV rows:", [dict(_r._mapping) for _r in rows])
