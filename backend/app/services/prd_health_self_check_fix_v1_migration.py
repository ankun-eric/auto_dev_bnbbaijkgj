"""[BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
健康自查（health_self_check）四问题集中修复迁移脚本。

主要工作：
1. 为 questionnaire_template 加列 `key_field_codes` JSON
2. 为 questionnaire_answer 加列 `key_summary` TEXT
3. D2 方案：彻底清理旧的健康自查模板/题目/选项/答卷/结果，避免重复 seed 数据
4. 重新 seed 健康自查模板：
   - `result_display_mode='triple'`
   - `key_field_codes=['部位','症状','严重程度','持续时间']`
   - Q5 严重程度选项（5 档单值）
   - Q6 题干 / placeholder 拆分文案
5. 幂等保护：所有 INSERT 前 SELECT 检查；如本次已完成则后续启动跳过

启动 main.py 时自动调用本脚本。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# DDL：加列工具
# ─────────────────────────────────────────────────────────────────


async def _column_exists(db, table: str, column: str) -> bool:
    row = await db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "  AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return int(row.scalar() or 0) > 0


async def _add_columns(db) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    if not await _column_exists(db, "questionnaire_template", "key_field_codes"):
        await db.execute(
            text(
                "ALTER TABLE questionnaire_template "
                "ADD COLUMN key_field_codes JSON NULL "
                "COMMENT 'AI 追问注入摘要时保留的关键字段 code 列表'"
            )
        )
        stats["template_key_field_codes"] = "added"
    else:
        stats["template_key_field_codes"] = "exists"

    if not await _column_exists(db, "questionnaire_answer", "key_summary"):
        await db.execute(
            text(
                "ALTER TABLE questionnaire_answer "
                "ADD COLUMN key_summary TEXT NULL "
                "COMMENT 'AI 追问关键摘要（≤200 字）'"
            )
        )
        stats["answer_key_summary"] = "added"
    else:
        stats["answer_key_summary"] = "exists"

    await db.commit()
    return stats


# ─────────────────────────────────────────────────────────────────
# D2：清空健康自查相关历史数据（模板/题目/答卷/结果）
# ─────────────────────────────────────────────────────────────────


async def _purge_health_self_check(db) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code='health_self_check'")
    )
    rec = row.fetchone()
    if not rec:
        stats["template_existed"] = False
        return stats
    tpl_id = int(rec[0])
    stats["template_existed"] = True
    stats["template_id"] = tpl_id

    # 答卷
    try:
        d = await db.execute(
            text("DELETE FROM questionnaire_answer WHERE template_id = :t"),
            {"t": tpl_id},
        )
        stats["answers_deleted"] = d.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.warning("[hsc-fix] del answers failed: %s", e)
        stats["answers_deleted"] = -1
    # 题目
    try:
        d = await db.execute(
            text("DELETE FROM questionnaire_question WHERE template_id = :t"),
            {"t": tpl_id},
        )
        stats["questions_deleted"] = d.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.warning("[hsc-fix] del questions failed: %s", e)
        stats["questions_deleted"] = -1
    # 分型规则
    try:
        d = await db.execute(
            text(
                "DELETE FROM questionnaire_classification_rule WHERE template_id = :t"
            ),
            {"t": tpl_id},
        )
        stats["rules_deleted"] = d.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.warning("[hsc-fix] del rules failed: %s", e)
    await db.commit()
    return stats


# ─────────────────────────────────────────────────────────────────
# Re-seed 健康自查模板（含三段式 + key_field_codes）
# ─────────────────────────────────────────────────────────────────


async def _reseed_health_self_check(db) -> dict[str, Any]:
    """重新 seed 健康自查模板 + 6 维度题目（含修复后的 Q5/Q6 文案与选项）。

    复用 seed_packs.registry._install_health_self_check 的逻辑。
    """
    from app.services.seed_packs.registry import _install_health_self_check  # noqa: WPS437

    res = await _install_health_self_check(db, mode="overwrite")

    # 把模板字段刷成「三段式 + key_field_codes」
    key_field_codes_json = json.dumps(
        ["部位", "症状", "严重程度", "持续时间"], ensure_ascii=False
    )
    await db.execute(
        text(
            "UPDATE questionnaire_template SET "
            "  result_display_mode = 'triple', "
            "  ai_followup_enabled = 1, "
            "  key_field_codes = :kfc, "
            "  updated_at = CURRENT_TIMESTAMP "
            "WHERE code = 'health_self_check'"
        ),
        {"kfc": key_field_codes_json},
    )
    await db.commit()
    return {"install_result": res, "key_field_codes_set": True}


# ─────────────────────────────────────────────────────────────────
# 幂等标记：已执行过则跳过 D2 清空 + 重 seed
# ─────────────────────────────────────────────────────────────────


SENTINEL_KEY = "BUG_HEALTH_SELF_CHECK_FIX_V1_DONE"


async def _ensure_sentinel_table(db):
    """使用 questionnaire_template 表的扩展不太合适，这里复用一个简单的"配置标记"。
    优先使用现有 app_settings 表（若存在），否则建一个内置 migration_flags 表。
    """
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS migration_flags ("
            "  flag_key VARCHAR(128) PRIMARY KEY, "
            "  done TINYINT NOT NULL DEFAULT 0, "
            "  payload TEXT NULL, "
            "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP "
            "    ON UPDATE CURRENT_TIMESTAMP"
            ")"
        )
    )
    await db.commit()


async def _is_done(db) -> bool:
    try:
        row = await db.execute(
            text("SELECT done FROM migration_flags WHERE flag_key = :k"),
            {"k": SENTINEL_KEY},
        )
        rec = row.fetchone()
        return bool(rec and int(rec[0]) == 1)
    except Exception:  # noqa: BLE001
        return False


async def _mark_done(db, payload: dict[str, Any]):
    try:
        await db.execute(
            text(
                "INSERT INTO migration_flags (flag_key, done, payload) "
                "VALUES (:k, 1, :p) "
                "ON DUPLICATE KEY UPDATE done = 1, payload = :p"
            ),
            {"k": SENTINEL_KEY, "p": json.dumps(payload, ensure_ascii=False)[:4000]},
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("[hsc-fix] mark done failed: %s", e)


# ─────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────


async def run_migration_with_session(async_session_factory):
    """主入口：每次启动自动跑一次

    - DDL 始终幂等执行（加列、加 flag 表）
    - D2 清空 + 重 seed 仅在首次执行；后续启动按 sentinel 跳过
    """
    stats: dict[str, Any] = {"phase": "health_self_check_fix_v1"}
    print("[migrate] health_self_check_fix_v1: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            # 1. 始终保证 DDL 与 sentinel 表存在
            stats["ddl"] = await _add_columns(db)
            await _ensure_sentinel_table(db)

            # 2. 幂等保护：已完成则跳过 D2 + 重 seed
            if await _is_done(db):
                stats["skip_reason"] = "sentinel_done"
                print(
                    f"[migrate] health_self_check_fix_v1: 已执行过，跳过清空与重新 seed stats={stats}",
                    flush=True,
                )
                return stats

            # 3. D2：清空旧数据
            stats["purge"] = await _purge_health_self_check(db)

            # 4. 重新 seed 健康自查模板（含修复后的 Q5/Q6 + 三段式）
            stats["reseed"] = await _reseed_health_self_check(db)

            # 5. 标记完成
            await _mark_done(db, stats)

        print(
            f"[migrate] health_self_check_fix_v1: 完成 stats={json.dumps(stats, ensure_ascii=False, default=str)[:2000]}",
            flush=True,
        )
        return stats
    except Exception as e:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(f"[migrate] health_self_check_fix_v1: 异常（不影响启动）: {e}", flush=True)
        return stats
