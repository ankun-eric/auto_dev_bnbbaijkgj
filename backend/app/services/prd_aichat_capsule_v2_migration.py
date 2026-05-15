"""
[PRD-AICHAT-CAPSULE-V2 2026-05-15] AI 咨询配置-功能按钮管理优化 启动期数据迁移

执行内容：
  1. 在 prompt_templates 表中插入/补全 3 个系统内置识药模板（is_builtin=1）：
       - MED_RECOG_FULL         识药-完整分析
       - MED_RECOG_ADVICE_ONLY  识药-仅用药建议
       - MED_RECOG_AUTO         识药-AI 自动判断
  2. 把存量 chat_function_buttons 中 button_type=photo_recognize_drug 的按钮，
     按 params.ai_reply_mode（或 ai_reply_mode 列）的值映射到 prompt_template_id：
       - full / complete_analysis   → MED_RECOG_FULL
       - medicine_only / basic_advice → MED_RECOG_ADVICE_ONLY
       - auto / ai_auto / 空 / NULL → MED_RECOG_AUTO
     并清空 params.ai_reply_mode 残留值（保留键以兼容旧前端解析，但置 ""）。

幂等性：本脚本可重复执行，已迁移的按钮不会重复变更（按"目标 prompt_template_id 为空时才迁移"判定）。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy import text


_logger = logging.getLogger("app.prd_aichat_capsule_v2")


# 三个系统内置识药模板（PRD 表）
BUILTIN_TEMPLATES = [
    {
        "code": "MED_RECOG_FULL",
        "name": "识药-完整分析",
        "prompt_type": "drug_personal",
        "content": (
            "你是一位专业的临床药学 AI 助手。根据用户上传的药品图片识别结果，请输出：\n"
            "1) 药品基本信息（通用名 / 商品名 / 剂型 / 规格 / 主要成分）；\n"
            "2) 适应症与禁忌；\n"
            "3) 推荐用法用量；\n"
            "4) 与用户现有用药 / 病史的可能相互作用与注意事项。\n"
            "所有内容仅供参考，最终请遵医嘱。"
        ),
    },
    {
        "code": "MED_RECOG_ADVICE_ONLY",
        "name": "识药-仅用药建议",
        "prompt_type": "drug_general",
        "content": (
            "你是一位药品识别 AI 助手。请基于药品图片识别结果，仅输出：怎么吃（用法用量、最佳服用时间、注意事项），"
            "不要展开成分 / 适应症等冗长信息，保持简洁明了。所有用药信息仅供参考，请遵医嘱。"
        ),
    },
    {
        "code": "MED_RECOG_AUTO",
        "name": "识药-AI 自动判断",
        "prompt_type": "drug_query",
        "content": (
            "你是一位资深药品识别 AI 助手。请根据药品图片识别结果 + 用户问题深浅，自适应决定回答的详略：\n"
            " - 用户问得很笼统时，给简明概要 + 关键风险点；\n"
            " - 用户问得明确（如剂量 / 联用 / 禁忌）时，针对性深入回答。\n"
            "所有内容仅供参考，请遵医嘱。"
        ),
    },
]


# 旧 reply_mode 字面值 → 内置模板 code 的映射表
REPLY_MODE_TO_CODE = {
    "full": "MED_RECOG_FULL",
    "complete_analysis": "MED_RECOG_FULL",
    "medicine_only": "MED_RECOG_ADVICE_ONLY",
    "basic_advice": "MED_RECOG_ADVICE_ONLY",
    "auto": "MED_RECOG_AUTO",
    "ai_auto": "MED_RECOG_AUTO",
    "": "MED_RECOG_AUTO",
    None: "MED_RECOG_AUTO",
}


async def _ensure_builtin_templates(db) -> Dict[str, int]:
    """确保 3 个内置模板存在，返回 code -> id 的映射。"""
    code_to_id: Dict[str, int] = {}
    for tpl in BUILTIN_TEMPLATES:
        try:
            res = await db.execute(text(
                "SELECT id FROM prompt_templates WHERE code = :code LIMIT 1"
            ), {"code": tpl["code"]})
            row = res.first()
            if row:
                code_to_id[tpl["code"]] = int(row[0])
                # 重置：保证 is_builtin=1（兼容旧数据被人工置为 0 的情况）
                await db.execute(text(
                    "UPDATE prompt_templates SET is_builtin = 1 WHERE id = :id"
                ), {"id": int(row[0])})
                continue
            # 插入：固定 version=1、is_active=1、is_builtin=1
            ins = await db.execute(text(
                "INSERT INTO prompt_templates "
                "(name, prompt_type, content, version, is_active, code, is_builtin, created_at, updated_at) "
                "VALUES (:name, :prompt_type, :content, 1, 0, :code, 1, NOW(), NOW())"
            ), {
                "name": tpl["name"],
                "prompt_type": tpl["prompt_type"],
                "content": tpl["content"],
                "code": tpl["code"],
            })
            new_id = ins.lastrowid  # type: ignore[attr-defined]
            if not new_id:
                # 兜底再查一次
                res2 = await db.execute(text(
                    "SELECT id FROM prompt_templates WHERE code = :code ORDER BY id DESC LIMIT 1"
                ), {"code": tpl["code"]})
                row2 = res2.first()
                new_id = int(row2[0]) if row2 else 0
            if new_id:
                code_to_id[tpl["code"]] = int(new_id)
            await db.commit()
        except Exception as e:
            await db.rollback()
            _logger.warning("[PRD-CAPSULE-V2] 内置模板 %s 写入失败：%s", tpl["code"], e)
    return code_to_id


def _extract_reply_mode(params_raw: Any, fallback: Optional[str]) -> Optional[str]:
    """从 params JSON 中提取 ai_reply_mode；不存在则用 fallback（旧 ai_reply_mode 列值）。"""
    if isinstance(params_raw, str):
        try:
            params_raw = json.loads(params_raw)
        except Exception:
            params_raw = None
    if isinstance(params_raw, dict):
        v = params_raw.get("ai_reply_mode")
        if v is not None:
            return v if isinstance(v, str) else str(v)
    return fallback


async def _migrate_buttons(db, code_to_id: Dict[str, int]) -> int:
    """把 photo_recognize_drug 按钮的 reply_mode 字段映射到 prompt_template_id（仅当 prompt_template_id 为空时才迁移）。"""
    if not code_to_id:
        return 0
    res = await db.execute(text(
        "SELECT id, params, ai_reply_mode, prompt_template_id "
        "FROM chat_function_buttons "
        "WHERE button_type IN ('photo_recognize_drug', 'drug_identify')"
    ))
    rows = list(res.fetchall())
    migrated = 0
    for row in rows:
        bid, params_raw, ai_reply_mode_col, pt_id = row
        if pt_id:
            # 已有绑定，跳过映射，但仍清空残留的 ai_reply_mode 字面值（避免运营继续看到旧字段语义混乱）
            await _strip_reply_mode_from_params(db, bid, params_raw)
            continue
        mode = _extract_reply_mode(params_raw, ai_reply_mode_col)
        target_code = REPLY_MODE_TO_CODE.get(mode, "MED_RECOG_AUTO")
        target_id = code_to_id.get(target_code)
        if not target_id:
            continue
        try:
            await db.execute(text(
                "UPDATE chat_function_buttons SET prompt_template_id = :pt WHERE id = :id"
            ), {"pt": int(target_id), "id": int(bid)})
            await _strip_reply_mode_from_params(db, bid, params_raw)
            migrated += 1
        except Exception as e:
            _logger.warning("[PRD-CAPSULE-V2] 按钮 id=%s 迁移失败：%s", bid, e)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
    return migrated


async def _strip_reply_mode_from_params(db, button_id: int, params_raw: Any) -> None:
    """把 params.ai_reply_mode 残留值清空（保留 key 兼容旧前端解析）。"""
    parsed = params_raw
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        return
    if "ai_reply_mode" not in parsed:
        return
    parsed["ai_reply_mode"] = ""
    try:
        await db.execute(text(
            "UPDATE chat_function_buttons SET params = :p WHERE id = :id"
        ), {"p": json.dumps(parsed, ensure_ascii=False), "id": int(button_id)})
    except Exception:
        pass


async def run_migration_with_session(async_session_factory) -> Dict[str, Any]:
    """对外入口：拉 session，依次写入内置模板 + 迁移按钮。返回简要统计。"""
    stats: Dict[str, Any] = {"builtin_inserted": 0, "buttons_migrated": 0, "templates": {}}
    async with async_session_factory() as db:
        code_to_id = await _ensure_builtin_templates(db)
        stats["templates"] = code_to_id
        stats["builtin_inserted"] = len(code_to_id)
        migrated = await _migrate_buttons(db, code_to_id)
        stats["buttons_migrated"] = migrated
    _logger.info("[PRD-CAPSULE-V2] 迁移完成：%s", stats)
    return stats
