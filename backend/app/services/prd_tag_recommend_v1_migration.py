"""[PRD-TAG-RECOMMEND-V1 2026-05-20] 标签管理 + 问卷推荐配置 迁移

迁移内容：
1. 新建表：tags、goods_tags、questionnaire_recommend_config
2. questionnaire_template 表新增 4 个字段
3. 一次性把 9 种体质（平和/气虚/阳虚/阴虚/痰湿/湿热/血瘀/气郁/特禀）迁入「适用体质」分类的标签
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# 9 种体质
CONSTITUTION_TAGS = [
    "平和质", "气虚质", "阳虚质", "阴虚质",
    "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质",
]

# 7 类标签的初始示例（PRD 模块 3.3 示意中的标签）
INITIAL_TAGS = [
    # 症状类
    ("symptom", ["疲劳", "气短", "自汗", "失眠", "头痛", "腰酸"]),
    # 功效类
    ("effect", ["补气", "健脾", "固表", "助眠", "活血", "清热"]),
    # 适用人群
    ("crowd", ["中老年", "女性", "男性", "青年", "亚健康人群"]),
    # 服务特性
    ("service", ["年卡", "单次", "上门检测", "线上咨询"]),
    # 使用场景
    ("scene", ["日常调理", "节气养生", "病后恢复"]),
    # 其他
    ("other", ["新品", "热销", "推荐"]),
]


async def _ensure_tag_tables(db: AsyncSession) -> dict[str, int]:
    """建表（幂等）"""
    stats = {"tags_created": 0, "goods_tags_created": 0, "recommend_cfg_created": 0}
    # tags 表
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS tags (
          id BIGINT PRIMARY KEY AUTO_INCREMENT,
          name VARCHAR(64) NOT NULL,
          category VARCHAR(32) NOT NULL,
          status TINYINT NOT NULL DEFAULT 1,
          goods_count INT DEFAULT 0,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_category_name (category, name),
          INDEX idx_category (category)
        )
    """))
    # goods_tags 表
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS goods_tags (
          goods_id BIGINT NOT NULL,
          tag_id BIGINT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (goods_id, tag_id),
          KEY idx_tag_id (tag_id)
        )
    """))
    # questionnaire_recommend_config 表
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
            # 不抛出，继续
    return {"template_columns_added": cols_added}


async def _seed_constitution_tags(db: AsyncSession) -> dict[str, int]:
    """把 9 种体质作为 constitution 类标签写入（幂等）"""
    created = 0
    for name in CONSTITUTION_TAGS:
        try:
            await db.execute(
                text(
                    "INSERT IGNORE INTO tags (name, category, status, goods_count, created_at, updated_at) "
                    "VALUES (:n, 'constitution', 1, 0, NOW(), NOW())"
                ),
                {"n": name},
            )
            created += 1
        except Exception:
            pass
    return {"constitution_tags_seeded": created}


async def _seed_initial_tags(db: AsyncSession) -> dict[str, int]:
    """种入示例标签（幂等）"""
    created = 0
    for cat, names in INITIAL_TAGS:
        for n in names:
            try:
                await db.execute(
                    text(
                        "INSERT IGNORE INTO tags (name, category, status, goods_count, created_at, updated_at) "
                        "VALUES (:n, :c, 1, 0, NOW(), NOW())"
                    ),
                    {"n": n, "c": cat},
                )
                created += 1
            except Exception:
                pass
    return {"initial_tags_seeded": created}


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
    """迁移入口：被 main.py lifespan 调用"""
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
            stats.update(await _seed_constitution_tags(db))
            stats.update(await _seed_initial_tags(db))
            stats.update(await _default_tcm_recommend_display(db))
            await db.commit()
        except Exception:
            await db.rollback()
    return stats
