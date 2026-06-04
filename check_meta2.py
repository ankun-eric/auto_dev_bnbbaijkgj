import asyncio, json, sys
sys.path.insert(0, "backend")

from app.core.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as db:
        # Check all recent chat messages for report_interpret sessions
        result = await db.execute(text("""
            SELECT cm.id, cm.session_id, cm.role, cm.message_metadata, cm.content, cm.created_at,
                   cs.session_type
            FROM chat_messages cm
            JOIN chat_sessions cs ON cs.id = cm.session_id
            WHERE cs.session_type = 'report_interpret'
            ORDER BY cm.created_at DESC
            LIMIT 20
        """))
        rows = result.fetchall()
        print(f"=== Total report_interpret messages found: {len(rows)} ===\n")
        for r in rows:
            meta = r[3]
            content_preview = (r[4] or "")[:80]
            print(f"msg_id={r[0]} session={r[1]} role={r[2]} created={r[5]} type={r[6]}")
            print(f"  content_preview={content_preview}")
            if meta:
                if isinstance(meta, str):
                    meta = json.loads(meta)
                print(f"  card_type={meta.get('card_type', 'NOT_FOUND')}")
                print(f"  meta_keys={list(meta.keys())}")
            else:
                print("  meta=None")
            print()

        # Check CheckupReport table
        result2 = await db.execute(text("SELECT COUNT(*) FROM checkup_reports"))
        count = result2.scalar()
        print(f"=== Total CheckupReport records: {count} ===\n")

        # Check ReportHistory table
        result3 = await db.execute(text("SELECT COUNT(*) FROM report_history"))
        count3 = result3.scalar()
        print(f"=== Total ReportHistory records: {count3} ===\n")

        # Check session report_id
        result4 = await db.execute(text("""
            SELECT id, session_type, report_id, created_at
            FROM chat_sessions
            WHERE session_type = 'report_interpret'
            ORDER BY created_at DESC
            LIMIT 10
        """))
        rows4 = result4.fetchall()
        print(f"=== report_interpret sessions: ===")
        for r in rows4:
            print(f"  session_id={r[0]} type={r[1]} report_id={r[2]} created={r[3]}")

asyncio.run(check())
