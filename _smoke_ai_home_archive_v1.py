"""[BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1] smoke 验证：
- DB 中 ai_home_config.input.family_consult.archive_path 应为 /health-profile
- DB 中 ai_home_config.func_grid.items[g3].target_path 应为 /health-profile
"""

import asyncio
import json
from sqlalchemy import text
from app.core.database import async_session


async def main():
    async with async_session() as db:
        r = await db.execute(
            text("SELECT value FROM app_settings WHERE `key` = 'ai_home_config'")
        )
        row = r.fetchone()
        if not row:
            print("[smoke] FAIL: no ai_home_config row in app_settings")
            return 1
        try:
            cfg = json.loads(row[0])
        except Exception as e:
            print(f"[smoke] FAIL: invalid json: {e}")
            return 1
        ap = cfg.get("input", {}).get("family_consult", {}).get("archive_path")
        items = cfg.get("func_grid", {}).get("items", [])
        g3 = next((it for it in items if it.get("id") == "g3"), None)
        tp = g3.get("target_path") if g3 else None

        print(f"[smoke] archive_path = {ap!r}")
        print(f"[smoke] g3.target_path = {tp!r}")

        ok_ap = ap == "/health-profile"
        ok_tp = tp == "/health-profile"
        if ok_ap and ok_tp:
            print("[smoke] PASS ✅ all paths are /health-profile")
            return 0
        else:
            print(f"[smoke] FAIL ❌ ok_ap={ok_ap} ok_tp={ok_tp}")
            return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
