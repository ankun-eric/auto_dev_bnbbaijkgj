import asyncio, json, sys
sys.path.insert(0, "backend")

from app.core.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as db:
        # Check CheckupReport records
        result = await db.execute(text("""
            SELECT id, user_id, family_member_id, title, report_date, status,
                   interpret_session_id, file_url, file_urls, created_at
            FROM checkup_reports
            ORDER BY created_at DESC
            LIMIT 10
        """))
        rows = result.fetchall()
        print(f"=== CheckupReport records (latest 10): ===\n")
        for r in rows:
            file_urls_val = r[8]
            if isinstance(file_urls_val, str):
                try:
                    file_urls_val = json.loads(file_urls_val)
                except:
                    pass
            print(f"  id={r[0]} user={r[1]} member={r[2]} title={r[3]}")
            print(f"  date={r[4]} status={r[5]} session_id={r[6]}")
            print(f"  file_url={r[7]}")
            print(f"  file_urls type={type(file_urls_val).__name__} val={str(file_urls_val)[:100]}")
            print(f"  created={r[9]}")
            print()

        # Check chat_sessions for report_interpret type - check family_member_id
        result2 = await db.execute(text("""
            SELECT id, session_type, report_id, family_member_id, user_id, created_at
            FROM chat_sessions
            WHERE session_type = 'report_interpret'
            ORDER BY created_at DESC
            LIMIT 10
        """))
        rows2 = result2.fetchall()
        print(f"=== chat_sessions (report_interpret): ===\n")
        for r in rows2:
            print(f"  session_id={r[0]} type={r[1]} report_id={r[2]} family_member_id={r[3]} user={r[4]} created={r[5]}")

        # Check MedicalRecord
        result3 = await db.execute(text("SELECT COUNT(*) FROM medical_records WHERE category = 'checkup_report'"))
        count3 = result3.scalar()
        print(f"\n=== MedicalRecord (checkup_report) count: {count3} ===")

asyncio.run(check())
