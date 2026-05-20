"""[BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1 2026-05-21]
AI 对话主页 "查看档案 ›" 点击 404（跨端档案路径统一）数据迁移脚本。

主要工作：扫描 app_settings 表中 key='ai_home_config' 的 JSON 配置，
将其中残留的旧路径修正为新路径 /health-profile：

1. input.family_consult.archive_path 若 == '/health-records' → '/health-profile'
2. func_grid.items[*].target_path 若 == '/health-archive' → '/health-profile'

执行策略：
- 正向白名单：仅扫描 key='ai_home_config' 的记录
- 字段路径精准：仅替换上述两个字段路径
- 幂等执行：已经是 /health-profile 则跳过；脚本可重复执行不出错
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


OLD_ARCHIVE_PATH = "/health-records"
OLD_GRID_TARGET = "/health-archive"
NEW_PATH = "/health-profile"
CONFIG_KEY = "ai_home_config"


async def _table_exists(db, table: str) -> bool:
    row = await db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :t"
        ),
        {"t": table},
    )
    return int(row.scalar() or 0) > 0


def _fix_config(cfg: Any) -> tuple[Any, int, int]:
    """对单条 ai_home_config JSON 进行精准修正，返回 (新对象, archive_fix_cnt, grid_fix_cnt)。"""
    archive_cnt = 0
    grid_cnt = 0
    if not isinstance(cfg, dict):
        return cfg, 0, 0

    # 1. input.family_consult.archive_path
    try:
        inp = cfg.get("input")
        if isinstance(inp, dict):
            fc = inp.get("family_consult")
            if isinstance(fc, dict):
                ap = fc.get("archive_path")
                if ap == OLD_ARCHIVE_PATH:
                    fc["archive_path"] = NEW_PATH
                    archive_cnt += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("[ai_home_archive_fix] fix archive_path err: %s", e)

    # 2. func_grid.items[*].target_path
    try:
        fg = cfg.get("func_grid")
        if isinstance(fg, dict):
            items = fg.get("items")
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict) and it.get("target_path") == OLD_GRID_TARGET:
                        it["target_path"] = NEW_PATH
                        grid_cnt += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("[ai_home_archive_fix] fix grid target err: %s", e)

    return cfg, archive_cnt, grid_cnt


async def run_migration_with_session(async_session_factory):
    """主入口：扫描 app_settings(key='ai_home_config') 并修正路径残留。"""
    stats: dict[str, Any] = {
        "phase": "ai_home_archive_path_fix_v1",
        "rows_scanned": 0,
        "archive_path_fixed": 0,
        "grid_target_fixed": 0,
        "rows_updated": 0,
    }
    print("[migrate] ai_home_archive_path_fix_v1: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            if not await _table_exists(db, "app_settings"):
                stats["skip_reason"] = "table_app_settings_not_exists"
                print(
                    f"[migrate] ai_home_archive_path_fix_v1: 跳过 stats={stats}",
                    flush=True,
                )
                return stats

            res = await db.execute(
                text("SELECT id, `value` FROM app_settings WHERE `key` = :k"),
                {"k": CONFIG_KEY},
            )
            rows = res.fetchall()
            stats["rows_scanned"] = len(rows)

            for row in rows:
                pk = row[0]
                raw_val = row[1]
                if raw_val is None:
                    continue
                if isinstance(raw_val, (dict, list)):
                    cfg = raw_val
                else:
                    try:
                        cfg = json.loads(raw_val)
                    except Exception:  # noqa: BLE001
                        continue

                new_cfg, a_cnt, g_cnt = _fix_config(cfg)
                if a_cnt == 0 and g_cnt == 0:
                    continue  # 幂等：已是新路径

                stats["archive_path_fixed"] += a_cnt
                stats["grid_target_fixed"] += g_cnt
                stats["rows_updated"] += 1

                new_json = json.dumps(new_cfg, ensure_ascii=False, default=str)
                await db.execute(
                    text("UPDATE app_settings SET `value` = :v WHERE id = :pk"),
                    {"v": new_json, "pk": pk},
                )

            await db.commit()

        print(
            f"[migrate] ai_home_archive_path_fix_v1: 扫描 app_settings(key=ai_home_config) "
            f"共 {stats['rows_scanned']} 条",
            flush=True,
        )
        print(
            f"[migrate] ai_home_archive_path_fix_v1: archive_path 修正 {stats['archive_path_fixed']} 条",
            flush=True,
        )
        print(
            f"[migrate] ai_home_archive_path_fix_v1: 宫格 target_path 修正 {stats['grid_target_fixed']} 条",
            flush=True,
        )
        print("[migrate] ai_home_archive_path_fix_v1: done.", flush=True)
        return stats
    except Exception as e:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(
            f"[migrate] ai_home_archive_path_fix_v1: 异常（不影响启动）: {e}",
            flush=True,
        )
        return stats
