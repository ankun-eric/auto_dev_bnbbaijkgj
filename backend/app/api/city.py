import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import City
from app.schemas.city import (
    AdminCityListResponse,
    CityBrief,
    CityGroupResponse,
    CityListResponse,
    CityResponse,
    HotCityResponse,
    HotCitySetRequest,
    LocateResponse,
)

router = APIRouter(prefix="/api/cities", tags=["城市定位"])
admin_router = APIRouter(prefix="/api/admin/cities", tags=["管理后台-城市管理"])

admin_dep = require_role("admin")


# ════════════════════════════════════════
#  用户端 API（无需登录）
# ════════════════════════════════════════


@router.get("/list", response_model=CityListResponse)
async def get_city_list(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
):
    query = select(City).where(City.is_active == True)  # noqa: E712

    if keyword:
        kw = f"%{keyword}%"
        query = query.where(
            or_(
                City.name.like(kw),
                City.short_name.like(kw),
                City.pinyin.like(kw),
            )
        )

    query = query.order_by(City.first_letter.asc(), City.pinyin.asc())
    result = await db.execute(query)
    cities = result.scalars().all()

    groups_dict: dict[str, list[CityBrief]] = {}
    for c in cities:
        brief = CityBrief.model_validate(c)
        groups_dict.setdefault(c.first_letter, []).append(brief)

    groups = [
        CityGroupResponse(letter=letter, cities=city_list)
        for letter, city_list in sorted(groups_dict.items())
    ]

    return CityListResponse(groups=groups, total=len(cities))


@router.get("/hot", response_model=HotCityResponse)
async def get_hot_cities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(City)
        .where(City.is_active == True, City.is_hot == True)  # noqa: E712
        .order_by(City.hot_sort.asc())
    )
    cities = [CityBrief.model_validate(c) for c in result.scalars().all()]
    return HotCityResponse(cities=cities)


@router.get("/locate", response_model=LocateResponse)
async def locate_city(
    lng: float = Query(..., description="经度"),
    lat: float = Query(..., description="纬度"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(City).where(
            City.is_active == True,  # noqa: E712
            City.longitude.isnot(None),
            City.latitude.isnot(None),
        )
    )
    cities = result.scalars().all()

    if not cities:
        return LocateResponse(city=None, message="暂无城市数据")

    nearest = None
    min_dist = float("inf")
    for c in cities:
        dist = math.sqrt(
            (float(c.longitude) - lng) ** 2 + (float(c.latitude) - lat) ** 2
        )
        if dist < min_dist:
            min_dist = dist
            nearest = c

    if nearest is None:
        return LocateResponse(city=None, message="未找到匹配城市")

    return LocateResponse(city=CityBrief.model_validate(nearest), message="ok")


# ════════════════════════════════════════
#  管理端 API（需要 admin 权限）
# ════════════════════════════════════════


@admin_router.get("/list", response_model=AdminCityListResponse)
async def admin_city_list(
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(City)
    count_query = select(func.count(City.id))

    if keyword:
        kw = f"%{keyword}%"
        filt = or_(
            City.name.like(kw),
            City.short_name.like(kw),
            City.pinyin.like(kw),
        )
        query = query.where(filt)
        count_query = count_query.where(filt)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(City.first_letter.asc(), City.pinyin.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [CityResponse.model_validate(c) for c in result.scalars().all()]

    return AdminCityListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@admin_router.get("/hot")
async def admin_hot_cities(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(City)
        .where(City.is_hot == True)  # noqa: E712
        .order_by(City.hot_sort.asc())
    )
    cities = [CityResponse.model_validate(c) for c in result.scalars().all()]
    return {"cities": cities}


@admin_router.post("/hot")
async def admin_set_hot_cities(
    data: HotCitySetRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # Clear existing hot cities
    result = await db.execute(
        select(City).where(City.is_hot == True)  # noqa: E712
    )
    for city in result.scalars().all():
        city.is_hot = False
        city.hot_sort = 0

    # Set new hot cities
    for idx, city_id in enumerate(data.city_ids):
        result = await db.execute(select(City).where(City.id == city_id))
        city = result.scalar_one_or_none()
        if not city:
            raise HTTPException(status_code=404, detail=f"城市 ID {city_id} 不存在")
        city.is_hot = True
        city.hot_sort = idx + 1

    await db.flush()
    return {"message": "热门城市设置成功"}


@admin_router.delete("/hot/{city_id}")
async def admin_remove_hot_city(
    city_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(City).where(City.id == city_id))
    city = result.scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=404, detail="城市不存在")

    city.is_hot = False
    city.hot_sort = 0
    await db.flush()
    return {"message": "已移除热门城市"}
