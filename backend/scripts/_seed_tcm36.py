"""[PRD-TCM-DRAWER-V12-BUG2 2026-05-20] 一次性手动补数脚本：强制刷新 36 题模板

用途
----
当线上 docker 容器内 questionnaire_template id=3 的题目数 != 36 时，
在 docker exec 内执行本脚本一次即可强制刷新到 36 题（同时回填默认关键词）。

用法
----
docker exec -i <backend_container> python -m backend.scripts._seed_tcm36
或者：
docker exec -i <backend_container> python backend/scripts/_seed_tcm36.py

幂等性
------
- 反复执行不会破坏数据
- 每次都会软重建 tcm_constitution 模板下的 questions（先删后插）
- 历史 questionnaire_answer 不动（保留只读）
"""

import asyncio
import json
import sys
from pathlib import Path


def _ensure_app_on_path() -> None:
    here = Path(__file__).resolve()
    backend_root = here.parent.parent  # .../backend
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


async def _main() -> int:
    _ensure_app_on_path()
    from app.core.database import async_session
    from app.services.prd_tcm36_drawer_v12_migration import run_migration_with_session

    stats = await run_migration_with_session(async_session)
    print("[_seed_tcm36] done stats=" + json.dumps(stats, ensure_ascii=False))
    inserted = int(stats.get("questions_inserted", 0) or 0)
    return 0 if inserted == 36 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
