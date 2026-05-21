"""[PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查 AI 解读真接入大模型迁移脚本

为「健康自查功能优化」需求新增数据库字段：

1. questionnaire_answer 表
   - ai_profile_snapshot   JSON  NULL  生成 AI 解读时档案关键字段快照（用于 A+++ 比对）
   - ai_generated_at       DATETIME NULL  最近一次 AI 生成时间

2. questionnaire_template 表（health_self_check 模板）
   - 同步更新 ai_prompt_template 为正式版（中文占位符 + 结构化 JSON 输出协议）
     仅当当前值为空或仍是旧版（包含 {scores}/{main_type} 等错误占位符）时才覆盖。

设计原则（极度保守）：
- 幂等：可重复执行；通过 INFORMATION_SCHEMA 检查列是否已存在
- 不影响主启动流程：任何步骤失败仅记录日志、不抛错
- 历史数据：ai_profile_snapshot 为 NULL 时前端 profile_outdated=false，不打扰

执行入口：`run_migration_with_session(db)` —— 在 main.py 的 lifespan 调用。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)

_SENTINEL_PHASE = "hsc_ai_real_v1"


# ─── 健康自查模板的正式版 ai_prompt_template（中文占位符） ───
HSC_AI_PROMPT_TEMPLATE_V1 = """你是一名专业的全科医生助手。以下是用户的健康自查信息，请基于这些信息给出专业、温和、易懂的初步分析与建议。

【咨询人档案】
姓名信息：{档案信息}
年龄：{档案年龄}
性别：{档案性别}
既往病史：{档案既往病史}
过敏史：{档案过敏史}
在用药物：{档案在用药物}
家族病史：{档案家族病史}

【自查信息】
身体部位：{部位}
出现症状：{症状列表}
持续时间：{持续时间}

请从以下角度作答：
1. 可能的常见原因（按可能性从高到低列出 2~4 个）；
2. 建议进一步关注的伴随症状；
3. 居家可采取的缓解或观察建议；
4. 何种情况下应当尽快就医（明确预警信号）。

回答需通俗、克制，避免给出确定性诊断；末尾自动追加医疗免责声明。

【输出格式要求 — 必须严格遵守】
请直接返回一个 JSON 对象（不要带 ```json 代码块包装），结构如下：
{
  "interpretation": "可能原因 + 伴随症状关注（Markdown 文本，200~400 字）",
  "home_care_tips": ["居家建议1", "居家建议2", "居家建议3", "..."],
  "red_flags": ["就医警示1", "就医警示2", "就医警示3", "..."]
}
home_care_tips 与 red_flags 至少各 3 条、最多各 6 条，每条 15~40 字，结合用户填写的部位与症状个性化生成。
"""


async def _ensure_phase_state_table(db: AsyncSession) -> None:
    try:
        await db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS prd_phase_state (
                  phase VARCHAR(64) PRIMARY KEY,
                  status VARCHAR(32) NOT NULL,
                  detail TEXT NULL,
                  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP
                ) DEFAULT CHARSET=utf8mb4;
                """
            )
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_ai_real_v1] create prd_phase_state failed: %s", e)


async def _set_phase_status(db: AsyncSession, status: str, detail: str = "") -> None:
    try:
        await db.execute(
            text(
                """
                INSERT INTO prd_phase_state (phase, status, detail)
                VALUES (:p, :s, :d)
                ON DUPLICATE KEY UPDATE status = :s, detail = :d
                """
            ),
            {"p": _SENTINEL_PHASE, "s": status, "d": detail[:1000]},
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_ai_real_v1] set phase status failed: %s", e)


async def _column_exists(db: AsyncSession, table: str, column: str) -> bool:
    try:
        row = (
            await db.execute(
                text(
                    """
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :t AND COLUMN_NAME = :c
                    LIMIT 1
                    """
                ),
                {"t": table, "c": column},
            )
        ).first()
        return bool(row)
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_ai_real_v1] _column_exists(%s.%s) failed: %s", table, column, e)
        return False


async def _add_column_safe(db: AsyncSession, table: str, column: str, ddl: str) -> bool:
    if await _column_exists(db, table, column):
        return False
    try:
        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        await db.commit()
        _logger.info("[hsc_ai_real_v1] +column %s.%s", table, column)
        return True
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_ai_real_v1] ADD COLUMN %s.%s failed: %s", table, column, e)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


def _is_legacy_or_empty_prompt(s: Optional[str]) -> bool:
    """旧版残留特征：含 {scores} / {main_type} / 英文占位符 {body_parts} 等；或为空。"""
    if not s or not s.strip():
        return True
    lower = s
    bad_tokens = ["{scores}", "{main_type}", "{body_parts}", "{symptoms}", "{medical_history}"]
    return any(tok in lower for tok in bad_tokens)


async def _update_hsc_prompt(db: AsyncSession) -> int:
    """更新 health_self_check 模板的 ai_prompt_template 为正式版。

    仅在 ai_prompt_template 为空 / 包含旧版占位符时才覆盖，避免误改运营手动修改后的值。
    """
    try:
        row = (
            await db.execute(
                text(
                    "SELECT id, ai_prompt_template FROM questionnaire_template "
                    "WHERE code = 'health_self_check' LIMIT 1"
                )
            )
        ).first()
        if not row:
            _logger.info("[hsc_ai_real_v1] health_self_check 模板不存在，跳过 prompt 更新")
            return 0
        tpl_id, cur_prompt = row[0], row[1]
        if _is_legacy_or_empty_prompt(cur_prompt):
            await db.execute(
                text(
                    "UPDATE questionnaire_template SET ai_prompt_template = :p "
                    "WHERE id = :id"
                ),
                {"id": tpl_id, "p": HSC_AI_PROMPT_TEMPLATE_V1},
            )
            await db.commit()
            _logger.info("[hsc_ai_real_v1] 更新 health_self_check 模板 prompt (template_id=%s)", tpl_id)
            return 1
        return 0
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_ai_real_v1] update prompt failed: %s", e)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return 0


async def run_migration_with_session(db: AsyncSession) -> dict:
    """主入口：在 main.py 的 lifespan 调用。"""
    stats = {"answer_added": 0, "prompt_updated": 0}
    try:
        await _ensure_phase_state_table(db)
        ans_table = "questionnaire_answer"
        ans_cols = [
            ("ai_profile_snapshot", "JSON NULL COMMENT 'AI 解读时档案关键字段快照'"),
            ("ai_generated_at", "DATETIME NULL COMMENT '最近一次 AI 生成时间'"),
        ]
        for col, ddl in ans_cols:
            if await _add_column_safe(db, ans_table, col, ddl):
                stats["answer_added"] += 1

        stats["prompt_updated"] = await _update_hsc_prompt(db)

        await _set_phase_status(db, "done", str(stats))
        _logger.info("[migrate] hsc_ai_real_v1: 迁移完成 stats=%s", stats)
    except Exception as e:  # noqa: BLE001
        _logger.exception("[migrate] hsc_ai_real_v1 failed: %s", e)
    return stats
