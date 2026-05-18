"""
[PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 健康档案页面优化 — AI 外呼配置启动期数据迁移

迁移目标：将"用药计划层"的 AI 外呼配置 + "人维度"总开关合并为
"被守护人维度"的单层结构（每 owner+target 唯一一份）。

迁移策略：
  1) 遍历所有用户（每个 user 作为 owner）：
     - 在 medication_plans 表中聚合该 user 的所有计划的 ai_call_enabled，
       「开 > 关」占多数 → 新结构的 enabled=True；
       不存在历史用药计划 → enabled=False；
       若用户在 reminder_settings 中已有 medication_ai_call_enabled，则优先以该值兜底，
       但仍按"占多数"原则推断 enabled。
     - 免打扰时段：取该用户最近一次 medication_plans.ai_call_dnd_start/end（按 updated_at DESC），
       无则使用默认 22:00–07:00。
     - 外呼对象：取该用户最近一次 medication_plans.ai_call_target_user_id，
       若值为 current user 自己 → 'self'；否则 → 'guardian'；无历史则 'self'。
     - 该配置作为 (owner=user_id, target=user_id) 即"本人对自己"的配置写入。
  2) 对每条 family_management（manager_user_id + managed_user_id + active）：
     - 若 owner=manager_user_id, target=managed_user_id 尚无配置，则插入一条
       默认配置（enabled=False, 22:00–07:00, call_target='self'）。

幂等性：通过 app_settings 中 `_migration_done.prd_health_archive_optim_v1` 标志保护。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text


_logger = logging.getLogger("app.prd_health_archive_optim_v1")


async def run_migration_with_session(async_session_factory) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "users_seen": 0,
        "self_settings_inserted": 0,
        "guardian_settings_inserted": 0,
        "skipped": False,
    }
    FLAG_KEY = "_migration_done.prd_health_archive_optim_v1"

    async with async_session_factory() as db:
        try:
            # 0. 幂等性检查
            try:
                res_flag = await db.execute(
                    text("SELECT `value` FROM app_settings WHERE `key` = :k LIMIT 1"),
                    {"k": FLAG_KEY},
                )
                row = res_flag.first()
                if row and row[0]:
                    stats["skipped"] = True
                    return stats
            except Exception:
                pass

            # 1. 确保 guardian_ai_call_settings 表存在
            try:
                await db.execute(text("SELECT 1 FROM guardian_ai_call_settings LIMIT 1"))
            except Exception:
                # 表尚未创建（schema_sync 应已建好），此时跳过迁移
                _logger.warning("guardian_ai_call_settings 表尚未创建，跳过迁移")
                return stats

            # 2. 为所有用户生成"本人对自己"的配置
            try:
                users_res = await db.execute(text("SELECT id FROM users"))
                user_ids = [r[0] for r in users_res.fetchall()]
            except Exception:
                user_ids = []
            stats["users_seen"] = len(user_ids)

            for uid in user_ids:
                # 检查是否已存在
                exist_res = await db.execute(
                    text("""
                    SELECT id FROM guardian_ai_call_settings
                    WHERE owner_user_id = :owner AND target_user_id = :target
                    LIMIT 1
                    """),
                    {"owner": uid, "target": uid},
                )
                if exist_res.first():
                    continue

                # 推断默认值
                enabled = False
                dnd_start = "22:00"
                dnd_end = "07:00"
                call_target = "self"

                # 从 reminder_settings 中取人维度总开关
                try:
                    rs_res = await db.execute(
                        text("SELECT medication_ai_call_enabled FROM reminder_settings WHERE user_id = :uid LIMIT 1"),
                        {"uid": uid},
                    )
                    rs_row = rs_res.first()
                    if rs_row and rs_row[0]:
                        enabled = True
                except Exception:
                    pass

                # 从 medication_plans 占多数判断（如该表/字段存在）
                try:
                    plan_res = await db.execute(
                        text("""
                        SELECT
                          SUM(CASE WHEN ai_call_enabled = 1 THEN 1 ELSE 0 END) AS on_cnt,
                          SUM(CASE WHEN ai_call_enabled = 0 THEN 1 ELSE 0 END) AS off_cnt
                        FROM medication_plans WHERE user_id = :uid
                        """),
                        {"uid": uid},
                    )
                    pr = plan_res.first()
                    if pr:
                        on_cnt = int(pr[0] or 0)
                        off_cnt = int(pr[1] or 0)
                        if on_cnt + off_cnt > 0:
                            enabled = on_cnt > off_cnt
                except Exception:
                    pass

                # 取最近一次 dnd 时段
                try:
                    dnd_res = await db.execute(
                        text("""
                        SELECT ai_call_dnd_start, ai_call_dnd_end, ai_call_target_user_id
                        FROM medication_plans
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """),
                        {"uid": uid},
                    )
                    dr = dnd_res.first()
                    if dr:
                        if dr[0]:
                            dnd_start = dr[0]
                        if dr[1]:
                            dnd_end = dr[1]
                        if dr[2] is not None and int(dr[2]) != uid:
                            call_target = "guardian"
                        else:
                            call_target = "self"
                except Exception:
                    pass

                # 插入
                try:
                    await db.execute(
                        text("""
                        INSERT INTO guardian_ai_call_settings
                            (owner_user_id, target_user_id, enabled, dnd_start, dnd_end, call_target, created_at, updated_at)
                        VALUES
                            (:owner, :target, :en, :ds, :de, :ct, NOW(), NOW())
                        """),
                        {
                            "owner": uid, "target": uid,
                            "en": 1 if enabled else 0,
                            "ds": dnd_start, "de": dnd_end,
                            "ct": call_target,
                        },
                    )
                    stats["self_settings_inserted"] += 1
                except Exception as e:
                    _logger.warning(f"insert self setting failed for user {uid}: {e}")

            # 3. 为每条 family_management(active) 生成"守护者对被守护人"的默认配置
            try:
                fm_res = await db.execute(text("""
                    SELECT manager_user_id, managed_user_id FROM family_management
                    WHERE status = 'active'
                """))
                pairs = list(fm_res.fetchall())
            except Exception:
                pairs = []

            for owner, target in pairs:
                exist_res = await db.execute(
                    text("""
                    SELECT id FROM guardian_ai_call_settings
                    WHERE owner_user_id = :owner AND target_user_id = :target
                    LIMIT 1
                    """),
                    {"owner": owner, "target": target},
                )
                if exist_res.first():
                    continue
                try:
                    await db.execute(
                        text("""
                        INSERT INTO guardian_ai_call_settings
                            (owner_user_id, target_user_id, enabled, dnd_start, dnd_end, call_target, created_at, updated_at)
                        VALUES (:owner, :target, 0, '22:00', '07:00', 'self', NOW(), NOW())
                        """),
                        {"owner": owner, "target": target},
                    )
                    stats["guardian_settings_inserted"] += 1
                except Exception as e:
                    _logger.warning(f"insert guardian setting failed owner={owner} target={target}: {e}")

            # 4. 写入幂等标志
            try:
                await db.execute(
                    text("""
                    INSERT INTO app_settings (`key`, `value`, `created_at`, `updated_at`)
                    VALUES (:k, '1', NOW(), NOW())
                    ON DUPLICATE KEY UPDATE `value` = '1', `updated_at` = NOW()
                    """),
                    {"k": FLAG_KEY},
                )
            except Exception as e:
                _logger.warning(f"set flag failed: {e}")

            await db.commit()
        except Exception as e:
            _logger.exception(f"prd_health_archive_optim_v1 migration error: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
    return stats
