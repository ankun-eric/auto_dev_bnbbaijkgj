"""[2026-05-05 用户地址改造 PRD v1.0] 老地址数据迁移脚本（一次性）。

策略（A+B 组合的 Phase 1）：
- 扫描所有 UserAddress 记录
- 把 name → consignee_name, phone → consignee_phone, street → detail（若新字段为空）
- 用正则 + 行政区划库尝试从老 name/phone/province/city/district/street 中提取省市县
- 拆不出来的：将原 street/detail 整段塞入 detail，省/市/县留空（标记为待补全）
- 输出迁移报告：成功条数 / 失败条数 / 失败样本

执行方式（容器内）：
    docker exec <backend-container> python -m backend.scripts.migrate_addresses_v2
或：
    python -m app.scripts.migrate_addresses_v2  # 在 backend 容器内 cwd=/app
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# 兼容容器内执行：sys.path 添加 backend 根目录
_HERE = Path(__file__).resolve()
_BACKEND_ROOT = _HERE.parent.parent  # backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.models import UserAddress  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_addresses_v2")


def _load_regions() -> dict[str, Any]:
    p = _BACKEND_ROOT / "app" / "data" / "regions.json"
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_region_index(regions: dict[str, Any]):
    """构建快速匹配表：省名→省条目；(省名,市名)→市条目；(省,市,区)→区代码。"""
    province_map: dict[str, dict] = {}
    for prov in regions.get("provinces", []):
        province_map[prov["name"]] = prov
        # 省名简写：去掉 省/市/自治区/壮族 等
        for short in (prov["name"].replace("省", "").replace("市", "").replace("自治区", "").replace("回族", "").replace("壮族", "").replace("维吾尔", ""),):
            if short and short not in province_map:
                province_map[short] = prov
    return province_map


def _try_split(text: str, province_map: dict[str, dict]) -> dict[str, str]:
    """简单正则：尝试从文本中提取 省/市/县。"""
    if not text:
        return {}
    # 顺序尝试每个省
    for pname, prov in province_map.items():
        if pname in text:
            for city in prov.get("cities", []):
                cname = city["name"]
                if cname in text or cname.replace("市", "") in text:
                    for dist in city.get("districts", []):
                        dname = dist["name"]
                        if dname in text or dname.replace("区", "").replace("县", "") in text:
                            return {
                                "province": prov["name"],
                                "province_code": prov["code"],
                                "city": cname,
                                "city_code": city["code"],
                                "district": dname,
                                "district_code": dist["code"],
                            }
                    # 仅匹配到省+市
                    return {
                        "province": prov["name"],
                        "province_code": prov["code"],
                        "city": cname,
                        "city_code": city["code"],
                    }
            return {"province": prov["name"], "province_code": prov["code"]}
    return {}


async def main():
    regions = _load_regions()
    province_map = _build_region_index(regions)

    success = 0
    failed = 0
    failed_samples: list[dict] = []

    async with async_session() as db:
        res = await db.execute(select(UserAddress))
        addrs = res.scalars().all()
        logger.info("共扫描到 %d 条地址记录", len(addrs))

        for addr in addrs:
            changed = False
            # 1) 同步 name/phone → consignee_*
            if not addr.consignee_name and addr.name:
                addr.consignee_name = addr.name
                changed = True
            if not addr.consignee_phone and addr.phone:
                addr.consignee_phone = addr.phone
                changed = True
            # 2) street → detail
            if not addr.detail and addr.street:
                addr.detail = addr.street
                changed = True
            # 3) 尝试拆解省市县（若已有则跳过）
            if not (addr.province and addr.city and addr.district):
                # 拼装可供匹配的文本
                hay = " ".join(filter(None, [
                    addr.province or "", addr.city or "", addr.district or "",
                    addr.street or "", addr.detail or "",
                ]))
                hit = _try_split(hay, province_map)
                if hit:
                    if hit.get("province") and not addr.province:
                        addr.province = hit["province"]
                        addr.province_code = hit.get("province_code") or addr.province_code
                        changed = True
                    if hit.get("city") and not addr.city:
                        addr.city = hit["city"]
                        addr.city_code = hit.get("city_code") or addr.city_code
                        changed = True
                    if hit.get("district") and not addr.district:
                        addr.district = hit["district"]
                        addr.district_code = hit.get("district_code") or addr.district_code
                        changed = True

            # 4) is_deleted 默认 False
            if addr.is_deleted is None:
                addr.is_deleted = False
                changed = True

            if addr.province and addr.city and addr.district:
                success += 1
            else:
                failed += 1
                if len(failed_samples) < 5:
                    failed_samples.append({
                        "id": addr.id,
                        "user_id": addr.user_id,
                        "old_province": addr.province,
                        "old_city": addr.city,
                        "old_street": addr.street,
                        "old_detail": addr.detail,
                    })

            if changed:
                db.add(addr)

        await db.commit()

    logger.info("迁移完成：成功 %d 条，待补全 %d 条", success, failed)
    if failed_samples:
        logger.info("失败样本（前 5 条）：%s", json.dumps(failed_samples, ensure_ascii=False, indent=2))
    print(json.dumps({
        "total": success + failed,
        "success": success,
        "needs_completion": failed,
        "failed_samples": failed_samples,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
