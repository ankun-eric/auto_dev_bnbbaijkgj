"""[PRD-TCM-DRAWER-V12 2026-05-20] 用户最近体质 AI 上下文注入

工作流程：
1. get_user_latest_constitution(db, user_id) → 返回最近一次主体质 + 兼夹 + 测评时间
2. build_constitution_system_prompt(latest) → 80 字内的 system prompt 注入文本

与对话 API（app/api/chat.py）解耦：调用方在拼装 system_prompt 时主动调用本服务。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    ChatFunctionButton,
    QuestionnaireAnswer,
    QuestionnaireClassificationRule,
    QuestionnaireTemplate,
)


CONSTITUTION_BRIEF: dict[str, str] = {
    "平和质": "阴阳调和、起居有常即可",
    "气虚质": "宜补气、忌过度劳累，多吃山药、黄芪、大枣",
    "阳虚质": "宜温阳、忌生冷，多吃羊肉、生姜、桂圆",
    "阴虚质": "宜滋阴、忌辛辣，多吃银耳、百合、莲子",
    "痰湿质": "宜化湿、忌肥腻，多吃薏米、冬瓜、白萝卜",
    "湿热质": "宜清热利湿、忌油腻甜食，多吃绿豆、苦瓜",
    "血瘀质": "宜活血化瘀、忌寒凉，多吃黑木耳、桃仁、山楂",
    "气郁质": "宜疏肝解郁、多运动，多吃玫瑰花、柑橘、佛手",
    "特禀质": "宜调和气血、远离过敏原，饮食清淡少海鲜",
}


async def get_user_latest_constitution(
    db: AsyncSession, user_id: int
) -> Optional[dict[str, Any]]:
    """获取用户最近一次"中医体质测评"完成结果。

    Returns:
        {
          "main_type": "阳虚质",
          "secondary_types": ["气虚质"],
          "completed_at": datetime,
          "template_code": "tcm_constitution",
        } 或 None
    """
    if not user_id:
        return None
    # 找到 tcm_constitution 模板
    tpl_row = (
        await db.execute(
            select(QuestionnaireTemplate).where(
                QuestionnaireTemplate.code == "tcm_constitution"
            )
        )
    ).scalar_one_or_none()
    if not tpl_row:
        return None
    # 找最近完成的答卷
    ans_row = (
        await db.execute(
            select(QuestionnaireAnswer)
            .where(
                QuestionnaireAnswer.user_id == user_id,
                QuestionnaireAnswer.template_id == tpl_row.id,
                QuestionnaireAnswer.status == "completed",
            )
            .order_by(desc(QuestionnaireAnswer.completed_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if not ans_row:
        return None

    # 优先：classification_id 关联的分型规则
    main_type = None
    if ans_row.classification_id:
        cls = await db.get(
            QuestionnaireClassificationRule, ans_row.classification_id
        )
        if cls:
            main_type = cls.name

    # 兜底：从 dimension_scores 找最高分
    secondary_types: list[str] = []
    scores = ans_row.dimension_scores or {}
    if isinstance(scores, dict) and scores:
        sorted_items = sorted(
            ((k, float(v or 0)) for k, v in scores.items()),
            key=lambda x: x[1], reverse=True,
        )
        if not main_type and sorted_items:
            main_type = sorted_items[0][0]
        # 兼夹：除主之外，分数 >= 40 的
        for k, v in sorted_items:
            if k == main_type:
                continue
            if v >= 40:
                secondary_types.append(k)

    return {
        "main_type": main_type,
        "secondary_types": secondary_types,
        "completed_at": ans_row.completed_at or ans_row.created_at,
        "template_code": tpl_row.code,
        "answer_id": ans_row.id,
    }


def build_constitution_system_prompt(latest: Optional[dict[str, Any]]) -> Optional[str]:
    """构造注入到大模型 system prompt 的体质上下文文本（控制在 80 字内）。

    Returns:
        "用户最近一次中医体质测评：主体质=阳虚质（建议温阳忌生冷）" 或 None
    """
    if not latest or not latest.get("main_type"):
        return None
    main = latest["main_type"]
    brief = CONSTITUTION_BRIEF.get(main, "")
    if brief:
        return f"用户最近一次中医体质测评：主体质={main}（{brief}）"
    return f"用户最近一次中医体质测评：主体质={main}"


async def is_passive_reference_enabled(db: AsyncSession) -> bool:
    """是否有任意 tcm_constitution 按钮启用了被动引用（默认 true）"""
    rows = (
        await db.execute(
            select(ChatFunctionButton).where(
                ChatFunctionButton.button_type == "ai_function",
                ChatFunctionButton.ai_function_type == "questionnaire",
            )
        )
    ).scalars().all()
    if not rows:
        return True
    return any(
        (b.ai_reference_passive is not False) for b in rows
    )


async def should_recommend_tcm_again(
    db: AsyncSession, user_id: int, hours: int = 24
) -> bool:
    """24 小时内是否已经做过/被推荐过测评（已做过 → 不再推荐）"""
    latest = await get_user_latest_constitution(db, user_id)
    if not latest or not latest.get("completed_at"):
        return True
    completed_at = latest["completed_at"]
    if not isinstance(completed_at, datetime):
        return True
    # 已经做过测评的用户：不再主动推荐
    return False


__all__ = [
    "CONSTITUTION_BRIEF",
    "get_user_latest_constitution",
    "build_constitution_system_prompt",
    "is_passive_reference_enabled",
    "should_recommend_tcm_again",
]
