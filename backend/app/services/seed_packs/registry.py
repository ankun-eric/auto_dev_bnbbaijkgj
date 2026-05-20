"""种子包注册表

每个种子包都实现以下接口：
- detect(db) -> str: 'installed' / 'not_installed' / 'partial'
- install(db, conflict_mode: str) -> dict: 安装结果
- uninstall(db) -> dict: 卸载结果

`conflict_mode`：
- 'skip': 已存在则跳过（默认）
- 'overwrite': 覆盖（删除现有，重新插入）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────
# Data class
# ───────────────────────────────────────────────────────────────


@dataclass
class SeedPackDefinition:
    code: str
    name: str
    description: str
    summary: str
    source: str = ""
    version: str = "v1"
    # 检测函数：返回 'installed' / 'not_installed' / 'partial'
    detect: Callable[[AsyncSession], Awaitable[str]] = field(default=lambda db: _noop_detect(db))
    # 安装函数：返回安装结果 dict
    install: Callable[[AsyncSession, str], Awaitable[dict[str, Any]]] = field(
        default=lambda db, mode: _noop_install(db, mode)
    )
    # 卸载函数：返回卸载结果 dict
    uninstall: Callable[[AsyncSession], Awaitable[dict[str, Any]]] = field(
        default=lambda db: _noop_uninstall(db)
    )
    # 详情元数据（前端展示用）
    detail: dict[str, Any] = field(default_factory=dict)


async def _noop_detect(_db) -> str:
    return "not_installed"


async def _noop_install(_db, _mode) -> dict[str, Any]:
    return {"ok": False, "msg": "not implemented"}


async def _noop_uninstall(_db) -> dict[str, Any]:
    return {"ok": False, "msg": "not implemented"}


# ───────────────────────────────────────────────────────────────
# 通用工具函数
# ───────────────────────────────────────────────────────────────


async def _template_exists(db: AsyncSession, code: str) -> int | None:
    row = await db.execute(
        text("SELECT id FROM questionnaire_template WHERE code = :c"),
        {"c": code},
    )
    rec = row.fetchone()
    return int(rec[0]) if rec else None


async def _count_questions(db: AsyncSession, tpl_id: int) -> int:
    r = await db.execute(
        text("SELECT COUNT(*) FROM questionnaire_question WHERE template_id = :t"),
        {"t": tpl_id},
    )
    return int(r.scalar() or 0)


async def _delete_template_data(db: AsyncSession, tpl_id: int) -> dict[str, int]:
    """删除一个模板的所有附属数据（不删模板本身）"""
    stats = {"questions": 0, "rules": 0}
    try:
        d = await db.execute(
            text("DELETE FROM questionnaire_question WHERE template_id = :t"),
            {"t": tpl_id},
        )
        stats["questions"] = d.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.warning("[seed] del questions failed: %s", e)
    try:
        d = await db.execute(
            text("DELETE FROM questionnaire_classification_rule WHERE template_id = :t"),
            {"t": tpl_id},
        )
        stats["rules"] = d.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.warning("[seed] del classification rules failed: %s", e)
    return stats


async def _drop_template(db: AsyncSession, code: str) -> dict[str, int]:
    """彻底删除一个模板（含题目、分型规则）"""
    tpl_id = await _template_exists(db, code)
    if tpl_id is None:
        return {"template_deleted": 0, "questions": 0, "rules": 0}
    stats = await _delete_template_data(db, tpl_id)
    d = await db.execute(
        text("DELETE FROM questionnaire_template WHERE id = :t"),
        {"t": tpl_id},
    )
    stats["template_deleted"] = d.rowcount or 0
    return stats


# ═══════════════════════════════════════════════════════════════
# 1. 中医体质测评（王琦国标 36 题）
# ═══════════════════════════════════════════════════════════════


async def _detect_tcm_constitution(db: AsyncSession) -> str:
    tpl_id = await _template_exists(db, "tcm_constitution")
    if tpl_id is None:
        return "not_installed"
    qn = await _count_questions(db, tpl_id)
    rules = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM questionnaire_classification_rule WHERE template_id = :t"
            ),
            {"t": tpl_id},
        )
    ).scalar() or 0
    if qn == 36 and rules == 9:
        return "installed"
    if qn == 0 and int(rules) == 0:
        return "not_installed"
    return "partial"


async def _install_tcm_constitution(db: AsyncSession, mode: str) -> dict[str, Any]:
    # 重用 prd_tcm36_drawer_v12_migration 中的种子函数
    from app.services.prd_tcm36_drawer_v12_migration import (
        _seed_tcm36_template_and_questions,
    )

    tpl_id = await _template_exists(db, "tcm_constitution")
    if tpl_id and mode == "skip":
        return {"ok": True, "skipped": True, "msg": "已存在，按跳过策略不变更"}
    # mode == 'overwrite' 时 _seed_tcm36_template_and_questions 内部会先删后插，安全
    res = await _seed_tcm36_template_and_questions(db)

    # 自动登记 / 重连「中医体质测评」按钮（指向新模板）
    tpl_id = await _template_exists(db, "tcm_constitution")
    button_action = "unchanged"
    if tpl_id is not None:
        existed = (
            await db.execute(
                text(
                    "SELECT id FROM chat_function_buttons "
                    "WHERE name = '中医体质测评' "
                    "  AND (button_type = 'ai_function' OR button_type = 'questionnaire') "
                    "LIMIT 1"
                )
            )
        ).fetchone()
        if existed:
            await db.execute(
                text(
                    "UPDATE chat_function_buttons SET "
                    "questionnaire_template_id = :tid, ai_function_type = 'questionnaire', "
                    "button_type = 'ai_function', is_enabled = 1, updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {"tid": tpl_id, "id": int(existed[0])},
            )
            button_action = "updated"
        else:
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
            button_action = "inserted"
    return {"ok": True, "template": res, "button_action": button_action}


async def _uninstall_tcm_constitution(db: AsyncSession) -> dict[str, Any]:
    # 删除关联按钮指向 + 模板及题目/分型规则
    tpl_id = await _template_exists(db, "tcm_constitution")
    if tpl_id is None:
        return {"ok": True, "msg": "未安装，无需卸载"}
    btn_d = await db.execute(
        text(
            "DELETE FROM chat_function_buttons "
            "WHERE questionnaire_template_id = :t AND name = '中医体质测评'"
        ),
        {"t": tpl_id},
    )
    drop = await _drop_template(db, "tcm_constitution")
    drop["buttons_deleted"] = btn_d.rowcount or 0
    return {"ok": True, **drop}


# ═══════════════════════════════════════════════════════════════
# 2/3/4. PHQ-9 / GAD-7 / PSQI
# ═══════════════════════════════════════════════════════════════


def _make_score_range_pack(
    code: str,
    name: str,
    description: str,
    summary: str,
    source: str,
    expected_questions: int,
    expected_rules: int,
    seed_func_name: str,
) -> SeedPackDefinition:
    async def detect(db: AsyncSession) -> str:
        tpl_id = await _template_exists(db, code)
        if tpl_id is None:
            return "not_installed"
        qn = await _count_questions(db, tpl_id)
        rn = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM questionnaire_classification_rule WHERE template_id = :t"
                ),
                {"t": tpl_id},
            )
        ).scalar() or 0
        if int(qn) == expected_questions and int(rn) == expected_rules:
            return "installed"
        if int(qn) == 0:
            return "not_installed"
        return "partial"

    async def install(db: AsyncSession, mode: str) -> dict[str, Any]:
        import importlib

        m = importlib.import_module("app.services.prd_qn_content_v1_migration")
        # 先确保 chips/cta 列已存在
        await m._add_template_chips_cta_columns(db)  # noqa: SLF001
        tpl_id = await _template_exists(db, code)
        if tpl_id and mode == "skip":
            return {"ok": True, "skipped": True, "msg": "已存在，按跳过策略不变更"}
        seed_fn = getattr(m, seed_func_name)
        result = await seed_fn(db)
        return {"ok": True, "seed_result": result}

    async def uninstall(db: AsyncSession) -> dict[str, Any]:
        drop = await _drop_template(db, code)
        return {"ok": True, **drop}

    return SeedPackDefinition(
        code=code,
        name=name,
        description=description,
        summary=summary,
        source=source,
        detect=detect,
        install=install,
        uninstall=uninstall,
        detail={
            "tables_affected": [
                "questionnaire_template",
                "questionnaire_question",
                "questionnaire_classification_rule",
            ],
            "expected_questions": expected_questions,
            "expected_rules": expected_rules,
        },
    )


# ═══════════════════════════════════════════════════════════════
# 5. 健康自查 6 维度升级包
# ═══════════════════════════════════════════════════════════════


async def _detect_health_self_check(db: AsyncSession) -> str:
    tpl_id = await _template_exists(db, "health_self_check")
    if tpl_id is None:
        return "not_installed"
    qn = await _count_questions(db, tpl_id)
    # 6 维度 = 部位/症状/持续 + 性质/严重程度/备注，sort_order 中含 91/92/93
    extra = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM questionnaire_question "
                "WHERE template_id = :t AND sort_order >= 91"
            ),
            {"t": tpl_id},
        )
    ).scalar() or 0
    if int(qn) >= 3 and int(extra) >= 3:
        return "installed"
    if int(qn) >= 3 and int(extra) == 0:
        return "partial"
    if int(qn) == 0:
        return "not_installed"
    return "partial"


async def _install_health_self_check(db: AsyncSession, mode: str) -> dict[str, Any]:
    import importlib

    drawer_m = importlib.import_module(
        "app.services.prd_questionnaire_drawer_v1_migration"
    )
    content_m = importlib.import_module("app.services.prd_qn_content_v1_migration")

    # 先确保 chips/cta 列存在
    await content_m._add_template_chips_cta_columns(db)  # noqa: SLF001

    tpl_id = await _template_exists(db, "health_self_check")
    if tpl_id and mode == "skip":
        return {"ok": True, "skipped": True, "msg": "已存在，按跳过策略不变更"}

    if mode == "overwrite" and tpl_id is not None:
        # 删除现有题目，重新插入
        await _delete_template_data(db, tpl_id)

    # 1) 确保模板存在（基础壳）
    tpl_id = await drawer_m._ensure_hsc_template(db)  # noqa: SLF001

    # 2) 默认 AI prompt
    default_prompt = await drawer_m._load_first_hsc_default_prompt(db)  # noqa: SLF001
    if default_prompt:
        await db.execute(
            text(
                "UPDATE questionnaire_template "
                "SET ai_prompt_template = COALESCE(NULLIF(ai_prompt_template,''), :p) "
                "WHERE id = :id"
            ),
            {"id": tpl_id, "p": default_prompt},
        )

    # 3) 部位 + 症状 + 持续时间 3 道基础题
    parts = await drawer_m._load_body_part_dicts(db)  # noqa: SLF001
    durations = await drawer_m._load_first_hsc_duration_options(db)  # noqa: SLF001
    qstats = await drawer_m._upsert_questions(db, tpl_id, parts, durations)  # noqa: SLF001

    # 4) 升级按钮指向
    btn_n = await drawer_m._upgrade_buttons(db, tpl_id)  # noqa: SLF001

    # 5) 新 3 维度题（性质/严重程度/备注）+ chips/cta
    hsc_v2 = await content_m._upgrade_health_self_check_v2(db)  # noqa: SLF001

    return {
        "ok": True,
        "template_id": tpl_id,
        "base_questions": qstats,
        "buttons_upgraded": btn_n,
        "hsc_v2": hsc_v2,
    }


async def _uninstall_health_self_check(db: AsyncSession) -> dict[str, Any]:
    drop = await _drop_template(db, "health_self_check")
    return {"ok": True, **drop}


# ═══════════════════════════════════════════════════════════════
# 6. 9 种体质标签
# ═══════════════════════════════════════════════════════════════


CONSTITUTION_TAGS_LIST = [
    "平和质", "气虚质", "阳虚质", "阴虚质",
    "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质",
]


async def _detect_constitution_tags(db: AsyncSession) -> str:
    try:
        r = await db.execute(
            text(
                "SELECT COUNT(*) FROM tags "
                "WHERE category = 'constitution' "
                "  AND name IN ('平和质','气虚质','阳虚质','阴虚质','痰湿质','湿热质','血瘀质','气郁质','特禀质') "
                "  AND status = 1"
            )
        )
        n = int(r.scalar() or 0)
    except Exception:
        return "not_installed"
    if n >= 9:
        return "installed"
    if n == 0:
        return "not_installed"
    return "partial"


async def _install_constitution_tags(db: AsyncSession, mode: str) -> dict[str, Any]:
    # 先确保 tags 表存在以及 is_locked、sort_order 列
    try:
        await db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tags (
                  id BIGINT PRIMARY KEY AUTO_INCREMENT,
                  name VARCHAR(64) NOT NULL,
                  category VARCHAR(32) NOT NULL,
                  status TINYINT NOT NULL DEFAULT 1,
                  goods_count INT DEFAULT 0,
                  is_locked TINYINT NOT NULL DEFAULT 0,
                  sort_order INT NOT NULL DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  UNIQUE KEY uk_category_name (category, name),
                  INDEX idx_category (category)
                )
                """
            )
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("ensure tags table: %s", e)

    created = 0
    updated = 0
    for idx, name in enumerate(CONSTITUTION_TAGS_LIST):
        exists = (
            await db.execute(
                text(
                    "SELECT id FROM tags WHERE category='constitution' AND name=:n LIMIT 1"
                ),
                {"n": name},
            )
        ).fetchone()
        if exists:
            if mode == "skip":
                continue
            await db.execute(
                text(
                    "UPDATE tags SET status=1, sort_order=:so, is_locked=0, "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=:id"
                ),
                {"so": idx + 1, "id": int(exists[0])},
            )
            updated += 1
        else:
            await db.execute(
                text(
                    "INSERT INTO tags (name, category, status, goods_count, is_locked, sort_order, created_at, updated_at) "
                    "VALUES (:n, 'constitution', 1, 0, 0, :so, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"n": name, "so": idx + 1},
            )
            created += 1
    return {"ok": True, "created": created, "updated": updated}


async def _uninstall_constitution_tags(db: AsyncSession) -> dict[str, Any]:
    # 仅卸载未被任何商品引用的标签
    deleted = 0
    skipped: list[str] = []
    for name in CONSTITUTION_TAGS_LIST:
        row = (
            await db.execute(
                text(
                    "SELECT id, goods_count FROM tags "
                    "WHERE category='constitution' AND name=:n"
                ),
                {"n": name},
            )
        ).fetchone()
        if not row:
            continue
        tid, goods_count = int(row[0]), int(row[1] or 0)
        if goods_count > 0:
            skipped.append(f"{name}(被{goods_count}件商品使用)")
            continue
        try:
            await db.execute(text("DELETE FROM tags WHERE id=:id"), {"id": tid})
            deleted += 1
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{name}(删除失败: {e})")
    return {"ok": True, "deleted": deleted, "skipped": skipped}


# ═══════════════════════════════════════════════════════════════
# 注册表
# ═══════════════════════════════════════════════════════════════


SEED_PACK_REGISTRY: dict[str, SeedPackDefinition] = {
    "tcm_constitution": SeedPackDefinition(
        code="tcm_constitution",
        name="中医体质测评（王琦国标 36 题）",
        description=(
            "王琦九种体质国标 ZYYXH/T157-2009，5 分钟测出 9 种体质中的一种。"
            "包含 36 题量表 + 9 体质分型规则 + 1 个功能按钮 + 默认触发关键词。"
        ),
        summary="1 模板 + 36 题 + 9 分型规则 + 1 功能按钮 + 11 默认关键词",
        source="ZYYXH/T157-2009《中医体质分类与判定》",
        detect=_detect_tcm_constitution,
        install=_install_tcm_constitution,
        uninstall=_uninstall_tcm_constitution,
        detail={
            "tables_affected": [
                "questionnaire_template",
                "questionnaire_question",
                "questionnaire_classification_rule",
                "chat_function_buttons",
            ],
            "expected_questions": 36,
            "expected_rules": 9,
        },
    ),
    "phq9": _make_score_range_pack(
        code="phq9",
        name="抑郁筛查 PHQ-9",
        description="患者健康问卷抑郁量表 PHQ-9，9 个条目，约 3-5 分钟完成。",
        summary="1 模板 + 9 题 + 5 级分型 + 追问 chips + CTA",
        source="PHQ-9 抑郁量表（国际通用）",
        expected_questions=9,
        expected_rules=5,
        seed_func_name="_seed_phq9",
    ),
    "gad7": _make_score_range_pack(
        code="gad7",
        name="焦虑筛查 GAD-7",
        description="广泛性焦虑量表 GAD-7，7 个条目，约 2-3 分钟完成。",
        summary="1 模板 + 7 题 + 4 级分型 + 追问 chips + CTA",
        source="GAD-7 焦虑量表（国际通用）",
        expected_questions=7,
        expected_rules=4,
        seed_func_name="_seed_gad7",
    ),
    "psqi": _make_score_range_pack(
        code="psqi",
        name="匹兹堡睡眠质量指数 PSQI",
        description="匹兹堡睡眠质量指数 PSQI 自评部分，19 个条目，约 5 分钟完成。",
        summary="1 模板 + 19 题 + 4 级分型 + 追问 chips + CTA",
        source="PSQI 匹兹堡睡眠质量指数",
        expected_questions=19,
        expected_rules=4,
        seed_func_name="_seed_psqi",
    ),
    "health_self_check": SeedPackDefinition(
        code="health_self_check",
        name="健康自查 6 维度升级包",
        description=(
            "健康自查问卷模板：部位、症状、持续时间、症状性质、严重程度（VAS 0-10）、症状补充备注。"
            "6 维度配置，覆盖运营常见自查场景。"
        ),
        summary="1 模板 + 6 维度题目 + chips + CTA",
        source="宾尼小康健康自查 v2",
        detect=_detect_health_self_check,
        install=_install_health_self_check,
        uninstall=_uninstall_health_self_check,
        detail={
            "tables_affected": [
                "questionnaire_template",
                "questionnaire_question",
                "chat_function_buttons",
            ],
        },
    ),
    "constitution_tags": SeedPackDefinition(
        code="constitution_tags",
        name="9 种体质标签",
        description=(
            "9 种体质标签：平和质、气虚质、阳虚质、阴虚质、痰湿质、湿热质、血瘀质、气郁质、特禀质。"
            "解锁状态（is_locked=0），允许运营手动管理。"
        ),
        summary="9 条 tags 记录（category=constitution）",
        source="ZYYXH/T157-2009 9 种体质名称",
        detect=_detect_constitution_tags,
        install=_install_constitution_tags,
        uninstall=_uninstall_constitution_tags,
        detail={"tables_affected": ["tags"]},
    ),
}


# ───────────────────────────────────────────────────────────────
# Helper
# ───────────────────────────────────────────────────────────────


def list_packs() -> list[SeedPackDefinition]:
    return list(SEED_PACK_REGISTRY.values())


def get_pack(code: str) -> SeedPackDefinition | None:
    return SEED_PACK_REGISTRY.get(code)
