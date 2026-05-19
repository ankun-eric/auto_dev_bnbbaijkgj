"""[PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 健康自查抽屉化 + 新版问卷模板体系融合

迁移目标：
1. DDL：
   - chat_function_buttons 加 questionnaire_display_form 列
   - questionnaire_template 加 result_summary_template / source 列
   - questionnaire_question 加 display_condition_json / option_filter_json / layout_hint 列
2. 数据：
   - 把老健康自查的 BodyPartDict 部位+症状 / HealthCheckTemplate.duration_options 全量迁入
     questionnaire 模板"健康自查"的 3 道题（部位/症状/持续时间）+ 选项 + 选项过滤规则
   - 把 BodyPartDict 上的 symptoms 数组 → 问卷的 option_filter_json（部位↔症状联动）
   - 把老 HealthCheckTemplate.default_prompt + duration_options 写入 questionnaire_template
     的 ai_prompt_template 与持续时间题选项
   - 升级所有 button_type='health_self_check' / ai_function_type='health_self_check' 的按钮：
     主类型→ai_function；ai_function_type→questionnaire；questionnaire_template_id 指向健康自查模板；
     questionnaire_display_form→DRAWER_SCROLL；prompt_override_text/enabled 保持原值
3. 全部幂等可重跑。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


async def _add_col(db, table: str, column: str, ddl: str) -> None:
    try:
        chk = await db.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
        if (chk.scalar() or 0) == 0:
            await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            print(
                f"[migrate] questionnaire_drawer_v1: {table}.{column} 列已添加",
                flush=True,
            )
    except Exception as e:  # noqa: BLE001
        logger.debug("加列 %s.%s 跳过: %s", table, column, e)


async def _table_exists(db, table: str) -> bool:
    chk = await db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :t"
        ),
        {"t": table},
    )
    return (chk.scalar() or 0) > 0


async def _ensure_hsc_template(db) -> Optional[int]:
    """确保健康自查 questionnaire 模板存在，返回 ID。"""
    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code = 'health_self_check'"),
    )
    rec = row.fetchone()
    if rec:
        # 反向更新：result_summary_template / source 等若为空则填默认值
        # 对 health_self_check 模板，强制把 source 标记为 system_migrated（因为它就是被本次迁移升级的）
        await db.execute(
            text(
                "UPDATE questionnaire_template "
                "SET result_summary_template = COALESCE(NULLIF(result_summary_template,''), :tpl), "
                "    source = 'system_migrated', "
                "    name = COALESCE(NULLIF(name,''), '健康自查'), "
                "    description = COALESCE(NULLIF(description,''), :desc), "
                "    intro_text = COALESCE(NULLIF(intro_text,''), :intro) "
                "WHERE id = :id"
            ),
            {
                "id": rec[0],
                "tpl": "部位：{部位} | 症状：{症状} | 持续：{持续时间}",
                "desc": "选择部位 → 选择症状 → 选择持续时间，AI 会基于结果给出初步分析。",
                "intro": "请如实选择您当前的症状部位、症状描述及持续时间，AI 会为您给出初步建议。",
            },
        )
        return int(rec[0])
    # 不存在则创建
    res = await db.execute(
        text(
            "INSERT INTO questionnaire_template "
            "(code, name, description, intro_text, estimated_minutes, allow_back, "
            " shuffle_questions, report_layout, status, result_summary_template, source, "
            " created_at, updated_at) "
            "VALUES "
            "('health_self_check', '健康自查', "
            " '选择部位 → 选择症状 → 选择持续时间，AI 会基于结果给出初步分析。', "
            " '请如实选择您当前的症状部位、症状描述及持续时间，AI 会为您给出初步建议。', "
            " 3, 1, 0, 'standard', 1, "
            " '部位：{部位} | 症状：{症状} | 持续：{持续时间}', "
            " 'system_migrated', NOW(), NOW())"
        ),
    )
    return res.lastrowid


def _norm_symptoms(raw: Any) -> list[str]:
    """BodyPartDict.symptoms 可能存的是 JSON list、JSON 字符串、用 `、` 或 `,` 分隔的字符串"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            j = json.loads(s)
            if isinstance(j, list):
                return [str(x).strip() for x in j if x is not None and str(x).strip()]
        except Exception:
            pass
        for sep in ["、", ",", "，", " "]:
            if sep in s:
                return [x.strip() for x in s.split(sep) if x.strip()]
        return [s]
    return []


async def _load_body_part_dicts(db) -> list[dict[str, Any]]:
    if not await _table_exists(db, "body_part_dict"):
        return []
    rows = (
        await db.execute(
            text(
                "SELECT id, name, icon, symptoms, sort_order, enabled "
                "FROM body_part_dict "
                "WHERE enabled = 1 OR enabled IS NULL "
                "ORDER BY sort_order ASC, id ASC"
            )
        )
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r[0]),
                "name": str(r[1] or "").strip(),
                "icon": str(r[2] or "").strip(),
                "symptoms": _norm_symptoms(r[3]),
                "sort_order": int(r[4] or 0),
            }
        )
    return out


async def _load_first_hsc_duration_options(db) -> list[str]:
    """读取任意一个 HealthCheckTemplate.duration_options 作为持续时间题的默认选项。"""
    if not await _table_exists(db, "health_check_templates"):
        return ["今天", "1-3 天", "4-7 天", "1-4 周", "1 个月以上"]
    try:
        row = (
            await db.execute(
                text(
                    "SELECT duration_options FROM health_check_templates "
                    "WHERE (enabled = 1 OR enabled IS NULL) "
                    "ORDER BY id ASC LIMIT 1"
                )
            )
        ).fetchone()
    except Exception:
        row = None
    if not row or not row[0]:
        return ["今天", "1-3 天", "4-7 天", "1-4 周", "1 个月以上"]
    raw = row[0]
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    try:
        j = json.loads(raw)
        if isinstance(j, list):
            return [str(x) for x in j if x]
    except Exception:
        pass
    return ["今天", "1-3 天", "4-7 天", "1-4 周", "1 个月以上"]


async def _load_first_hsc_default_prompt(db) -> Optional[str]:
    """读取任意一个 HealthCheckTemplate.default_prompt 作为问卷模板的 ai_prompt_template 默认值。"""
    if not await _table_exists(db, "health_check_templates"):
        return None
    try:
        row = (
            await db.execute(
                text(
                    "SELECT default_prompt FROM health_check_templates "
                    "WHERE (enabled = 1 OR enabled IS NULL) "
                    "ORDER BY id ASC LIMIT 1"
                )
            )
        ).fetchone()
    except Exception:
        row = None
    if row and row[0]:
        return str(row[0])
    return None


async def _upsert_questions(
    db, tpl_id: int, parts: list[dict[str, Any]], durations: list[str]
) -> dict[str, int]:
    """把"部位 / 症状 / 持续时间"三道题幂等写入（标识用 dimension 字段）。"""
    stats = {"created": 0, "updated": 0}

    # 准备选项与联动
    part_options = [
        {"label": p["name"], "value": p["name"], "icon": p["icon"], "_id": p["id"]}
        for p in parts
        if p["name"]
    ]
    # 收集所有症状（去重，保持出现顺序）
    seen: dict[str, None] = {}
    for p in parts:
        for s in p["symptoms"]:
            if s and s not in seen:
                seen[s] = None
    symptom_options = [{"label": s, "value": s} for s in seen.keys()]

    # 症状题选项过滤映射：部位 → 该部位下症状列表
    filter_map = {p["name"]: p["symptoms"] for p in parts if p["name"]}
    option_filter_json = {
        "deps": [{"question_dimension": "部位", "operator": "in"}],
        "filter_map": filter_map,
        "default": [],
    }

    duration_options = [{"label": d, "value": d} for d in durations if d]

    async def _upsert_one(
        sort_order: int,
        qtype: str,
        title: str,
        subtitle: Optional[str],
        options: list[dict[str, Any]],
        dimension: str,
        layout: str,
        display_condition: Optional[dict[str, Any]] = None,
        option_filter: Optional[dict[str, Any]] = None,
        required: bool = True,
    ) -> int:
        existed = (
            await db.execute(
                text(
                    "SELECT id FROM questionnaire_question "
                    "WHERE template_id = :tid AND dimension = :dim LIMIT 1"
                ),
                {"tid": tpl_id, "dim": dimension},
            )
        ).fetchone()
        params = {
            "tid": tpl_id,
            "so": sort_order,
            "qt": qtype,
            "title": title,
            "sub": subtitle,
            "req": 1 if required else 0,
            "opts": json.dumps(options, ensure_ascii=False),
            "dim": dimension,
            "dc": json.dumps(display_condition, ensure_ascii=False) if display_condition else None,
            "of": json.dumps(option_filter, ensure_ascii=False) if option_filter else None,
            "lh": layout,
        }
        if existed:
            await db.execute(
                text(
                    "UPDATE questionnaire_question SET "
                    "  sort_order = :so, question_type = :qt, title = :title, "
                    "  subtitle = :sub, required = :req, options = :opts, "
                    "  display_condition_json = :dc, option_filter_json = :of, "
                    "  layout_hint = :lh "
                    "WHERE id = :id"
                ),
                {**params, "id": existed[0]},
            )
            stats["updated"] += 1
            return int(existed[0])
        res = await db.execute(
            text(
                "INSERT INTO questionnaire_question "
                "(template_id, sort_order, question_type, title, subtitle, required, "
                " options, dimension, display_condition_json, option_filter_json, "
                " layout_hint, created_at, updated_at) "
                "VALUES (:tid, :so, :qt, :title, :sub, :req, :opts, :dim, :dc, :of, :lh, NOW(), NOW())"
            ),
            params,
        )
        stats["created"] += 1
        return int(res.lastrowid)

    # 题 1：部位（多选 + 图标网格）
    await _upsert_one(
        1, "multi_choice", "请选择不适部位（可多选）",
        "可同时选择多个不适部位",
        part_options or [{"label": "头部", "value": "头部", "icon": "🧠"}],
        "部位", "icon_grid",
    )
    # 题 2：症状（多选 + 标签）+ 联动过滤
    await _upsert_one(
        2, "multi_choice", "请选择您的症状（可多选）",
        "选项会根据您选的部位自动过滤",
        symptom_options or [{"label": "头痛", "value": "头痛"}],
        "症状", "tag_list",
        display_condition={
            "deps": [
                {"question_dimension": "部位", "operator": "not_empty"}
            ],
            "logic": "and",
        },
        option_filter=option_filter_json,
    )
    # 题 3：持续时间（单选）
    await _upsert_one(
        3, "single_choice", "持续了多久？",
        None,
        duration_options or [{"label": "今天", "value": "今天"}],
        "持续时间", "tag_grid",
    )

    return stats


async def _upgrade_buttons(db, tpl_id: int) -> int:
    """把所有"健康自查类"按钮升级到 questionnaire 子类型 + DRAWER_SCROLL 形态。"""
    cnt = 0
    try:
        u1 = await db.execute(
            text(
                "UPDATE chat_function_buttons "
                "SET ai_function_type = 'questionnaire', "
                "    questionnaire_template_id = :tid, "
                "    questionnaire_display_form = COALESCE(NULLIF(questionnaire_display_form,''), 'DRAWER_SCROLL') "
                "WHERE button_type = 'ai_function' "
                "  AND ai_function_type = 'health_self_check' "
                "  AND (questionnaire_template_id IS NULL OR questionnaire_template_id = 0)"
            ),
            {"tid": tpl_id},
        )
        cnt += u1.rowcount or 0
        u2 = await db.execute(
            text(
                "UPDATE chat_function_buttons "
                "SET button_type = 'ai_function', "
                "    ai_function_type = 'questionnaire', "
                "    questionnaire_template_id = :tid, "
                "    questionnaire_display_form = COALESCE(NULLIF(questionnaire_display_form,''), 'DRAWER_SCROLL') "
                "WHERE button_type = 'health_self_check' "
                "  AND (questionnaire_template_id IS NULL OR questionnaire_template_id = 0)"
            ),
            {"tid": tpl_id},
        )
        cnt += u2.rowcount or 0
        # 对存量 ai_function_type=questionnaire 但没有展示形态的按钮，补默认值
        await db.execute(
            text(
                "UPDATE chat_function_buttons "
                "SET questionnaire_display_form = 'DRAWER_SCROLL' "
                "WHERE ai_function_type = 'questionnaire' "
                "  AND (questionnaire_display_form IS NULL OR questionnaire_display_form = '')"
            ),
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("[questionnaire_drawer_v1] 按钮升级跳过: %s", e)
    return cnt


async def _ensure_tcm_template(db) -> Optional[int]:
    """[v1.2 F13] 确保中医体质测评 questionnaire 模板存在，返回 ID。

    模板编码：tcm_constitution_wangqi_36
    模板的"题库"沿用既有 constitution_questions 表（不在 questionnaire_question 中重复维护）；
    questionnaire_template 这里只是个"入口元信息"，让中医体质测评也能复用按钮 + 引导卡片体系。
    """
    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code = 'tcm_constitution_wangqi_36'"),
    )
    rec = row.fetchone()
    if rec:
        return int(rec[0])
    res = await db.execute(
        text(
            "INSERT INTO questionnaire_template "
            "(code, name, description, intro_text, estimated_minutes, allow_back, "
            " shuffle_questions, report_layout, status, result_summary_template, source, "
            " ai_prompt_template, created_at, updated_at) "
            "VALUES ("
            " 'tcm_constitution_wangqi_36', '中医体质测评（王琦 36 题版）', "
            " '基于王琦国标 36 题，5 分钟了解您属于 9 种体质中的哪一种', "
            " '请根据近一年的实际感受作答，共 36 题，5 分钟完成。', "
            " 5, 1, 0, 'radar', 1, "
            " NULL, 'system_migrated', "
            " NULL, NOW(), NOW())"
        ),
    )
    return res.lastrowid


async def _register_tcm_constitution_button(db, tpl_id: int) -> int:
    """[v1.2 F10] 把"中医体质测评"自动登记为一个 questionnaire 类型按钮（幂等）。"""
    try:
        existed = (
            await db.execute(
                text(
                    "SELECT id FROM chat_function_buttons "
                    "WHERE ai_function_type = 'questionnaire' "
                    "  AND questionnaire_template_id = :tid LIMIT 1"
                ),
                {"tid": tpl_id},
            )
        ).fetchone()
        if existed:
            return 0
        await db.execute(
            text(
                "INSERT INTO chat_function_buttons "
                "(name, icon, button_type, ai_function_type, questionnaire_template_id, "
                " questionnaire_display_form, sort_weight, is_enabled, is_recommended, is_capsule, "
                " card_title, card_subtitle, button_sub_desc, pre_card_enabled, "
                " pre_card_icon, pre_card_icon_type, ai_opening, "
                " auto_user_message, created_at, updated_at) "
                "VALUES "
                "('中医体质测评', '🌿', 'ai_function', 'questionnaire', :tid, "
                " 'DRAWER_STEPPED', 200, 1, 1, 1, "
                " '中医体质测评', "
                " '基于王琦国标 36 题，5 分钟了解您属于 9 种体质中的哪一种', "
                " '预计耗时 4-5 分钟 · 数据加密保护', 1, "
                " '🌿', 'emoji', '我想测一下自己的中医体质类型', "
                " '开始中医体质测评', NOW(), NOW())"
            ),
            {"tid": tpl_id},
        )
        return 1
    except Exception as e:  # noqa: BLE001
        logger.debug("[questionnaire_drawer_v1.2] 中医体质按钮登记跳过: %s", e)
        return 0


async def _mark_reverse_score_questions(db) -> int:
    """[v1.2 F13] 标记 34/35/36 题为反向计分。"""
    try:
        res = await db.execute(
            text(
                "UPDATE constitution_questions "
                "SET is_reverse_score = 1 "
                "WHERE order_num IN (34, 35, 36) "
                "  AND (is_reverse_score IS NULL OR is_reverse_score = 0)"
            ),
        )
        return res.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.debug("[questionnaire_drawer_v1.2] 反向题标记跳过: %s", e)
        return 0


async def _backfill_precard_defaults(db) -> int:
    """[v1.2 F10] 所有问卷类按钮的 pre_card_enabled 默认置 true（NULL→1）。"""
    try:
        res = await db.execute(
            text(
                "UPDATE chat_function_buttons "
                "SET pre_card_enabled = 1 "
                "WHERE ai_function_type = 'questionnaire' "
                "  AND (pre_card_enabled IS NULL)"
            ),
        )
        return res.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.debug("[questionnaire_drawer_v1.2] pre_card 默认值回填跳过: %s", e)
        return 0


async def run_migration_with_session(async_session_factory):
    stats = {
        "columns_added": 0,
        "template_seeded": 0,
        "questions_created": 0,
        "questions_updated": 0,
        "buttons_upgraded": 0,
        "tcm_button_registered": 0,
        "reverse_score_marked": 0,
        "precard_backfilled": 0,
    }
    print("[migrate] questionnaire_drawer_v1: 启动", flush=True)
    try:
        async with async_session_factory() as db:
            # 1. DDL
            await _add_col(
                db, "chat_function_buttons",
                "questionnaire_display_form",
                "questionnaire_display_form VARCHAR(32) NULL DEFAULT 'DRAWER_SCROLL' "
                "COMMENT '问卷展示形态：DRAWER_SCROLL / DRAWER_STEPPED / INLINE_CHAT'",
            )
            # [v1.2 新增] 引导卡片图标三选一相关字段
            await _add_col(
                db, "chat_function_buttons",
                "pre_card_icon",
                "pre_card_icon VARCHAR(500) NULL COMMENT '引导卡片图标内容（URL 或 Emoji）'",
            )
            await _add_col(
                db, "chat_function_buttons",
                "pre_card_icon_type",
                "pre_card_icon_type VARCHAR(16) NULL DEFAULT 'default' "
                "COMMENT '图标类型：url / emoji / default'",
            )
            await _add_col(
                db, "questionnaire_template",
                "result_summary_template",
                "result_summary_template TEXT NULL COMMENT '结果摘要模板（含 {题目名} 占位符）'",
            )
            await _add_col(
                db, "questionnaire_template",
                "source",
                "source VARCHAR(32) NULL DEFAULT 'operator_created' "
                "COMMENT '模板来源 system_migrated / operator_created'",
            )
            await _add_col(
                db, "questionnaire_question",
                "display_condition_json",
                "display_condition_json JSON NULL COMMENT '题目显示条件'",
            )
            await _add_col(
                db, "questionnaire_question",
                "option_filter_json",
                "option_filter_json JSON NULL COMMENT '选项过滤规则'",
            )
            await _add_col(
                db, "questionnaire_question",
                "layout_hint",
                "layout_hint VARCHAR(32) NULL DEFAULT 'tag_grid' COMMENT '题目视觉布局'",
            )
            # [v1.2 新增] TCM 体质题反向计分标识
            await _add_col(
                db, "constitution_questions",
                "is_reverse_score",
                "is_reverse_score BOOLEAN NULL DEFAULT 0 "
                "COMMENT '是否反向计分（如平和质的 容易累/声音低弱/不开心）'",
            )
            # [v1.2 新增] Diagnosis 9 项转换分
            await _add_col(
                db, "tcm_diagnoses",
                "constitution_scores",
                "constitution_scores JSON NULL "
                "COMMENT '王琦本地公式 9 项转换分 + 主体质 + 兼夹体质 + 置信度'",
            )
            await db.commit()

            # 2. 模板
            tpl_id = await _ensure_hsc_template(db)
            if tpl_id:
                stats["template_seeded"] = 1
            await db.commit()

            if not tpl_id:
                print("[migrate] questionnaire_drawer_v1: 健康自查模板创建失败，跳过后续", flush=True)
                return stats

            # 3. 老 HealthCheckTemplate 数据 → 模板顶层字段
            default_prompt = await _load_first_hsc_default_prompt(db)
            if default_prompt:
                await db.execute(
                    text(
                        "UPDATE questionnaire_template "
                        "SET ai_prompt_template = COALESCE(NULLIF(ai_prompt_template,''), :p) "
                        "WHERE id = :id"
                    ),
                    {"id": tpl_id, "p": default_prompt},
                )
                await db.commit()

            # 4. 部位+症状+持续时间 → 题目
            parts = await _load_body_part_dicts(db)
            durations = await _load_first_hsc_duration_options(db)
            qstats = await _upsert_questions(db, tpl_id, parts, durations)
            stats["questions_created"] = qstats["created"]
            stats["questions_updated"] = qstats["updated"]
            await db.commit()

            # 5. 升级按钮
            stats["buttons_upgraded"] = await _upgrade_buttons(db, tpl_id)
            await db.commit()

            # 6. [v1.2 新增] 反向计分题标记
            stats["reverse_score_marked"] = await _mark_reverse_score_questions(db)
            await db.commit()

            # 7. [v1.2 新增] 中医体质测评模板 + 按钮自动登记
            tcm_tpl_id = await _ensure_tcm_template(db)
            if tcm_tpl_id:
                stats["tcm_button_registered"] = await _register_tcm_constitution_button(
                    db, tcm_tpl_id
                )
            await db.commit()

            # 8. [v1.2 新增] pre_card_enabled 默认值回填
            stats["precard_backfilled"] = await _backfill_precard_defaults(db)
            await db.commit()

        print(
            f"[migrate] questionnaire_drawer_v1: 完成 stats={json.dumps(stats, ensure_ascii=False)}",
            flush=True,
        )
        return stats
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] questionnaire_drawer_v1: 异常（不影响启动）: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return stats
