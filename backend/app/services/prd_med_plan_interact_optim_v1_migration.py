"""
[PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18] 用药计划交互优化 — 启动期数据迁移

执行内容（一次性，幂等）：
  1. 扫描 medication_reminders 表，按 (user_id, family_member_id, normalized(medicine_name))
     维度分组所有 status='active' 的记录；
  2. 同组若超过 1 条，则保留 updated_at（无则 created_at）最新的一条，其余记录
     `status='deleted'`（软删），不动 medication_check_in（服药打卡历史）；
  3. 把保留下来的那条记录的 medicine_name 做 trim 标准化写回，避免后续匹配时拖泥带水；

幂等性：
  通过 app_settings 中 `_migration_done.prd_med_plan_interact_optim_v1` 标志，
  迁移成功后写入 `1`，再次启动时直接跳过。

注意：
  本迁移仅对 status='active' 的记录生效。已结束（archived/deleted）的记录保持不变，
  确保历史服药打卡曲线不受影响。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from sqlalchemy import text


_logger = logging.getLogger("app.prd_med_plan_interact_optim_v1")


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


async def run_migration_with_session(async_session_factory) -> Dict[str, Any]:
    """对外入口：用药计划重复 active 记录软删迁移。"""
    stats: Dict[str, Any] = {
        "groups_scanned": 0,
        "duplicates_soft_deleted": 0,
        "names_normalized": 0,
        "skipped": False,
    }
    FLAG_KEY = "_migration_done.prd_med_plan_interact_optim_v1"

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

            # 1. 拉取所有 active 记录
            try:
                rows = (
                    await db.execute(
                        text(
                            "SELECT id, user_id, family_member_id, medicine_name, "
                            "       updated_at, created_at "
                            "FROM medication_reminders "
                            "WHERE status = 'active'"
                        )
                    )
                ).all()
            except Exception as exc:
                _logger.exception("[med-plan-interact-optim-v1] 拉取 active 记录失败：%s", exc)
                return stats

            groups: Dict[Tuple[int, int | None, str], List[tuple]] = defaultdict(list)
            for r in rows:
                rid, uid, fmid, mname, updated_at, created_at = r
                key = (int(uid), int(fmid) if fmid is not None else None, _norm(mname))
                if not key[2]:
                    continue
                groups[key].append((rid, updated_at, created_at, mname))

            stats["groups_scanned"] = len(groups)

            to_soft_delete: List[int] = []
            for key, items in groups.items():
                if len(items) <= 1:
                    continue
                # 按 updated_at 降序，更新时间为空的退化到 created_at
                items.sort(
                    key=lambda x: (x[1] or x[2] or 0),
                    reverse=True,
                )
                # 保留第一条，其余软删
                for it in items[1:]:
                    to_soft_delete.append(it[0])

            # 2. 批量软删
            if to_soft_delete:
                try:
                    # 分批避免 IN 子句过大
                    BATCH = 200
                    affected = 0
                    for i in range(0, len(to_soft_delete), BATCH):
                        batch = to_soft_delete[i : i + BATCH]
                        ph = ",".join([f":id{j}" for j in range(len(batch))])
                        params = {f"id{j}": v for j, v in enumerate(batch)}
                        res = await db.execute(
                            text(
                                f"UPDATE medication_reminders "
                                f"SET status = 'deleted' "
                                f"WHERE id IN ({ph})"
                            ),
                            params,
                        )
                        affected += int(getattr(res, "rowcount", 0) or 0)
                    stats["duplicates_soft_deleted"] = affected
                except Exception as exc:
                    _logger.exception("[med-plan-interact-optim-v1] 软删重复记录失败：%s", exc)

            # 3. 名字标准化（仅 trim，去掉前后空白；不强制改大小写避免显示突变）
            try:
                res_norm = await db.execute(
                    text(
                        "UPDATE medication_reminders "
                        "SET medicine_name = TRIM(medicine_name) "
                        "WHERE status = 'active' AND medicine_name IS NOT NULL "
                        "  AND medicine_name <> TRIM(medicine_name)"
                    )
                )
                stats["names_normalized"] = int(getattr(res_norm, "rowcount", 0) or 0)
            except Exception as exc:
                _logger.exception("[med-plan-interact-optim-v1] 标准化药品名失败：%s", exc)

            # 4. 写入 app_settings 标志
            try:
                await db.execute(
                    text(
                        "INSERT INTO app_settings (`key`, `value`) VALUES (:k, :v) "
                        "ON DUPLICATE KEY UPDATE `value` = :v"
                    ),
                    {"k": FLAG_KEY, "v": "1"},
                )
            except Exception:
                pass

            await db.commit()
            _logger.info(
                "[med-plan-interact-optim-v1] 迁移完成 stats=%s", stats
            )
        except Exception as exc:
            await db.rollback()
            _logger.exception("[med-plan-interact-optim-v1] 迁移出现异常：%s", exc)
            raise

    return stats
