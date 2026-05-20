"""[PRD-TAG-RECOMMEND-V1 2026-05-20] / [商品标签体系重构 v1.0 2026-05-20]
标签管理 + 问卷推荐配置 + 标签体系重构 一次性迁移

迁移内容（幂等，可重复执行）：
1. 新建表：tags、goods_tags、questionnaire_recommend_config
2. questionnaire_template 表新增 4 个字段
3. tags 表新增 is_locked、sort_order 字段（v1.0 重构新增）
4. 9 种体质（平和/气虚/阳虚/阴虚/痰湿/湿热/血瘀/气郁/特禀）写入 constitution 类，is_locked=1
5. 把旧 Tag.category='service'/'other' 的数据迁移：
   - 'service' → 转入 'contraindication'（保留运营资产，但语义上服务特性已废）
   - 'other' → 直接 status=0 停用（不破坏关联），运营可手动归类
6. 将 products.symptom_tags JSON 中包含 9 种体质名字符的旧脏数据
   作为 goods_tags 关联写入，drop products.symptom_tags 字段
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# 9 种体质
CONSTITUTION_TAGS = [
    "平和质", "气虚质", "阳虚质", "阴虚质",
    "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质",
]

# 9 种体质同义识别表：脏数据中可能写成的形式 → 标准体质名
CONSTITUTION_ALIASES = {
    "平和质": "平和质", "平和": "平和质", "平和体质": "平和质",
    "气虚质": "气虚质", "气虚": "气虚质", "气虚体质": "气虚质",
    "阳虚质": "阳虚质", "阳虚": "阳虚质", "阳虚体质": "阳虚质",
    "阴虚质": "阴虚质", "阴虚": "阴虚质", "阴虚体质": "阴虚质",
    "痰湿质": "痰湿质", "痰湿": "痰湿质", "痰湿体质": "痰湿质",
    "湿热质": "湿热质", "湿热": "湿热质", "湿热体质": "湿热质",
    "血瘀质": "血瘀质", "血瘀": "血瘀质", "血瘀体质": "血瘀质",
    "气郁质": "气郁质", "气郁": "气郁质", "气郁体质": "气郁质",
    "特禀质": "特禀质", "特禀": "特禀质", "特禀体质": "特禀质",
}


async def _ensure_tag_tables(db: AsyncSession) -> dict[str, int]:
    """建表（幂等）"""
    stats = {"tags_created": 0, "goods_tags_created": 0, "recommend_cfg_created": 0}
    await db.execute(text("""
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
    """))
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS goods_tags (
          goods_id BIGINT NOT NULL,
          tag_id BIGINT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (goods_id, tag_id),
          KEY idx_tag_id (tag_id)
        )
    """))
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS questionnaire_recommend_config (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          template_id BIGINT NOT NULL,
          result_key VARCHAR(64) NOT NULL,
          mode TINYINT NOT NULL,
          filter_json JSON NULL,
          manual_goods_ids JSON NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_template_result (template_id, result_key)
        )
    """))
    return stats


async def _add_template_columns(db: AsyncSession) -> dict[str, int]:
    """questionnaire_template 表添加 4 个字段（幂等）"""
    cols_added = 0
    columns = [
        ("result_display_mode", "VARCHAR(16) DEFAULT 'simple'"),
        ("ai_followup_enabled", "TINYINT DEFAULT 1"),
        ("recommend_click_mode", "VARCHAR(16) DEFAULT 'drawer'"),
        ("recommend_display_count", "TINYINT DEFAULT 6"),
    ]
    for col, defn in columns:
        try:
            await db.execute(text(f"ALTER TABLE questionnaire_template ADD COLUMN {col} {defn}"))
            cols_added += 1
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "exists" in msg or "1060" in msg:
                continue
    return {"template_columns_added": cols_added}


async def _add_tag_columns(db: AsyncSession) -> dict[str, int]:
    """[体系重构 v1.0] tags 表新增 is_locked、sort_order 字段（幂等）"""
    added = 0
    for col, defn in (
        ("is_locked", "TINYINT NOT NULL DEFAULT 0"),
        ("sort_order", "INT NOT NULL DEFAULT 0"),
    ):
        try:
            await db.execute(text(f"ALTER TABLE tags ADD COLUMN {col} {defn}"))
            added += 1
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "exists" in msg or "1060" in msg:
                continue
    return {"tag_columns_added": added}


async def _seed_constitution_tags(db: AsyncSession) -> dict[str, int]:
    """把 9 种体质作为 constitution 类标签写入（幂等），并锁定 is_locked=1"""
    created = 0
    for idx, name in enumerate(CONSTITUTION_TAGS):
        try:
            await db.execute(
                text(
                    "INSERT INTO tags (name, category, status, goods_count, is_locked, sort_order, created_at, updated_at) "
                    "VALUES (:n, 'constitution', 1, 0, 1, :so, NOW(), NOW()) "
                    "ON DUPLICATE KEY UPDATE is_locked=1, status=COALESCE(status,1), sort_order=:so"
                ),
                {"n": name, "so": idx + 1},
            )
            created += 1
        except Exception:
            pass
    return {"constitution_tags_seeded": created}


async def _migrate_legacy_tag_categories(db: AsyncSession) -> dict[str, int]:
    """[体系重构 v1.0] 把 Tag.category in ('service','other') 的历史数据收敛到 6 类内
    - service → 改为 contraindication（保留运营资产）
    - other → 状态置 0 停用（不破坏关联，避免数据丢失）
    """
    moved_service = 0
    deactivated_other = 0
    try:
        r = await db.execute(text("UPDATE tags SET category='contraindication' WHERE category='service'"))
        moved_service = r.rowcount or 0
    except Exception:
        pass
    try:
        r2 = await db.execute(text("UPDATE tags SET status=0 WHERE category='other'"))
        deactivated_other = r2.rowcount or 0
    except Exception:
        pass
    return {
        "legacy_service_to_contraindication": int(moved_service or 0),
        "legacy_other_deactivated": int(deactivated_other or 0),
    }


async def _migrate_symptom_tags_to_goods_tags(db: AsyncSession) -> dict[str, int]:
    """[体系重构 v1.0] 把 products.symptom_tags(JSON) 中包含体质名的旧数据迁入 goods_tags

    仅迁体质（9 种规整数据），其他症状脏数据全量丢弃。
    若 products 表已无 symptom_tags 列（已被 drop），跳过。
    """
    moved = 0
    # 检查列是否存在
    try:
        col_exists = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='products' AND COLUMN_NAME='symptom_tags'"
                )
            )
        ).scalar() or 0
        if not int(col_exists or 0):
            return {"symptom_tags_migrated": 0, "symptom_tags_column_missing": 1}
    except Exception:
        return {"symptom_tags_migrated": 0}

    # 读取 constitution 标签 name → id
    try:
        rows = (
            await db.execute(text("SELECT id, name FROM tags WHERE category='constitution'"))
        ).all()
        const_name_to_id = {str(n): int(i) for i, n in rows}
    except Exception:
        return {"symptom_tags_migrated": 0}

    if not const_name_to_id:
        return {"symptom_tags_migrated": 0}

    try:
        prod_rows = (
            await db.execute(
                text("SELECT id, symptom_tags FROM products WHERE symptom_tags IS NOT NULL")
            )
        ).all()
    except Exception:
        return {"symptom_tags_migrated": 0}

    import json
    for pid, raw in prod_rows:
        # raw 可能是 JSON 字符串或 list
        try:
            data = raw
            if isinstance(raw, (bytes, bytearray)):
                data = raw.decode("utf-8", errors="ignore")
            if isinstance(data, str):
                data = json.loads(data)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        target_tag_ids: set[int] = set()
        for token in data:
            if not isinstance(token, str):
                continue
            t = token.strip()
            std = CONSTITUTION_ALIASES.get(t)
            if std and std in const_name_to_id:
                target_tag_ids.add(const_name_to_id[std])
        for tid in target_tag_ids:
            try:
                await db.execute(
                    text(
                        "INSERT IGNORE INTO goods_tags (goods_id, tag_id, created_at) "
                        "VALUES (:g, :t, NOW())"
                    ),
                    {"g": int(pid), "t": int(tid)},
                )
                moved += 1
            except Exception:
                pass
    return {"symptom_tags_migrated": moved}


async def _drop_symptom_tags_column(db: AsyncSession) -> dict[str, int]:
    """[体系重构 v1.0] 删除 products.symptom_tags 字段（一次性、幂等）"""
    try:
        col_exists = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='products' AND COLUMN_NAME='symptom_tags'"
                )
            )
        ).scalar() or 0
        if not int(col_exists or 0):
            return {"symptom_tags_column_dropped": 0}
        await db.execute(text("ALTER TABLE products DROP COLUMN symptom_tags"))
        return {"symptom_tags_column_dropped": 1}
    except Exception:
        return {"symptom_tags_column_dropped": 0}


async def _default_tcm_recommend_display(db: AsyncSession) -> dict[str, int]:
    """把体质测评模板（code=tcm_constitution）的 result_display_mode 设为 triple"""
    try:
        await db.execute(
            text(
                "UPDATE questionnaire_template "
                "SET result_display_mode='triple', ai_followup_enabled=1, "
                "    recommend_click_mode='drawer', recommend_display_count=6 "
                "WHERE code='tcm_constitution' "
                "  AND (result_display_mode IS NULL OR result_display_mode='simple')"
            )
        )
        return {"tcm_set_triple": 1}
    except Exception:
        return {"tcm_set_triple": 0}


async def run_migration_with_session(session_maker) -> dict[str, int]:
    """迁移入口：被 main.py lifespan 调用。幂等，可重复执行。"""
    stats: dict[str, int] = {}
    async with session_maker() as db:
        try:
            stats.update(await _ensure_tag_tables(db))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        try:
            stats.update(await _add_template_columns(db))
            await db.commit()
        except Exception:
            await db.rollback()
        try:
            stats.update(await _add_tag_columns(db))
            await db.commit()
        except Exception:
            await db.rollback()
        try:
            stats.update(await _seed_constitution_tags(db))
            stats.update(await _migrate_legacy_tag_categories(db))
            stats.update(await _default_tcm_recommend_display(db))
            await db.commit()
        except Exception:
            await db.rollback()
        try:
            stats.update(await _migrate_symptom_tags_to_goods_tags(db))
            await db.commit()
        except Exception:
            await db.rollback()
        try:
            stats.update(await _drop_symptom_tags_column(db))
            await db.commit()
        except Exception:
            await db.rollback()
    return stats
