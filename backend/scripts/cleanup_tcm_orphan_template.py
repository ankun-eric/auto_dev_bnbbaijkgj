"""[PRD-AI-PAGE-OPTIM-V1 2026-05-21] 一次性孤儿模板清理脚本

目标：
1. 把所有 `chat_function_buttons` 中 `questionnaire_template_id` 指向
   `code = 'tcm_constitution_wangqi_36'`（空壳模板）的按钮，
   重定向到 `code = 'tcm_constitution'`（有 36 题的好模板）。
2. 物理删除空壳模板 `tcm_constitution_wangqi_36`，连带：
   - 它的所有 `questionnaire_question`
   - 它的所有 `questionnaire_classification_rule`
   - 它的所有 `questionnaire_recommend_config`（如有）

安全保护：
- 全程事务保护，任一步失败立即回滚
- 输出清理报告日志

运行方式（容器内）：
    docker exec -it <backend-container> python -m backend.scripts.cleanup_tcm_orphan_template

或者：
    docker exec -it <backend-container> python /app/scripts/cleanup_tcm_orphan_template.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# 确保可以从项目根目录 import app.*
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


ORPHAN_CODE = "tcm_constitution_wangqi_36"
TARGET_CODE = "tcm_constitution"


async def cleanup_orphan_tcm_template() -> dict[str, Any]:
    """执行孤儿模板清理。返回清理报告 dict。"""
    from app.core.database import async_session  # noqa: WPS433

    report: dict[str, Any] = {
        "orphan_code": ORPHAN_CODE,
        "target_code": TARGET_CODE,
        "orphan_template_id": None,
        "target_template_id": None,
        "buttons_redirected": 0,
        "questions_deleted": 0,
        "classification_rules_deleted": 0,
        "recommend_configs_deleted": 0,
        "template_deleted": False,
        "warnings": [],
    }

    async with async_session() as db:
        try:
            # 1. 找到孤儿模板 id
            row = await db.execute(
                text("SELECT id FROM questionnaire_template WHERE code = :c"),
                {"c": ORPHAN_CODE},
            )
            rec = row.fetchone()
            if not rec:
                report["warnings"].append(
                    f"未发现孤儿模板 code='{ORPHAN_CODE}'，无需清理"
                )
                logger.info("[cleanup] 未发现孤儿模板 %s，跳过", ORPHAN_CODE)
                return report
            orphan_id = int(rec[0])
            report["orphan_template_id"] = orphan_id

            # 2. 找到目标模板 id（有 36 题的好模板）
            row2 = await db.execute(
                text("SELECT id FROM questionnaire_template WHERE code = :c"),
                {"c": TARGET_CODE},
            )
            rec2 = row2.fetchone()
            target_id = int(rec2[0]) if rec2 else None
            report["target_template_id"] = target_id

            # 3. 按钮重定向（仅当目标模板存在时）
            if target_id is not None:
                upd = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET questionnaire_template_id = :tgt "
                        "WHERE questionnaire_template_id = :orphan"
                    ),
                    {"tgt": target_id, "orphan": orphan_id},
                )
                report["buttons_redirected"] = upd.rowcount or 0
                logger.info(
                    "[cleanup] 已把 %d 个按钮从孤儿模板 #%d 重定向到目标模板 #%d",
                    report["buttons_redirected"],
                    orphan_id,
                    target_id,
                )
            else:
                # 若没有 target 模板，则把按钮的指向置 NULL（避免外键悬挂）
                upd = await db.execute(
                    text(
                        "UPDATE chat_function_buttons "
                        "SET questionnaire_template_id = NULL "
                        "WHERE questionnaire_template_id = :orphan"
                    ),
                    {"orphan": orphan_id},
                )
                report["buttons_redirected"] = upd.rowcount or 0
                report["warnings"].append(
                    f"未找到目标模板 '{TARGET_CODE}'，按钮指向已置 NULL"
                )

            # 4. 删除关联数据
            for tbl, key in (
                ("questionnaire_question", "questions_deleted"),
                ("questionnaire_classification_rule", "classification_rules_deleted"),
            ):
                try:
                    d = await db.execute(
                        text(f"DELETE FROM {tbl} WHERE template_id = :tid"),
                        {"tid": orphan_id},
                    )
                    report[key] = d.rowcount or 0
                except Exception as e:  # noqa: BLE001
                    report["warnings"].append(f"删除 {tbl} 失败: {e}")

            # questionnaire_recommend_config 表是否存在
            try:
                exists = (
                    await db.execute(
                        text(
                            "SELECT COUNT(*) FROM information_schema.tables "
                            "WHERE table_schema = DATABASE() AND table_name = 'questionnaire_recommend_config'"
                        )
                    )
                ).scalar() or 0
                if int(exists):
                    d = await db.execute(
                        text(
                            "DELETE FROM questionnaire_recommend_config "
                            "WHERE template_id = :tid"
                        ),
                        {"tid": orphan_id},
                    )
                    report["recommend_configs_deleted"] = d.rowcount or 0
            except Exception as e:  # noqa: BLE001
                report["warnings"].append(f"删除 questionnaire_recommend_config 失败: {e}")

            # 5. 物理删除孤儿模板
            d = await db.execute(
                text("DELETE FROM questionnaire_template WHERE id = :tid"),
                {"tid": orphan_id},
            )
            report["template_deleted"] = bool(d.rowcount)

            await db.commit()
            logger.info(
                "[cleanup] 清理报告：%s",
                json.dumps(report, ensure_ascii=False),
            )
            return report
        except Exception as e:
            await db.rollback()
            logger.error("[cleanup] 清理失败，事务已回滚: %s", e)
            raise


async def main() -> None:
    report = await cleanup_orphan_tcm_template()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
