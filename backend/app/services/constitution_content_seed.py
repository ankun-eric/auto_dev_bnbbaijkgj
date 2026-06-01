"""[PRD-TIZHI-OPTIM-V1 2026-06-01] 体质测评结果页运营内容默认种子。

为 9 种体质各预置一条「专属膳食套餐」与一条「门店服务」默认内容卡，
便于运营在后台直接看到并调整。仅在表为空时插入，避免覆盖运营已配置数据。

内容来源：体质↔套餐映射库（constitution_content）的推荐模板，按体质天蓝品牌调性整理。
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.core.database import async_session
from app.models.models import ConstitutionContentConfig

logger = logging.getLogger(__name__)

# 天蓝品牌主色（统一替代旧紫色）
BRAND_BLUE = "#0EA5E9"

# 每个体质的默认膳食套餐 / 门店服务文案
DEFAULT_MEALS = {
    "平和质": ("季节调养餐", "顺应四季，维持阴阳平衡的均衡膳食", "维持平衡"),
    "气虚质": ("补气养元餐", "黄芪山药入膳，补气固本改善乏力", "补气固本"),
    "阳虚质": ("温补阳气餐", "羊肉生姜温阳散寒，改善畏冷怕风", "温阳散寒"),
    "阴虚质": ("滋阴润燥餐", "银耳百合滋阴降火，缓解口干燥热", "滋阴降火"),
    "痰湿质": ("化痰祛湿餐", "薏米冬瓜化痰祛湿，清爽控重", "化痰祛湿"),
    "湿热质": ("清热祛湿餐", "绿豆苦瓜清利湿热，改善油腻", "清利湿热"),
    "血瘀质": ("活血化瘀餐", "山楂三七活血通络，改善气色", "活血通络"),
    "气郁质": ("疏肝解郁餐", "玫瑰佛手疏肝理气，舒缓情志", "疏肝理气"),
    "特禀质": ("增强免疫餐", "益生菌屏风方调和体质，增强抵抗", "调和抗敏"),
}

DEFAULT_STORES = {
    t: ("预约艾灸调理", "到店由专业理疗师根据您的体质匹配调理方案", "门店预约")
    for t in DEFAULT_MEALS
}


async def seed_constitution_content() -> dict:
    async with async_session() as db:
        existing = (
            await db.execute(select(func.count(ConstitutionContentConfig.id)))
        ).scalar() or 0
        if existing > 0:
            return {"skipped": True, "existing": int(existing)}

        rows = []
        for ctype, (title, subtitle, tag) in DEFAULT_MEALS.items():
            rows.append(
                ConstitutionContentConfig(
                    constitution_type=ctype,
                    section="meal",
                    title=title,
                    subtitle=subtitle,
                    tag=tag,
                    tag_color=BRAND_BLUE,
                    link_type="none",
                    button_text="了解详情",
                    sort_order=0,
                    enabled=True,
                )
            )
        for ctype, (title, subtitle, tag) in DEFAULT_STORES.items():
            rows.append(
                ConstitutionContentConfig(
                    constitution_type=ctype,
                    section="store",
                    title=title,
                    subtitle=subtitle,
                    tag=tag,
                    tag_color=BRAND_BLUE,
                    link_type="order",
                    link_value="moxibustion",
                    button_text="预约",
                    sort_order=0,
                    enabled=True,
                )
            )
        db.add_all(rows)
        await db.commit()
        logger.info("constitution_content_seed: 已插入 %d 条默认配置", len(rows))
        return {"skipped": False, "inserted": len(rows)}
