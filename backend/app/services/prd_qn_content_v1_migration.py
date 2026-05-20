"""[PRD-QN-CONTENT-V1 2026-05-20] 4 个问卷题库 + 健康自查 6 维度 + chips/CTA 后台配置

本迁移做三件事（全部幂等）：

1. ALTER `questionnaire_template`：
   - 新增 `followup_chips_json` JSON 列（后台可配置追问 chips）
   - 新增 `cta_list_json` JSON 列（后台可配置 CTA 按钮 1~4 个）

2. SEED 三个全新问卷模板（与现有 tcm_constitution、health_self_check 并列）：
   - `phq9`  抑郁症筛查 9 题（PHQ-9）
   - `gad7`  焦虑筛查 7 题（GAD-7）
   - `psqi`  匹兹堡睡眠质量指数 19 题（PSQI 自评部分）
   每个模板包含完整题干、5 级或 4 级选项、分型规则、默认 chips、默认 CTA。

3. 升级 `health_self_check` 模板：
   - 在原有"部位 / 症状 / 持续时间"3 步之外，新增 6 维度题目：
     步骤 4：症状性质（大白话 + 表情）
     步骤 5：严重程度（VAS 0-10 滑块）
     步骤 6：症状补充备注（文本 + 语音）
   - 新增的 4/5/6 题目均为 `required=False`，允许跳过

幂等执行：每次启动自动跑一次；可重复执行不破坏数据。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# PHQ-9（抑郁筛查 · 0-3 分 · 9 题）
# ════════════════════════════════════════════════════════════════

PHQ9_OPTIONS = [
    {"label": "完全没有", "value": "完全没有", "score": 0},
    {"label": "几天", "value": "几天", "score": 1},
    {"label": "一半以上的天数", "value": "一半以上的天数", "score": 2},
    {"label": "几乎每天", "value": "几乎每天", "score": 3},
]

PHQ9_QUESTIONS: list[dict[str, Any]] = [
    {"order": 1, "title": "做事时提不起劲或没有兴趣"},
    {"order": 2, "title": "感到心情低落、沮丧或绝望"},
    {"order": 3, "title": "入睡困难、睡不安稳或睡眠过多"},
    {"order": 4, "title": "感觉疲倦或没有活力"},
    {"order": 5, "title": "食欲不振或吃太多"},
    {"order": 6, "title": "觉得自己很糟，或觉得自己很失败，或让自己/家人失望"},
    {"order": 7, "title": "对事物专注有困难，例如看报纸或电视时"},
    {
        "order": 8,
        "title": "动作或说话速度缓慢到别人已经察觉？或刚好相反——变得比平日更烦躁或坐立不安、动来动去",
    },
    {"order": 9, "title": "有不如死掉或用某种方式伤害自己的念头"},
]

# PHQ-9 严重程度分型（score_range）
PHQ9_CLASSIFICATIONS = [
    {"code": "phq9_none", "name": "没有或最少抑郁", "min": 0, "max": 4, "desc": "目前没有明显抑郁症状"},
    {"code": "phq9_mild", "name": "轻度抑郁", "min": 5, "max": 9, "desc": "轻度抑郁，建议关注情绪状态"},
    {"code": "phq9_moderate", "name": "中度抑郁", "min": 10, "max": 14, "desc": "中度抑郁，建议寻求专业评估"},
    {"code": "phq9_mod_severe", "name": "中重度抑郁", "min": 15, "max": 19, "desc": "中重度抑郁，建议尽快就医"},
    {"code": "phq9_severe", "name": "重度抑郁", "min": 20, "max": 27, "desc": "重度抑郁，请立即寻求专业帮助"},
]

PHQ9_DEFAULT_CHIPS = [
    {"code": "shudao", "label": "情绪疏导方法"},
    {"code": "gaishan", "label": "改善建议"},
    {"code": "jiuyi", "label": "何时该求助"},
]

PHQ9_DEFAULT_CTA = [
    {
        "label": "为我生成情绪疏导计划",
        "action": "generate_health_plan",
        "target_url": "/health-plan/generate?source=phq9",
        "style": "primary",
    },
    {
        "label": "推荐：心理咨询服务 / 冥想课程",
        "action": "open_service",
        "target_url": "/services/category/mental_health",
        "style": "secondary",
    },
]

PHQ9_CRISIS_CTA = {
    "label": "立即拨打全国心理援助热线 400-161-9995",
    "action": "external_link",
    "target_url": "tel:400-161-9995",
    "style": "danger",
    "mandatory": True,
    "trigger": "phq9_q9>=1",
}


# ════════════════════════════════════════════════════════════════
# GAD-7（焦虑筛查 · 0-3 分 · 7 题）
# ════════════════════════════════════════════════════════════════

GAD7_OPTIONS = PHQ9_OPTIONS  # 选项一致

GAD7_QUESTIONS: list[dict[str, Any]] = [
    {"order": 1, "title": "感觉紧张、不安或烦躁"},
    {"order": 2, "title": "无法停止或控制担忧"},
    {"order": 3, "title": "对各种各样的事情担忧过多"},
    {"order": 4, "title": "很难放松下来"},
    {"order": 5, "title": "由于不安而无法静坐"},
    {"order": 6, "title": "变得容易烦恼或易被激怒"},
    {"order": 7, "title": "感到似乎有什么可怕的事情会发生"},
]

GAD7_CLASSIFICATIONS = [
    {"code": "gad7_none", "name": "没有或最少焦虑", "min": 0, "max": 4, "desc": "目前没有明显焦虑症状"},
    {"code": "gad7_mild", "name": "轻度焦虑", "min": 5, "max": 9, "desc": "轻度焦虑，建议自我调节"},
    {"code": "gad7_moderate", "name": "中度焦虑", "min": 10, "max": 14, "desc": "中度焦虑，建议关注并寻求帮助"},
    {"code": "gad7_severe", "name": "重度焦虑", "min": 15, "max": 21, "desc": "重度焦虑，建议尽快就医"},
]

GAD7_DEFAULT_CHIPS = [
    {"code": "shudao", "label": "情绪疏导方法"},
    {"code": "gaishan", "label": "改善建议"},
    {"code": "jiuyi", "label": "何时该求助"},
]

GAD7_DEFAULT_CTA = [
    {
        "label": "为我生成情绪疏导计划",
        "action": "generate_health_plan",
        "target_url": "/health-plan/generate?source=gad7",
        "style": "primary",
    },
    {
        "label": "推荐：放松冥想课程",
        "action": "open_service",
        "target_url": "/services/category/relaxation",
        "style": "secondary",
    },
]


# ════════════════════════════════════════════════════════════════
# PSQI（匹兹堡睡眠质量指数 · 自评部分 · 19 题）
# 算分采用简化版：每题 0-3 分，按 7 个成分分组求和；总分 0-21
# ════════════════════════════════════════════════════════════════

PSQI_FREQ_OPTIONS = [
    {"label": "无", "value": "无", "score": 0},
    {"label": "<1 次/周", "value": "<1次/周", "score": 1},
    {"label": "1-2 次/周", "value": "1-2次/周", "score": 2},
    {"label": "≥3 次/周", "value": ">=3次/周", "score": 3},
]

PSQI_QUALITY_OPTIONS = [
    {"label": "很好", "value": "很好", "score": 0},
    {"label": "较好", "value": "较好", "score": 1},
    {"label": "较差", "value": "较差", "score": 2},
    {"label": "很差", "value": "很差", "score": 3},
]

PSQI_LATENCY_OPTIONS = [
    {"label": "≤15 分钟", "value": "<=15min", "score": 0},
    {"label": "16-30 分钟", "value": "16-30min", "score": 1},
    {"label": "31-60 分钟", "value": "31-60min", "score": 2},
    {"label": ">60 分钟", "value": ">60min", "score": 3},
]

PSQI_DURATION_OPTIONS = [
    {"label": ">7 小时", "value": ">7h", "score": 0},
    {"label": "6-7 小时", "value": "6-7h", "score": 1},
    {"label": "5-6 小时", "value": "5-6h", "score": 2},
    {"label": "<5 小时", "value": "<5h", "score": 3},
]

PSQI_EFFICIENCY_OPTIONS = [
    {"label": ">85%", "value": ">85%", "score": 0},
    {"label": "75-84%", "value": "75-84%", "score": 1},
    {"label": "65-74%", "value": "65-74%", "score": 2},
    {"label": "<65%", "value": "<65%", "score": 3},
]

PSQI_DAYTIME_DYSFUNC_OPTIONS = [
    {"label": "没有困难", "value": "没有困难", "score": 0},
    {"label": "偶有困难", "value": "偶有困难", "score": 1},
    {"label": "经常困难", "value": "经常困难", "score": 2},
    {"label": "总是困难", "value": "总是困难", "score": 3},
]

PSQI_QUESTIONS: list[dict[str, Any]] = [
    # C1 主观睡眠质量
    {"order": 1, "title": "近 1 个月，您对自己睡眠质量的总体评价？", "options": PSQI_QUALITY_OPTIONS, "group": "C1主观睡眠质量"},
    # C2 入睡时间
    {"order": 2, "title": "近 1 个月，您通常上床后多久能入睡？", "options": PSQI_LATENCY_OPTIONS, "group": "C2入睡时间"},
    {"order": 3, "title": "近 1 个月，您因为入睡困难而烦恼的频率？", "options": PSQI_FREQ_OPTIONS, "group": "C2入睡时间"},
    # C3 睡眠时间
    {"order": 4, "title": "近 1 个月，您每晚实际睡眠时间约几小时？", "options": PSQI_DURATION_OPTIONS, "group": "C3睡眠时间"},
    # C4 睡眠效率
    {"order": 5, "title": "近 1 个月，您估计自己的睡眠效率（睡着时间÷躺床时间）？", "options": PSQI_EFFICIENCY_OPTIONS, "group": "C4睡眠效率"},
    # C5 睡眠紊乱（多项频率题）
    {"order": 6, "title": "夜间易醒或早醒", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 7, "title": "夜间起床上厕所", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 8, "title": "呼吸不畅", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 9, "title": "咳嗽或鼾声很响", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 10, "title": "感觉冷", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 11, "title": "感觉热", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 12, "title": "做噩梦", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 13, "title": "疼痛不适", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    {"order": 14, "title": "其他影响睡眠的事情", "options": PSQI_FREQ_OPTIONS, "group": "C5睡眠紊乱"},
    # C6 催眠药物
    {"order": 15, "title": "近 1 个月，您使用催眠药物（处方/非处方）的频率？", "options": PSQI_FREQ_OPTIONS, "group": "C6催眠药物"},
    # C7 日间功能障碍
    {"order": 16, "title": "近 1 个月，您日间感到困倦的频率？", "options": PSQI_FREQ_OPTIONS, "group": "C7日间功能障碍"},
    {"order": 17, "title": "近 1 个月，开车、吃饭或社交活动中保持清醒有困难的频率？", "options": PSQI_FREQ_OPTIONS, "group": "C7日间功能障碍"},
    {"order": 18, "title": "近 1 个月，您做事情精力不足的程度？", "options": PSQI_DAYTIME_DYSFUNC_OPTIONS, "group": "C7日间功能障碍"},
    {"order": 19, "title": "近 1 个月，您日间情绪低落或精神不振的频率？", "options": PSQI_FREQ_OPTIONS, "group": "C7日间功能障碍"},
]

PSQI_CLASSIFICATIONS = [
    {"code": "psqi_good", "name": "睡眠质量好", "min": 0, "max": 5, "desc": "您的睡眠质量良好"},
    {"code": "psqi_fair", "name": "睡眠质量一般", "min": 6, "max": 10, "desc": "睡眠质量一般，建议改善作息"},
    {"code": "psqi_poor", "name": "睡眠质量差", "min": 11, "max": 15, "desc": "睡眠质量差，建议关注"},
    {"code": "psqi_very_poor", "name": "睡眠质量很差", "min": 16, "max": 21, "desc": "睡眠质量很差，建议尽快就医"},
]

PSQI_DEFAULT_CHIPS = [
    {"code": "zhumian", "label": "改善睡眠方法"},
    {"code": "yinshi", "label": "助眠饮食"},
    {"code": "zuoxi", "label": "睡眠习惯调整"},
]

PSQI_DEFAULT_CTA = [
    {
        "label": "为我生成助眠改善计划",
        "action": "generate_health_plan",
        "target_url": "/health-plan/generate?source=psqi",
        "style": "primary",
    },
    {
        "label": "推荐：助眠产品 / 睡眠课程",
        "action": "open_shop",
        "target_url": "/shop/category/sleep",
        "style": "secondary",
    },
]


# ════════════════════════════════════════════════════════════════
# 健康自查 6 维度升级（步骤 4/5/6）
# ════════════════════════════════════════════════════════════════

# 步骤 4：症状性质（大白话 + 表情）
HSC_QUALITY_OPTIONS = [
    {"label": "🫀 像心跳一样一跳一跳的疼", "value": "搏动性疼痛", "score": 0},
    {"label": "☁️ 闷闷的、说不清的疼", "value": "钝痛", "score": 0},
    {"label": "🔥 像火烧一样的疼", "value": "烧灼感", "score": 0},
    {"label": "📍 针扎一样的疼", "value": "刺痛", "score": 0},
    {"label": "➰ 麻麻的没知觉", "value": "麻木", "score": 0},
    {"label": "💪 酸酸的像运动后", "value": "酸痛", "score": 0},
    {"label": "🪢 紧紧的像被捆着", "value": "紧绷感", "score": 0},
    {"label": "🕷️ 痒痒的", "value": "瘙痒", "score": 0},
    {"label": "❓ 说不清楚 / 跳过", "value": "skip", "score": 0},
]

# 步骤 5：严重程度 5 档单值（VAS 0-10 简化版）
# [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 改为 5 档单值（每档不重复），前端滑块刻度同步
HSC_SEVERITY_OPTIONS: list[dict[str, Any]] = [
    {"label": "1  🙂 轻微", "value": "1", "score": 1},
    {"label": "3  😐 轻度", "value": "3", "score": 3},
    {"label": "5  😣 中度", "value": "5", "score": 5},
    {"label": "7  😫 重度", "value": "7", "score": 7},
    {"label": "10 😱 剧烈", "value": "10", "score": 10},
    {"label": "❓ 说不清楚 / 跳过", "value": "skip", "score": 0},
]

HSC_NEW_QUESTIONS: list[dict[str, Any]] = [
    {
        "order": 91,  # 高 sort_order 避免冲突
        "title": "症状是什么感觉？（可跳过）",
        "subtitle": "选一个最贴近您的描述，不知道怎么形容就跳过",
        "type": "single_choice",
        "options": HSC_QUALITY_OPTIONS,
        "dimension": "症状性质",
        "required": False,
        "layout_hint": "tag_grid",
    },
    {
        "order": 92,
        "title": "症状严重程度（0=没感觉，10=剧痛，可跳过）",
        "subtitle": "拖动滑块或选数字，越大越严重",
        "type": "single_choice",
        "options": HSC_SEVERITY_OPTIONS,
        "dimension": "严重程度",
        "required": False,
        "layout_hint": "vas_slider",
    },
    {
        "order": 93,
        # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 题干与 placeholder 分离，不再复制
        "title": "还有什么想补充告诉小白的吗？（选填）",
        "subtitle": "例如：受凉后加重 / 每天下午 3 点准时出现 / 服用布洛芬后缓解",
        "type": "text",
        "options": None,
        "dimension": "症状备注",
        "required": False,
        "layout_hint": "voice_text",
    },
]

HSC_DEFAULT_CHIPS = [
    {"code": "jiaju", "label": "居家如何处理"},
    {"code": "zhuyi", "label": "注意事项"},
    {"code": "jiuyi", "label": "是否需要就医"},
]

HSC_DEFAULT_CTA = [
    {
        "label": "为我生成针对性健康计划",
        "action": "generate_health_plan",
        "target_url": "/health-plan/generate?source=health_self_check",
        "style": "primary",
    },
    {
        "label": "推荐：在线问诊 / 上门体检",
        "action": "open_service",
        "target_url": "/services/category/consult",
        "style": "secondary",
    },
]


# 体质测评默认 CTA（已存在 chips，仅补 CTA）
TCM_DEFAULT_CTA = [
    {
        "label": "为我生成体质调理计划",
        "action": "generate_health_plan",
        "target_url": "/health-plan/generate?source=tcm",
        "style": "primary",
    },
    {
        "label": "推荐：相应体质茶饮/食补套装",
        "action": "open_shop",
        "target_url": "/shop/category/tea?tag={main_type}",
        "style": "secondary",
    },
]


# ════════════════════════════════════════════════════════════════
# 通用工具
# ════════════════════════════════════════════════════════════════


async def _column_exists(db, table: str, column: str) -> bool:
    chk = await db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return (chk.scalar() or 0) > 0


async def _add_col_if_missing(db, table: str, column: str, ddl: str) -> bool:
    if await _column_exists(db, table, column):
        return False
    try:
        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        print(f"[migrate] qn_content_v1: ADD {table}.{column}", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        logger.debug("add col %s.%s skip: %s", table, column, e)
        return False


async def _add_template_chips_cta_columns(db) -> dict[str, bool]:
    """给 questionnaire_template 加 followup_chips_json / cta_list_json 两列"""
    added: dict[str, bool] = {}
    added["followup_chips_json"] = await _add_col_if_missing(
        db,
        "questionnaire_template",
        "followup_chips_json",
        "followup_chips_json JSON NULL COMMENT '可配置追问 chips（默认 3 个）'",
    )
    added["cta_list_json"] = await _add_col_if_missing(
        db,
        "questionnaire_template",
        "cta_list_json",
        "cta_list_json JSON NULL COMMENT '可配置 CTA 按钮（默认 2 个，最多 4）'",
    )
    await db.commit()
    return added


async def _upsert_template(
    db,
    *,
    code: str,
    name: str,
    description: str,
    intro_text: str,
    ai_opening: str,
    ai_prompt_template: str,
    result_summary_template: str,
    report_layout: str,
    estimated_minutes: int,
    chips: list[dict[str, str]],
    cta: list[dict[str, Any]],
) -> int:
    """upsert 一个问卷模板，返回 id。"""
    chips_json = json.dumps(chips, ensure_ascii=False)
    cta_json = json.dumps(cta, ensure_ascii=False)
    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code = :c"),
        {"c": code},
    )
    rec = row.fetchone()
    if rec:
        tid = int(rec[0])
        await db.execute(
            text(
                "UPDATE questionnaire_template SET "
                "name=:n, description=:d, intro_text=:it, ai_opening=:ao, "
                "ai_prompt_template=:apt, result_summary_template=:rst, "
                "estimated_minutes=:m, allow_back=1, report_layout=:rl, "
                "status=1, source='system_migrated', "
                "followup_chips_json=:chips, cta_list_json=:cta, "
                "updated_at=CURRENT_TIMESTAMP "
                "WHERE id=:tid"
            ),
            {
                "n": name, "d": description, "it": intro_text, "ao": ai_opening,
                "apt": ai_prompt_template, "rst": result_summary_template,
                "m": estimated_minutes, "rl": report_layout, "tid": tid,
                "chips": chips_json, "cta": cta_json,
            },
        )
        return tid
    res = await db.execute(
        text(
            "INSERT INTO questionnaire_template "
            "(code, name, description, intro_text, ai_opening, ai_prompt_template, "
            " result_summary_template, estimated_minutes, allow_back, shuffle_questions, "
            " report_layout, status, source, followup_chips_json, cta_list_json, "
            " created_at, updated_at) "
            "VALUES (:c, :n, :d, :it, :ao, :apt, :rst, :m, 1, 0, :rl, 1, "
            " 'system_migrated', :chips, :cta, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "c": code, "n": name, "d": description, "it": intro_text, "ao": ai_opening,
            "apt": ai_prompt_template, "rst": result_summary_template,
            "m": estimated_minutes, "rl": report_layout,
            "chips": chips_json, "cta": cta_json,
        },
    )
    return int(res.lastrowid)


async def _reset_questions(db, tid: int) -> int:
    """重建题目（先删后插）"""
    delr = await db.execute(
        text("DELETE FROM questionnaire_question WHERE template_id = :tid"),
        {"tid": tid},
    )
    return delr.rowcount or 0


async def _insert_phq9_or_gad7_questions(
    db, tid: int, qs: list[dict[str, Any]], options: list[dict[str, Any]], dim_prefix: str
) -> int:
    opts_json = json.dumps(options, ensure_ascii=False)
    inserted = 0
    for q in qs:
        meta = {"order_num": q["order"]}
        await db.execute(
            text(
                "INSERT INTO questionnaire_question "
                "(template_id, sort_order, question_type, title, subtitle, required, "
                " options, dimension, display_condition_json, option_filter_json, "
                " layout_hint, created_at, updated_at) "
                "VALUES (:tid, :so, 'single_choice', :title, :sub, 1, "
                " :opts, :dim, :meta, NULL, 'tag_list', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "tid": tid,
                "so": q["order"],
                "title": q["title"],
                "sub": f"第 {q['order']} 题",
                "opts": opts_json,
                "dim": dim_prefix,  # 单一维度，便于按总分求和
                "meta": json.dumps(meta, ensure_ascii=False),
            },
        )
        inserted += 1
    return inserted


async def _insert_psqi_questions(db, tid: int) -> int:
    inserted = 0
    for q in PSQI_QUESTIONS:
        meta = {"order_num": q["order"], "group": q["group"]}
        await db.execute(
            text(
                "INSERT INTO questionnaire_question "
                "(template_id, sort_order, question_type, title, subtitle, required, "
                " options, dimension, display_condition_json, option_filter_json, "
                " layout_hint, created_at, updated_at) "
                "VALUES (:tid, :so, 'single_choice', :title, :sub, 1, "
                " :opts, :dim, :meta, NULL, 'tag_list', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "tid": tid,
                "so": q["order"],
                "title": q["title"],
                "sub": q["group"],
                "opts": json.dumps(q["options"], ensure_ascii=False),
                "dim": q["group"],
                "meta": json.dumps(meta, ensure_ascii=False),
            },
        )
        inserted += 1
    return inserted


async def _insert_score_range_classifications(
    db, tid: int, classifications: list[dict[str, Any]]
) -> int:
    """按 score_range 模式写入分型规则"""
    # 先全删
    await db.execute(
        text("DELETE FROM questionnaire_classification_rule WHERE template_id = :tid"),
        {"tid": tid},
    )
    inserted = 0
    for idx, cls in enumerate(classifications):
        await db.execute(
            text(
                "INSERT INTO questionnaire_classification_rule "
                "(template_id, code, name, description, rule_type, rule_config, sort_order, "
                " created_at, updated_at) "
                "VALUES (:tid, :code, :name, :desc, 'score_range', :cfg, :so, "
                " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "tid": tid,
                "code": cls["code"],
                "name": cls["name"],
                "desc": cls.get("desc", ""),
                "cfg": json.dumps({"min": cls["min"], "max": cls["max"]}, ensure_ascii=False),
                "so": idx,
            },
        )
        inserted += 1
    return inserted


# ════════════════════════════════════════════════════════════════
# 各问卷 seed 主流程
# ════════════════════════════════════════════════════════════════


async def _seed_phq9(db) -> dict[str, Any]:
    tid = await _upsert_template(
        db,
        code="phq9",
        name="PHQ-9 抑郁筛查",
        description="患者健康问卷抑郁量表 PHQ-9，9 个条目，约 3-5 分钟完成。",
        intro_text=(
            "请根据最近 2 周内的实际体验，选择最符合您的选项。"
            "本量表用于初步筛查抑郁倾向，不作为临床诊断依据。"
        ),
        ai_opening="您的 PHQ-9 抑郁筛查已完成，AI 正在为您分析结果…",
        ai_prompt_template=(
            "用户最近一次 PHQ-9 抑郁筛查总分为 {scores}，等级为「{main_type}」。"
            "请用通俗温暖的语言给出 2-3 条改善建议，并提醒「本结果仅供筛查参考，"
            "不构成诊疗依据，如不适请及时就医」。"
        ),
        result_summary_template="PHQ-9 总分：{scores}\n等级：{main_type}",
        report_layout="score_bar",
        estimated_minutes=4,
        chips=PHQ9_DEFAULT_CHIPS,
        cta=PHQ9_DEFAULT_CTA,
    )
    await db.commit()
    deleted = await _reset_questions(db, tid)
    inserted = await _insert_phq9_or_gad7_questions(db, tid, PHQ9_QUESTIONS, PHQ9_OPTIONS, "PHQ9")
    await db.commit()
    cls_n = await _insert_score_range_classifications(db, tid, PHQ9_CLASSIFICATIONS)
    await db.commit()
    return {"template_id": tid, "deleted": deleted, "inserted": inserted, "classifications": cls_n}


async def _seed_gad7(db) -> dict[str, Any]:
    tid = await _upsert_template(
        db,
        code="gad7",
        name="GAD-7 焦虑筛查",
        description="广泛性焦虑量表 GAD-7，7 个条目，约 2-3 分钟完成。",
        intro_text=(
            "请根据最近 2 周内的实际体验，选择最符合您的选项。"
            "本量表用于初步筛查焦虑倾向，不作为临床诊断依据。"
        ),
        ai_opening="您的 GAD-7 焦虑筛查已完成，AI 正在为您分析结果…",
        ai_prompt_template=(
            "用户最近一次 GAD-7 焦虑筛查总分为 {scores}，等级为「{main_type}」。"
            "请用通俗温暖的语言给出 2-3 条放松建议，并提醒「本结果仅供筛查参考，"
            "不构成诊疗依据，如不适请及时就医」。"
        ),
        result_summary_template="GAD-7 总分：{scores}\n等级：{main_type}",
        report_layout="score_bar",
        estimated_minutes=3,
        chips=GAD7_DEFAULT_CHIPS,
        cta=GAD7_DEFAULT_CTA,
    )
    await db.commit()
    deleted = await _reset_questions(db, tid)
    inserted = await _insert_phq9_or_gad7_questions(db, tid, GAD7_QUESTIONS, GAD7_OPTIONS, "GAD7")
    await db.commit()
    cls_n = await _insert_score_range_classifications(db, tid, GAD7_CLASSIFICATIONS)
    await db.commit()
    return {"template_id": tid, "deleted": deleted, "inserted": inserted, "classifications": cls_n}


async def _seed_psqi(db) -> dict[str, Any]:
    tid = await _upsert_template(
        db,
        code="psqi",
        name="PSQI 匹兹堡睡眠质量指数",
        description="匹兹堡睡眠质量指数 PSQI 自评部分，19 个条目，约 5 分钟完成。",
        intro_text=(
            "请根据近 1 个月内的实际睡眠情况，选择最符合您的选项。"
            "本量表用于评估睡眠质量，不作为临床诊断依据。"
        ),
        ai_opening="您的 PSQI 睡眠质量评估已完成，AI 正在为您分析结果…",
        ai_prompt_template=(
            "用户最近一次 PSQI 总分为 {scores}，等级为「{main_type}」。"
            "请用通俗温暖的语言给出 2-3 条助眠建议，并提醒「本结果仅供参考」。"
        ),
        result_summary_template="PSQI 总分：{scores}\n等级：{main_type}",
        report_layout="radar",
        estimated_minutes=5,
        chips=PSQI_DEFAULT_CHIPS,
        cta=PSQI_DEFAULT_CTA,
    )
    await db.commit()
    deleted = await _reset_questions(db, tid)
    inserted = await _insert_psqi_questions(db, tid)
    await db.commit()
    cls_n = await _insert_score_range_classifications(db, tid, PSQI_CLASSIFICATIONS)
    await db.commit()
    return {"template_id": tid, "deleted": deleted, "inserted": inserted, "classifications": cls_n}


async def _upgrade_tcm_chips_cta(db) -> dict[str, Any]:
    """tcm_constitution：保留 chips 默认，补 cta_list_json"""
    chips = [
        {"code": "tiaoli_method", "label": "调理方法"},
        {"code": "yinshi_jinji", "label": "饮食禁忌"},
        {"code": "yundong", "label": "适合运动"},
    ]
    upd = await db.execute(
        text(
            "UPDATE questionnaire_template SET "
            "followup_chips_json = COALESCE(followup_chips_json, :chips), "
            "cta_list_json = COALESCE(cta_list_json, :cta), "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE code = 'tcm_constitution'"
        ),
        {
            "chips": json.dumps(chips, ensure_ascii=False),
            "cta": json.dumps(TCM_DEFAULT_CTA, ensure_ascii=False),
        },
    )
    await db.commit()
    return {"updated": upd.rowcount or 0}


async def _upgrade_health_self_check_v2(db) -> dict[str, Any]:
    """健康自查 v2：补 chips/CTA，并对默认模板加 3 个新维度题目（步骤 4/5/6）"""
    # chips/cta upsert
    upd = await db.execute(
        text(
            "UPDATE questionnaire_template SET "
            "followup_chips_json = COALESCE(followup_chips_json, :chips), "
            "cta_list_json = COALESCE(cta_list_json, :cta), "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE code = 'health_self_check'"
        ),
        {
            "chips": json.dumps(HSC_DEFAULT_CHIPS, ensure_ascii=False),
            "cta": json.dumps(HSC_DEFAULT_CTA, ensure_ascii=False),
        },
    )
    await db.commit()

    # 找到 health_self_check 模板 id
    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code = 'health_self_check' LIMIT 1")
    )
    rec = row.fetchone()
    inserted = 0
    if rec:
        tid = int(rec[0])
        # 删除旧的新维度题目（按 sort_order >= 91 判定）
        await db.execute(
            text(
                "DELETE FROM questionnaire_question "
                "WHERE template_id = :tid AND sort_order >= 91"
            ),
            {"tid": tid},
        )
        for q in HSC_NEW_QUESTIONS:
            meta = {"order_num": q["order"]}
            opts = q["options"]
            opts_json = json.dumps(opts, ensure_ascii=False) if opts else None
            await db.execute(
                text(
                    "INSERT INTO questionnaire_question "
                    "(template_id, sort_order, question_type, title, subtitle, required, "
                    " options, dimension, display_condition_json, option_filter_json, "
                    " layout_hint, created_at, updated_at) "
                    "VALUES (:tid, :so, :qt, :title, :sub, 0, "
                    " :opts, :dim, :meta, NULL, :lh, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "tid": tid,
                    "so": q["order"],
                    "qt": q["type"],
                    "title": q["title"],
                    "sub": q.get("subtitle"),
                    "opts": opts_json,
                    "dim": q["dimension"],
                    "meta": json.dumps(meta, ensure_ascii=False),
                    "lh": q.get("layout_hint", "tag_grid"),
                },
            )
            inserted += 1
        await db.commit()
    return {"chips_cta_updated": upd.rowcount or 0, "new_dim_questions_inserted": inserted}


# ════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════


async def run_migration_with_session(async_session_factory):
    """主入口：每次启动自动跑一次

    [PRD-AI-PAGE-OPTIM-V1 2026-05-21] 关闭自动种子插入：
    - 保留 DDL（questionnaire_template 加 followup_chips_json / cta_list_json 两列）
    - 关闭 PHQ-9 / GAD-7 / PSQI 三套模板 + 题目 + 分型规则的自动插入
    - 关闭健康自查 6 维度新题目的自动插入
    - 数据改由「管理后台 → 系统设置 → 种子数据导入」按需触发
    """
    stats: dict[str, Any] = {"phase": "qn_content_v1"}
    print("[migrate] qn_content_v1: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            stats["columns_added"] = await _add_template_chips_cta_columns(db)
            # [PRD-AI-PAGE-OPTIM-V1 2026-05-21] PHQ-9 / GAD-7 / PSQI / 健康自查 6 维度
            # 全部交由种子导入页按需触发，启动迁移不再自动写入
            stats["phq9"] = {"skipped": "by_seed_pack_admin_page"}
            stats["gad7"] = {"skipped": "by_seed_pack_admin_page"}
            stats["psqi"] = {"skipped": "by_seed_pack_admin_page"}
            stats["tcm_chips_cta"] = {"skipped": "by_seed_pack_admin_page"}
            stats["hsc_v2"] = {"skipped": "by_seed_pack_admin_page"}
            await db.commit()
        print(
            f"[migrate] qn_content_v1: 完成 stats={json.dumps(stats, ensure_ascii=False)}",
            flush=True,
        )
        print(
            "[qn_content_v1] DDL OK, seed data (PHQ-9/GAD-7/PSQI/hsc_v2) "
            "delegated to seed pack admin page",
            flush=True,
        )
        return stats
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] qn_content_v1: 异常（不影响启动）: {e}", flush=True)
        logger.error("[qn_content_v1] error: %s", e)
        return stats
