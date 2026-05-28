"""Clean old test data from report-related tables."""
import asyncio
from app.core.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as db:
        print("=== Cleaning old data ===")
        
        # 1. Delete all CheckupReport records (all are from old scheme, April 24-28)
        r1 = await db.execute(text("SELECT COUNT(*) FROM checkup_reports"))
        count1 = r1.scalar()
        print(f"  CheckupReport records to delete: {count1}")
        await db.execute(text("DELETE FROM checkup_reports"))
        
        # 2. Delete all ReportHistory records (should be 0 already)
        r2 = await db.execute(text("SELECT COUNT(*) FROM report_history"))
        count2 = r2.scalar()
        print(f"  ReportHistory records to delete: {count2}")
        await db.execute(text("DELETE FROM report_history"))
        
        # 3. Delete MedicalRecord/MedicalRecordFile with source='ai_interpret'
        r3 = await db.execute(text("SELECT COUNT(*) FROM medical_records WHERE source='ai_interpret'"))
        count3 = r3.scalar()
        print(f"  MedicalRecord (ai_interpret) records to delete: {count3}")
        if count3 > 0:
            await db.execute(text("DELETE FROM medical_record_files WHERE medical_record_id IN (SELECT id FROM medical_records WHERE source='ai_interpret')"))
            await db.execute(text("DELETE FROM medical_records WHERE source='ai_interpret'"))
        
        # 4. Clear report_id from ChatSessions that referenced old reports
        r4 = await db.execute(text("UPDATE chat_sessions SET report_id = NULL WHERE report_id IS NOT NULL"))
        print(f"  ChatSession report_id cleared: {r4.rowcount} rows")
        
        await db.commit()
        print()
        print("=== Done! All old data cleaned. ===")

asyncio.run(main())
