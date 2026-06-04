import asyncio, json, sys
sys.path.insert(0, "backend")

from app.core.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as db:
        result = await db.execute(text("""
            SELECT cm.id, cm.session_id, cm.message_metadata, cm.created_at
            FROM chat_messages cm
            JOIN chat_sessions cs ON cs.id = cm.session_id
            WHERE cs.session_type = 'report_interpret'
            AND cm.role = 'assistant'
            ORDER BY cm.created_at DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        for r in rows:
            meta = r[2]
            print(f"msg_id={r[0]} session={r[1]} created={r[3]}")
            if meta:
                if isinstance(meta, str):
                    meta = json.loads(meta)
                print(f"  card_type={meta.get('card_type', 'NOT_FOUND')}")
                print(f"  meta_keys={list(meta.keys())}")
            else:
                print("  meta=None")
            print()

asyncio.run(check())
