"""
Migrate legacy allergy text fields (drug_allergies, food_allergies, other_allergies)
into the unified JSON `allergies` field on HealthProfile.

Idempotent: skips records where allergies already has a value.

Usage:
    cd backend
    python -m scripts.migrate_allergy_data
"""

import asyncio
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.models import HealthProfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ALLERGY_PRESETS = [
    "青霉素", "头孢类", "磺胺类", "阿司匹林",
    "海鲜/贝壳类", "牛奶/乳制品", "鸡蛋", "花生/坚果类", "小麦/面筋",
    "花粉", "尘螨", "动物皮毛", "乳胶", "酒精",
]

SPLIT_PATTERN = re.compile(r"[,，、;\s;]+")


def _split_text(text: str | None) -> list[str]:
    if not text or not text.strip():
        return []
    parts = SPLIT_PATTERN.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _match_preset(item: str) -> str | None:
    """Return preset name if item fuzzy-matches any preset (substring match)."""
    item_lower = item.lower()
    for preset in ALLERGY_PRESETS:
        if item_lower in preset.lower() or preset.lower() in item_lower:
            return preset
    return None


def _merge_allergies(drug_text: str | None, food_text: str | None, other_text: str | None) -> list:
    seen_presets: set[str] = set()
    seen_custom: set[str] = set()
    result: list = []

    all_items: list[str] = []
    all_items.extend(_split_text(drug_text))
    all_items.extend(_split_text(food_text))
    all_items.extend(_split_text(other_text))

    for item in all_items:
        preset = _match_preset(item)
        if preset:
            if preset not in seen_presets:
                seen_presets.add(preset)
                result.append(preset)
        else:
            if item not in seen_custom:
                seen_custom.add(item)
                result.append({"type": "custom", "value": item})

    return result


async def migrate(db: AsyncSession) -> int:
    result = await db.execute(select(HealthProfile))
    profiles = result.scalars().all()

    migrated = 0
    for hp in profiles:
        if hp.allergies:
            continue

        has_legacy = bool(
            (hp.drug_allergies and hp.drug_allergies.strip())
            or (hp.food_allergies and hp.food_allergies.strip())
            or (hp.other_allergies and hp.other_allergies.strip())
        )
        if not has_legacy:
            continue

        merged = _merge_allergies(hp.drug_allergies, hp.food_allergies, hp.other_allergies)
        if merged:
            hp.allergies = merged
            migrated += 1

    await db.flush()
    return migrated


async def main():
    logger.info("Starting allergy data migration ...")
    async with async_session() as db:
        try:
            count = await migrate(db)
            await db.commit()
            logger.info("Migration completed: %d profiles updated", count)
        except Exception:
            await db.rollback()
            logger.exception("Migration failed")
            raise


if __name__ == "__main__":
    asyncio.run(main())
