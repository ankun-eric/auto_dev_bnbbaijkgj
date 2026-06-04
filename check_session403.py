import asyncio, json, sys
sys.path.insert(0, "backend")

from app.core.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as db:
        # Check session 403
        result = await db.execute(text("""
            SELECT id, session_type, report_id, family_member_id, user_id, title, created_at, status
            FROM chat_sessions
            WHERE id = 403
        """))
        row = result.fetchone()
        if row:
            print(f"Session 403:")
            print(f"  type={row[1]} report_id={row[2]} family_member_id={row[3]}")
            print(f"  user={row[4]} title={row[5]} created={row[6]} status={row[7]}")
        else:
            print("Session 403 not found")

        # Check messages in session 403
        result2 = await db.execute(text("""
            SELECT id, role, content, message_metadata, created_at
            FROM chat_messages
            WHERE session_id = 403
            ORDER BY created_at
        """))
        rows2 = result2.fetchall()
        print(f"\nMessages in session 403: {len(rows2)}")
        for r in rows2:
            meta = r[3]
            content = (r[2] or "")[:120]
            print(f"  msg_id={r[0]} role={r[1]} created={r[4]}")
            print(f"    content: {content}")
            if meta:
                if isinstance(meta, str):
                    meta = json.loads(meta)
                print(f"    card_type={meta.get('card_type', 'NOT_FOUND')}")
                print(f"    meta_keys={list(meta.keys())}")
            else:
                print(f"    meta=None")
            print()

        # Also check ALL sessions created after May 24, 2026
        result3 = await db.execute(text("""
            SELECT id, session_type, report_id, family_member_id, user_id, title, created_at
            FROM chat_sessions
            WHERE created_at >= '2026-05-24 00:00:00'
            AND session_type = 'report_interpret'
            ORDER BY created_at DESC
        """))
        rows3 = result3.fetchall()
        print(f"\n=== report_interpret sessions after 2026-05-24: {len(rows3)} ===")
        for r in rows3:
            print(f"  session={r[0]} type={r[1]} report_id={r[2]} member={r[3]} user={r[4]} title={r[5]} created={r[6]}")

asyncio.run(check())
