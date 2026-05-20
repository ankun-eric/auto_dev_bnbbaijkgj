"""[PRD-TCM-DRAWER-V12 2026-05-20] 中医体质测评 36 题 seed + 按钮触发字段扩展

修复内容：
1. 通用问卷模板 `tcm_constitution` 强制重建为 36 题（王琦国标 ZYYXH/T157-2009）
   - 9 体质 × 4 题 = 36 题
   - 5 级李克特量表选项（没有=1 / 很少=2 / 有时=3 / 经常=4 / 总是=5）
   - 题 34/35/36 为反向计分（平和质中的反向题）
   - 同时写入 dimension（体质名）+ 分型规则 9 条 + result_summary_template
2. chat_function_buttons 表新增 5 个字段：
   - trigger_by_keyword (bool, default 1)
   - trigger_by_intent (bool, default 1)
   - trigger_keywords (JSON, default 体质测评关键词列表)
   - ai_reference_passive (bool, default 1)
   - ai_reference_active (bool, default 1)
3. 历史脏数据保护：
   - 模板已存在 → 更新名称/描述/result_summary_template
   - questions 先全删（按 template_id）再插入 36 题（避免 8 题旧版残留）
   - 历史 questionnaire_answer 不动（保留只读）

幂等执行：每次启动自动跑一次；可重复执行不破坏数据。
"""

import json
import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


# 36 题数据（王琦国标 ZYYXH/T157-2009）
TCM36_QUESTIONS: list[dict[str, Any]] = [
    # 气虚质 1-4
    {"order": 1, "group": "气虚质", "title": "您容易疲乏吗？", "reverse": False},
    {"order": 2, "group": "气虚质", "title": "您容易气短（呼吸短促，接不上气）吗？", "reverse": False},
    {"order": 3, "group": "气虚质", "title": "您容易心慌吗？", "reverse": False},
    {"order": 4, "group": "气虚质", "title": "您容易头晕或站起时晕眩吗？", "reverse": False},
    # 阳虚质 5-8
    {"order": 5, "group": "阳虚质", "title": "您手脚发凉吗？", "reverse": False},
    {"order": 6, "group": "阳虚质", "title": "您胃脘部、背部或腰膝部怕冷吗？", "reverse": False},
    {"order": 7, "group": "阳虚质", "title": "您感到怕冷、衣服比别人穿得多吗？", "reverse": False},
    {"order": 8, "group": "阳虚质", "title": "您比一般人耐受不了寒冷（冬天的寒冷、夏天的冷空调、电扇等）吗？", "reverse": False},
    # 阴虚质 9-12
    {"order": 9, "group": "阴虚质", "title": "您感到手脚心发热吗？", "reverse": False},
    {"order": 10, "group": "阴虚质", "title": "您感觉身体、脸上发热吗？", "reverse": False},
    {"order": 11, "group": "阴虚质", "title": "您皮肤或口唇干吗？", "reverse": False},
    {"order": 12, "group": "阴虚质", "title": "您口唇的颜色比一般人红吗？", "reverse": False},
    # 痰湿质 13-16
    {"order": 13, "group": "痰湿质", "title": "您感到胸闷或腹部胀满吗？", "reverse": False},
    {"order": 14, "group": "痰湿质", "title": "您感到身体沉重不轻松或不爽快吗？", "reverse": False},
    {"order": 15, "group": "痰湿质", "title": "您腹部肥满松软吗？", "reverse": False},
    {"order": 16, "group": "痰湿质", "title": "您有额部油脂分泌多的现象吗？", "reverse": False},
    # 湿热质 17-20
    {"order": 17, "group": "湿热质", "title": "您面部或鼻部有油腻感或者油亮发光吗？", "reverse": False},
    {"order": 18, "group": "湿热质", "title": "您易生痤疮或疮疖吗？", "reverse": False},
    {"order": 19, "group": "湿热质", "title": "您感到口苦或嘴里有异味吗？", "reverse": False},
    {"order": 20, "group": "湿热质", "title": "您大便黏滞不爽、有解不尽的感觉吗？", "reverse": False},
    # 血瘀质 21-24
    {"order": 21, "group": "血瘀质", "title": "您的皮肤在不知不觉中会出现青紫瘀斑（皮下出血）吗？", "reverse": False},
    {"order": 22, "group": "血瘀质", "title": "您两颧部有细微红丝吗？", "reverse": False},
    {"order": 23, "group": "血瘀质", "title": "您身体上有哪里疼痛吗？", "reverse": False},
    {"order": 24, "group": "血瘀质", "title": "您面色晦暗或容易出现褐斑吗？", "reverse": False},
    # 气郁质 25-28
    {"order": 25, "group": "气郁质", "title": "您感到闷闷不乐、情绪低沉吗？", "reverse": False},
    {"order": 26, "group": "气郁质", "title": "您容易精神紧张、焦虑不安吗？", "reverse": False},
    {"order": 27, "group": "气郁质", "title": "您多愁善感、感情脆弱吗？", "reverse": False},
    {"order": 28, "group": "气郁质", "title": "您容易感到害怕或受到惊吓吗？", "reverse": False},
    # 特禀质 29-32
    {"order": 29, "group": "特禀质", "title": "您没有感冒时也会打喷嚏吗？", "reverse": False},
    {"order": 30, "group": "特禀质", "title": "您没有感冒时也会鼻塞、流鼻涕吗？", "reverse": False},
    {"order": 31, "group": "特禀质", "title": "您有因季节变化、温度变化或异味等原因而咳喘的现象吗？", "reverse": False},
    {"order": 32, "group": "特禀质", "title": "您容易过敏（药物、食物、气味、花粉或在季节交替、气候变化时）吗？", "reverse": False},
    # 平和质 33-36（34/35/36 为反向计分）
    {"order": 33, "group": "平和质", "title": "您精力充沛吗？", "reverse": False},
    {"order": 34, "group": "平和质", "title": "您容易疲乏吗？", "reverse": True},
    {"order": 35, "group": "平和质", "title": "您说话声音无力吗？", "reverse": True},
    {"order": 36, "group": "平和质", "title": "您感到闷闷不乐吗？", "reverse": True},
]


# 5 级李克特量表统一选项
LIKERT_5_OPTIONS = [
    {"label": "没有", "value": "没有", "score": 1},
    {"label": "很少", "value": "很少", "score": 2},
    {"label": "有时", "value": "有时", "score": 3},
    {"label": "经常", "value": "经常", "score": 4},
    {"label": "总是", "value": "总是", "score": 5},
]


# 9 体质分型规则（dimension_max + score_range 组合，最小判定）
TCM_CLASSIFICATIONS = [
    {"code": "ping_he", "name": "平和质", "desc": "阴阳气血调和，体质平和，是最理想的健康状态"},
    {"code": "qi_xu", "name": "气虚质", "desc": "元气不足，疲乏气短，易出汗"},
    {"code": "yang_xu", "name": "阳虚质", "desc": "阳气不足，畏寒怕冷，手足不温"},
    {"code": "yin_xu", "name": "阴虚质", "desc": "阴液亏少，口燥咽干，手足心热"},
    {"code": "tan_shi", "name": "痰湿质", "desc": "痰湿凝聚，形体肥胖，腹部肥满松软"},
    {"code": "shi_re", "name": "湿热质", "desc": "湿热内蕴，面垢油光，口苦口干"},
    {"code": "xue_yu", "name": "血瘀质", "desc": "血行不畅，肤色晦暗，舌质紫暗"},
    {"code": "qi_yu", "name": "气郁质", "desc": "气机郁滞，神情抑郁，忧虑脆弱"},
    {"code": "te_bing", "name": "特禀质", "desc": "先天禀赋不足，对过敏物质适应能力差"},
]


# 默认关键词列表（运营可在后台修改）
DEFAULT_TCM_TRIGGER_KEYWORDS = [
    "体质测评", "中医体质", "我要测体质", "测一下体质",
    "王琦体质", "九种体质", "9种体质", "我是什么体质",
    "看看我的体质", "做个体质测评", "体质自测",
]


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
        print(f"[migrate] tcm36_drawer_v12: ADD {table}.{column}", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        logger.debug("add col %s.%s skip: %s", table, column, e)
        return False


async def _add_button_trigger_columns(db) -> dict[str, bool]:
    """给 chat_function_buttons 加 5 个新列"""
    added = {}
    added["trigger_by_keyword"] = await _add_col_if_missing(
        db, "chat_function_buttons", "trigger_by_keyword",
        "trigger_by_keyword TINYINT(1) NULL DEFAULT 1 COMMENT '是否启用关键词触发本按钮（默认 1）'",
    )
    added["trigger_by_intent"] = await _add_col_if_missing(
        db, "chat_function_buttons", "trigger_by_intent",
        "trigger_by_intent TINYINT(1) NULL DEFAULT 1 COMMENT '是否启用 AI 意图识别触发本按钮（默认 1）'",
    )
    added["trigger_keywords"] = await _add_col_if_missing(
        db, "chat_function_buttons", "trigger_keywords",
        "trigger_keywords JSON NULL COMMENT '触发关键词列表（JSON 数组）'",
    )
    added["ai_reference_passive"] = await _add_col_if_missing(
        db, "chat_function_buttons", "ai_reference_passive",
        "ai_reference_passive TINYINT(1) NULL DEFAULT 1 COMMENT 'AI 对话被动引用本功能结果（默认 1）'",
    )
    added["ai_reference_active"] = await _add_col_if_missing(
        db, "chat_function_buttons", "ai_reference_active",
        "ai_reference_active TINYINT(1) NULL DEFAULT 1 COMMENT '完成后 AI 主动追问（默认 1）'",
    )
    await db.commit()
    return added


async def _seed_tcm36_template_and_questions(db) -> dict[str, Any]:
    """
    1. 确保 tcm_constitution 模板存在（并更新名称、描述、result_summary_template）
    2. 软删除老题目（更新 sort_order 加 10000 占位）然后插入 36 题
       —— 由于 questionnaire_answer 不直接外键到 question，可以安全 DELETE
    3. 写入分型规则 9 条
    """
    stats: dict[str, Any] = {
        "template_action": "noop",
        "questions_deleted": 0,
        "questions_inserted": 0,
        "classifications_inserted": 0,
        "classifications_existing": 0,
    }

    # 1. upsert template
    name = "中医体质测评（王琦 36 题版）"
    description = "依据 ZYYXH/T157-2009《中医体质分类与判定》标准，王琦九种体质 36 题量表"
    intro_text = (
        "请根据近一年的体验和感觉，回答以下 36 个问题。每题选择最符合您实际情况的选项，"
        "不要过多思考。预计耗时 5 分钟左右。"
    )
    ai_opening = "您的体质测评已完成，AI 正在为您分析最适合的调理方案…"
    result_summary_template = "主体质：{main_type}\n兼夹体质：{secondary_types}\n转换分：{scores}"
    ai_prompt_template = (
        "用户最近一次体质测评结果为「{main_type}」，请结合该体质特点回答用户健康问题，"
        "饮食起居建议结合「{main_type}」忌宜。"
    )

    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code = 'tcm_constitution'")
    )
    rec = row.fetchone()
    if rec:
        tpl_id = int(rec[0])
        await db.execute(
            text(
                "UPDATE questionnaire_template SET "
                "name=:n, description=:d, intro_text=:it, ai_opening=:ao, "
                "result_summary_template=:rst, ai_prompt_template=:apt, "
                "estimated_minutes=5, allow_back=1, report_layout='radar', "
                "status=1, source='system_migrated', updated_at=CURRENT_TIMESTAMP "
                "WHERE id=:tid"
            ),
            {
                "n": name, "d": description, "it": intro_text, "ao": ai_opening,
                "rst": result_summary_template, "apt": ai_prompt_template, "tid": tpl_id,
            },
        )
        stats["template_action"] = "updated"
    else:
        res = await db.execute(
            text(
                "INSERT INTO questionnaire_template "
                "(code, name, description, intro_text, ai_opening, result_summary_template, "
                " ai_prompt_template, estimated_minutes, allow_back, shuffle_questions, "
                " report_layout, status, source, created_at, updated_at) "
                "VALUES ('tcm_constitution', :n, :d, :it, :ao, :rst, :apt, "
                " 5, 1, 0, 'radar', 1, 'system_migrated', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "n": name, "d": description, "it": intro_text, "ao": ai_opening,
                "rst": result_summary_template, "apt": ai_prompt_template,
            },
        )
        tpl_id = res.lastrowid
        stats["template_action"] = "created"
    await db.commit()

    # 2. 重建 questions（先删后插）—— questionnaire_answer 表用 JSON 存答案不直接外键，可安全删
    # [PRD-TCM-DRAWER-V12-BUG2 2026-05-20] 先采集 before 题数，便于运维 grep tcm36 看到 before/after
    try:
        cnt_before = await db.execute(
            text("SELECT COUNT(*) FROM questionnaire_question WHERE template_id = :tid"),
            {"tid": tpl_id},
        )
        stats["questions_before"] = int(cnt_before.scalar() or 0)
    except Exception:  # noqa: BLE001
        stats["questions_before"] = -1

    try:
        delr = await db.execute(
            text("DELETE FROM questionnaire_question WHERE template_id = :tid"),
            {"tid": tpl_id},
        )
        stats["questions_deleted"] = delr.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.warning("[tcm36] delete old questions failed: %s", e)
        await db.rollback()

    options_json = json.dumps(LIKERT_5_OPTIONS, ensure_ascii=False)
    # display_condition / option_filter / layout_hint
    inserted = 0
    for q in TCM36_QUESTIONS:
        # 在 subtitle 中记录元信息（题号 + 反向标记 + group）
        subtitle_parts = [f"第 {q['order']} 题", f"分类：{q['group']}"]
        if q["reverse"]:
            subtitle_parts.append("反向计分")
        subtitle = " · ".join(subtitle_parts)
        # 把 order_num 和 is_reverse_score 编码进 display_condition_json（无侵入式扩展）
        # 注：constitution_score.py 同时支持 group/order_num/is_reverse_score 字段名
        # 这里同时通过 dimension 写入 group
        meta = {
            "order_num": q["order"],
            "is_reverse_score": q["reverse"],
        }
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
                "tid": tpl_id,
                "so": q["order"],
                "title": q["title"],
                "sub": subtitle,
                "opts": options_json,
                "dim": q["group"],
                "meta": json.dumps(meta, ensure_ascii=False),
            },
        )
        inserted += 1
    stats["questions_inserted"] = inserted
    await db.commit()

    # 3. 分型规则（9 体质：dimension_max 模式）
    for sort_idx, cls in enumerate(TCM_CLASSIFICATIONS):
        chk = await db.execute(
            text(
                "SELECT id FROM questionnaire_classification_rule "
                "WHERE template_id = :tid AND code = :code"
            ),
            {"tid": tpl_id, "code": cls["code"]},
        )
        if chk.fetchone():
            stats["classifications_existing"] += 1
            continue
        await db.execute(
            text(
                "INSERT INTO questionnaire_classification_rule "
                "(template_id, code, name, description, rule_type, rule_config, sort_order, "
                " created_at, updated_at) "
                "VALUES (:tid, :code, :name, :desc, 'dimension_max', :cfg, :so, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "tid": tpl_id,
                "code": cls["code"],
                "name": cls["name"],
                "desc": cls["desc"],
                "cfg": json.dumps({"dimension": cls["name"]}, ensure_ascii=False),
                "so": sort_idx,
            },
        )
        stats["classifications_inserted"] += 1
    await db.commit()

    stats["template_id"] = tpl_id
    return stats


async def _backfill_default_trigger_keywords(db, added_cols: dict[str, bool]) -> int:
    """对所有 tcm_constitution 关联的按钮，回填默认关键词列表（仅当 trigger_keywords 为 NULL 时）"""
    try:
        upd = await db.execute(
            text(
                "UPDATE chat_function_buttons cfb "
                "JOIN questionnaire_template qt ON cfb.questionnaire_template_id = qt.id "
                "SET cfb.trigger_keywords = :kw "
                "WHERE qt.code = 'tcm_constitution' "
                "  AND (cfb.trigger_keywords IS NULL OR JSON_LENGTH(cfb.trigger_keywords) = 0)"
            ),
            {"kw": json.dumps(DEFAULT_TCM_TRIGGER_KEYWORDS, ensure_ascii=False)},
        )
        return upd.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.debug("backfill trigger_keywords skip: %s", e)
        return 0


async def run_migration_with_session(async_session_factory):
    """主入口：每次启动自动跑一次"""
    stats: dict[str, Any] = {"phase": "tcm36_drawer_v12"}
    print("[migrate] tcm36_drawer_v12: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            added = await _add_button_trigger_columns(db)
            stats["columns_added"] = added
            tcm_stats = await _seed_tcm36_template_and_questions(db)
            stats.update(tcm_stats)
            stats["trigger_keywords_backfilled"] = await _backfill_default_trigger_keywords(db, added)
            await db.commit()
        print(
            f"[migrate] tcm36_drawer_v12: 完成 stats={json.dumps(stats, ensure_ascii=False)}",
            flush=True,
        )
        # [PRD-TCM-DRAWER-V12-BUG2 2026-05-20] 输出标准化运维日志
        _tid = stats.get("template_id")
        _before = stats.get("questions_before", "?")
        _after = stats.get("questions_inserted", 0)
        print(
            f"[tcm36] template_id={_tid} question_count: before={_before} after={_after}",
            flush=True,
        )
        if _after == 36:
            print("[tcm36] 36 questions OK", flush=True)
        else:
            print(f"[tcm36] WARNING question_count={_after} (expected 36)", flush=True)
        return stats
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] tcm36_drawer_v12: 异常（不影响启动）: {e}", flush=True)
        logger.error("[tcm36_drawer_v12] error: %s", e)
        return stats
