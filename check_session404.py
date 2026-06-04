"""Check session details."""
import asyncio
from app.core.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as db:
        print('=== Latest sessions ===')
        r = await db.execute(text('SELECT id, user_id, session_type, title, report_id, family_member_id, created_at, updated_at FROM chat_sessions ORDER BY id DESC LIMIT 10'))
        rows = r.fetchall()
        for row in rows:
            print(f'Session {row[0]}: user={row[1]}, type={row[2]}, title="{row[3]}", report_id={row[4]}, fmid={row[5]}, created={row[6]}, updated={row[7]}')

        print()
        print('=== Messages in session 404 ===')
        r2 = await db.execute(text("SELECT id, role, LEFT(content, 200), LEFT(CAST(message_metadata AS CHAR), 400), image_urls, created_at FROM chat_messages WHERE session_id=404 ORDER BY id"))
        msgs = r2.fetchall()
        for msg in msgs:
            print(f'  Msg {msg[0]}: role={msg[1]}, created={msg[5]}')
            print(f'    content: {msg[2]}')
            print(f'    meta: {msg[3]}')
            print(f'    images: {msg[4]}')

        print()
        print('=== CheckupReport (all) ===')
        r3 = await db.execute(text("SELECT id, user_id, title, status, interpret_session_id, created_at FROM checkup_reports ORDER BY id DESC LIMIT 10"))
        rows3 = r3.fetchall()
        for row in rows3:
            print(f'  Report {row[0]}: user={row[1]}, title={row[2]}, status={row[3]}, session={row[4]}, created={row[5]}')
        if not rows3:
            print('  (none)')

        print()
        print('=== ReportHistory (all) ===')
        r4 = await db.execute(text("SELECT id, user_id, report_name, created_at FROM report_history ORDER BY id DESC LIMIT 10"))
        rows4 = r4.fetchall()
        for row in rows4:
            print(f'  History {row[0]}: user={row[1]}, name={row[2]}, created={row[3]}')
        if not rows4:
            print('  (none)')

asyncio.run(main())
