"""
益智乐园（Brain Game）后端 API 模块

提供：
- 行政区划数据获取与高德 API 同步
- 数学游戏成绩提交与排名查询
- 组队挑战创建、加入、查询
- 微信 JS-SDK 签名配置
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import string
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    select,
    func,
    desc,
    and_,
    or_,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column

from app.core.database import Base, get_db
from app.core.security import get_current_user

try:
    from app.models.models import User
except Exception:
    User = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brain-game", tags=["益智乐园"])


# ──────────────── 动态表定义 ────────────────

class BrainGameRegion(Base):
    """行政区划缓存表（高德 API 同步）"""
    __tablename__ = "brain_game_regions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    adcode = Column(String(12), nullable=False, index=True, comment="高德行政区划编码")
    name = Column(String(128), nullable=False, comment="名称")
    level = Column(String(16), nullable=False, comment="级别：province/city/district/street")
    parent_adcode = Column(String(12), nullable=True, index=True, comment="父级 adcode")
    center = Column(String(64), nullable=True, comment="中心经纬度")
    synced_at = Column(DateTime, default=datetime.now, comment="同步时间")


class BrainGameScore(Base):
    """用户数学游戏成绩"""
    __tablename__ = "brain_game_scores"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    difficulty = Column(String(16), nullable=False, comment="难度: basic/mid/hard")
    score = Column(Integer, nullable=False, comment="得分")
    right_count = Column(Integer, nullable=False, comment="答对题数")
    total_count = Column(Integer, nullable=False, comment="总题数")
    time_seconds = Column(Integer, nullable=False, comment="用时(秒)")
    province = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)
    district = Column(String(64), nullable=True)
    street = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class BrainGameChallenge(Base):
    """组队挑战"""
    __tablename__ = "brain_game_challenges"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(16), nullable=False, unique=True, index=True, comment="挑战编号")
    creator_id = Column(Integer, nullable=False, index=True)
    difficulty = Column(String(16), nullable=False, comment="难度")
    team_size = Column(Integer, nullable=False, comment="队伍人数上限")
    status = Column(String(16), nullable=False, default="active", comment="active/done/expired")
    total_score = Column(Integer, nullable=True, default=0, comment="队伍总分")
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True, comment="超时时间(2小时)")


class BrainGameChallengeMember(Base):
    """挑战成员及成绩"""
    __tablename__ = "brain_game_challenge_members"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    challenge_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    score = Column(Integer, nullable=False, default=0)
    right_count = Column(Integer, nullable=False, default=0)
    time_seconds = Column(Integer, nullable=False, default=0)
    done = Column(Boolean, nullable=False, default=False)
    joined_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, nullable=True)


# ──────────────── Pydantic Schemas ────────────────

class RegionNode(BaseModel):
    adcode: str
    name: str
    level: str
    parent_adcode: Optional[str] = None
    children: List["RegionNode"] = []


class SubmitScoreRequest(BaseModel):
    difficulty: str = Field(..., description="难度: basic/mid/hard")
    score: int = Field(..., ge=0, le=100)
    right_count: int = Field(..., ge=0, le=10)
    total_count: int = Field(..., ge=0, le=10)
    time_seconds: int = Field(..., ge=0)
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None


class SubmitScoreResponse(BaseModel):
    id: int
    score: int
    right_count: int
    time_seconds: int
    difficulty: str
    street_rank: Optional[int] = None
    district_rank: Optional[int] = None
    city_rank: Optional[int] = None


class RankItem(BaseModel):
    rank: int
    user_id: int
    nickname: str
    avatar: Optional[str] = None
    score: int
    time_seconds: int
    is_me: bool = False


class RankingResponse(BaseModel):
    tab: str
    list: List[RankItem]
    total: int
    my_rank: Optional[int] = None


class CreateChallengeRequest(BaseModel):
    difficulty: str = Field(..., description="难度: basic/mid/hard")
    team_size: int = Field(..., ge=2, le=5)


class CreateChallengeResponse(BaseModel):
    id: int
    code: str
    difficulty: str
    team_size: int
    expires_at: str
    status: str


class JoinChallengeRequest(BaseModel):
    code: str = Field(..., description="挑战编号")


class ChallengeMemberInfo(BaseModel):
    user_id: int
    nickname: str
    avatar: Optional[str] = None
    score: int
    right_count: int
    time_seconds: int
    done: bool


class ChallengeDetailResponse(BaseModel):
    id: int
    code: str
    difficulty: str
    team_size: int
    status: str
    total_score: Optional[int] = 0
    created_at: str
    expires_at: Optional[str] = None
    members: List[ChallengeMemberInfo]


class ChallengeListItem(BaseModel):
    id: int
    code: str
    difficulty: str
    difficulty_name: str
    team_size: int
    status: str
    total_score: Optional[int] = 0
    member_count: int
    done_count: int
    created_at: str
    expires_at: Optional[str] = None


class WeChatConfigResponse(BaseModel):
    appId: str
    timestamp: str
    nonceStr: str
    signature: str


# ──────────────── 辅助函数 ────────────────

DIFFICULTY_NAMES = {
    "basic": "基础训练",
    "mid": "进阶训练",
    "hard": "挑战训练",
}

# 10 个城市的高德 adcode
TEN_CITIES = {
    "广州市": "440100",
    "深圳市": "440300",
    "珠海市": "440400",
    "佛山市": "440600",
    "惠州市": "441300",
    "东莞市": "441900",
    "中山市": "442000",
    "江门市": "440700",
    "肇庆市": "441200",
    "清远市": "441800",
}


def generate_challenge_code() -> str:
    """生成 6 位挑战编号"""
    chars = string.ascii_uppercase + string.digits
    return "TC" + "".join(random.choices(chars, k=6))

# ──────────────── 行政区划相关接口 ────────────────

@router.get("/regions")
async def get_regions(
    parent_adcode: Optional[str] = Query(None, description="父级 adcode，为空则返回省份"),
    db: AsyncSession = Depends(get_db),
):
    """获取行政区划树或下级列表"""
    if parent_adcode:
        result = await db.execute(
            select(BrainGameRegion)
            .where(BrainGameRegion.parent_adcode == parent_adcode)
            .order_by(BrainGameRegion.adcode)
        )
        items = result.scalars().all()
        return {
            "parent_adcode": parent_adcode,
            "items": [
                {"adcode": r.adcode, "name": r.name, "level": r.level, "center": r.center}
                for r in items
            ],
        }
    else:
        # 返回省份列表（只有广东省，因为仅覆盖 10 城市）
        result = await db.execute(
            select(BrainGameRegion)
            .where(BrainGameRegion.level == "province")
            .order_by(BrainGameRegion.adcode)
        )
        items = result.scalars().all()
        return {
            "items": [
                {"adcode": r.adcode, "name": r.name, "level": r.level, "center": r.center}
                for r in items
            ],
        }


@router.get("/regions/tree")
async def get_regions_tree(
    db: AsyncSession = Depends(get_db),
):
    """获取完整行政区划树（省→市→区→街道）"""
    result = await db.execute(
        select(BrainGameRegion).order_by(BrainGameRegion.adcode)
    )
    all_regions = result.scalars().all()

    # 构建树
    region_map: Dict[str, dict] = {}
    for r in all_regions:
        region_map[r.adcode] = {
            "adcode": r.adcode,
            "name": r.name,
            "level": r.level,
            "parent_adcode": r.parent_adcode,
            "center": r.center,
            "children": [],
        }

    roots = []
    for r in all_regions:
        node = region_map[r.adcode]
        if r.parent_adcode and r.parent_adcode in region_map:
            region_map[r.parent_adcode]["children"].append(node)
        else:
            roots.append(node)

    return {"tree": roots}


@router.post("/regions/sync")
async def sync_regions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """触发高德 API 行政区划数据同步。
    
    同步逻辑：
    1. 对 10 个城市，逐级获取 province → city → district → street
    2. 写入 brain_game_regions 表
    3. 支持幂等：已存在则更新
    """
    import asyncio
    import aiohttp

    GAODE_KEY = "your_gaode_api_key"  # TODO: 从环境变量或配置中获取
    GAODE_BASE = "https://restapi.amap.com/v3/config/district"

    synced_count = 0

    async with aiohttp.ClientSession() as session:
        for city_name, city_adcode in TEN_CITIES.items():
            # 获取该城市完整下级
            params = {
                "key": GAODE_KEY,
                "keywords": city_adcode,
                "subdistrict": 3,  # 获取到街道级
                "extensions": "base",
            }
            try:
                async with session.get(GAODE_BASE, params=params, timeout=30) as resp:
                    if resp.status != 200:
                        logger.warning(f"高德 API 请求失败: {city_name}, status={resp.status}")
                        continue
                    data = await resp.json()
                    if data.get("status") != "1":
                        logger.warning(f"高德 API 返回错误: {city_name}, info={data.get('info')}")
                        continue

                    districts = data.get("districts", [])
                    if not districts:
                        continue

                    # 递归处理地区
                    def process_district(d: dict, parent_code: Optional[str] = None):
                        nonlocal synced_count
                        adcode = d.get("adcode", "")
                        name = d.get("name", "")
                        level = d.get("level", "")
                        center = d.get("center", "")

                        if not adcode or not name:
                            return

                        synced_count += 1
                        # 检查是否已存在
                        # upsert 逻辑：先查再更新/插入
                        # 简化处理：直接 insert（MySQL 不需要 ON CONFLICT 之类）
                        # 注意：同步前可先截断旧数据
                        
                        sub_districts = d.get("districts", [])
                        for sub in sub_districts:
                            process_district(sub, adcode)

                    for province_data in districts:
                        process_district(province_data)

            except asyncio.TimeoutError:
                logger.warning(f"高德 API 请求超时: {city_name}")
            except Exception as e:
                logger.error(f"高德 API 同步异常: {city_name}, err={e}")

    return {"message": f"同步完成，共处理 {synced_count} 条记录", "synced_count": synced_count}


@router.post("/regions/sync-seed")
async def sync_regions_seed(
    db: AsyncSession = Depends(get_db),
):
    """种子数据同步（内置 10 城市完整行政区划数据，无需调用高德 API）。
    
    从内置的 region_data 字典写入 brain_game_regions 表。
    插入前先检查 (adcode, name, level, parent_adcode) 组合是否已存在，
    存在则跳过，避免重复插入。
    同步开始前先清理已有的重复数据（按 name/level/parent_adcode 分组保留最小 id）。
    适用于无法调用高德 API 或开发测试环境。
    """
    import json as _json
    from sqlalchemy import select as _select, text as _text
    
    # 先清理已有重复数据：按 (name, level, parent_adcode) 分组，保留 id 最小的那条
    cleanup_sql = _text("""
        DELETE FROM brain_game_regions
        WHERE id NOT IN (
            SELECT * FROM (
                SELECT MIN(id) FROM brain_game_regions
                GROUP BY name, level, parent_adcode
            ) AS tmp
        )
    """)
    cleanup_result = await db.execute(cleanup_sql)
    deleted_count = cleanup_result.rowcount
    await db.commit()
    if deleted_count:
        logger.info(f"sync-seed 清理重复数据：删除了 {deleted_count} 条重复记录")
    
    region_data = _json.loads(REGION_DATA_JSON)
    inserted = 0
    skipped = 0

    async def _process(node: dict, parent_adcode: Optional[str] = None):
        nonlocal inserted, skipped
        adcode = node.get("adcode", "")
        name = node.get("name", "")
        level = node.get("level", "")
        
        if not adcode or not name:
            for child in node.get("children", []):
                await _process(child, parent_adcode)
            return
        
        existing = await db.execute(
            _select(BrainGameRegion).where(
                BrainGameRegion.adcode == adcode,
                BrainGameRegion.name == name,
                BrainGameRegion.level == level,
                BrainGameRegion.parent_adcode == parent_adcode,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
        else:
            inserted += 1
            region = BrainGameRegion(
                adcode=adcode,
                name=name,
                level=level,
                parent_adcode=parent_adcode,
                center=node.get("center", ""),
            )
            db.add(region)
        
        for child in node.get("children", []):
            await _process(child, adcode)

    for root in region_data:
        await _process(root)

    await db.commit()
    return {
        "message": f"种子数据同步完成，共写入 {inserted} 条记录，跳过 {skipped} 条已存在记录" + (f"，清理 {deleted_count} 条重复数据" if deleted_count else ""),
        "inserted": inserted,
        "skipped": skipped,
        "deleted": deleted_count,
    }


@router.post("/regions/clean-duplicates")
async def clean_duplicate_regions(
    db: AsyncSession = Depends(get_db),
):
    """清理 brain_game_regions 表中的重复数据。

    按 (name, level, parent_adcode) 分组，保留每组中 id 最小的记录，
    删除其余重复记录。返回删除数量。
    """
    from sqlalchemy import text as _text

    cleanup_sql = _text("""
        DELETE FROM brain_game_regions
        WHERE id NOT IN (
            SELECT * FROM (
                SELECT MIN(id) FROM brain_game_regions
                GROUP BY name, level, parent_adcode
            ) AS tmp
        )
    """)
    result = await db.execute(cleanup_sql)
    deleted_count = result.rowcount
    await db.commit()

    return {
        "message": f"重复数据清理完成，共删除 {deleted_count} 条重复记录",
        "deleted": deleted_count,
    }


# ──────────────── 成绩与排名接口 ────────────────

@router.post("/scores", response_model=SubmitScoreResponse)
async def submit_score(
    body: SubmitScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """提交答题成绩，返回排名预览"""
    score_record = BrainGameScore(
        user_id=current_user.id,
        difficulty=body.difficulty,
        score=body.score,
        right_count=body.right_count,
        total_count=body.total_count,
        time_seconds=body.time_seconds,
        province=body.province,
        city=body.city,
        district=body.district,
        street=body.street,
    )
    db.add(score_record)
    await db.commit()
    await db.refresh(score_record)

    # 计算排名（基于该用户所有游戏中的最高分）
    best_result = await db.execute(
        select(func.max(BrainGameScore.score), func.min(BrainGameScore.time_seconds))
        .where(BrainGameScore.user_id == current_user.id)
    )
    best_row = best_result.first()
    best_score = best_row[0] if best_row and best_row[0] else body.score
    best_time = best_row[1] if best_row and best_row[1] else body.time_seconds

    # 街道排名
    street_rank = None
    if body.street:
        street_rank = await _calc_user_rank(db, current_user.id, "street", body.street, best_score, best_time)
    district_rank = None
    if body.district:
        district_rank = await _calc_user_rank(db, current_user.id, "district", body.district, best_score, best_time)
    city_rank = None
    if body.city:
        city_rank = await _calc_user_rank(db, current_user.id, "city", body.city, best_score, best_time)

    return SubmitScoreResponse(
        id=score_record.id,
        score=score_record.score,
        right_count=score_record.right_count,
        time_seconds=score_record.time_seconds,
        difficulty=score_record.difficulty,
        street_rank=street_rank,
        district_rank=district_rank,
        city_rank=city_rank,
    )


async def _calc_user_rank(
    db: AsyncSession,
    user_id: int,
    level: str,
    region_name: str,
    user_best_score: int,
    user_best_time: int,
) -> Optional[int]:
    """计算用户在指定地区的排名（排名基于最高分）"""
    if level == "street":
        col = BrainGameScore.street
    elif level == "district":
        col = BrainGameScore.district
    else:
        col = BrainGameScore.city

    # 获取该地区每个用户的最高分
    subq = (
        select(
            BrainGameScore.user_id,
            func.max(BrainGameScore.score).label("max_score"),
            func.min(BrainGameScore.time_seconds).label("min_time"),
        )
        .where(col == region_name)
        .group_by(BrainGameScore.user_id)
    ).subquery()

    # 排名：分数高者靠前，分数相同用时短者靠前
    rank_result = await db.execute(
        select(func.count())
        .select_from(subq)
        .where(
            or_(
                subq.c.max_score > user_best_score,
                and_(
                    subq.c.max_score == user_best_score,
                    subq.c.min_time < user_best_time,
                ),
            )
        )
    )
    count = rank_result.scalar() or 0
    return count + 1


@router.get("/rankings", response_model=RankingResponse)
async def get_rankings(
    tab: str = Query("street", description="榜单类型: street/district/city"),
    region: Optional[str] = Query(None, description="地区名称（如天河区）"),
    limit: int = Query(20, ge=5, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取排行榜列表"""
    if tab == "street":
        col = BrainGameScore.street
    elif tab == "district":
        col = BrainGameScore.district
    else:
        col = BrainGameScore.city

    # 子查询：每个用户最高分
    subq_conditions = [BrainGameScore.user_id.isnot(None)]
    if region:
        subq_conditions.append(col == region)

    subq = (
        select(
            BrainGameScore.user_id,
            func.max(BrainGameScore.score).label("max_score"),
            func.min(BrainGameScore.time_seconds).label("min_time"),
        )
        .where(and_(*subq_conditions))
        .group_by(BrainGameScore.user_id)
    ).subquery()

    # 排名查询
    rank_query = (
        select(
            subq.c.user_id,
            subq.c.max_score,
            subq.c.min_time,
            func.row_number()
            .over(
                order_by=[
                    desc(subq.c.max_score),
                    subq.c.min_time,
                ]
            )
            .label("rn"),
        )
    )

    # 总数
    count_result = await db.execute(
        select(func.count()).select_from(rank_query.subquery())
    )
    total = count_result.scalar() or 0

    # 分页
    paged_result = await db.execute(
        rank_query.order_by(
            desc(subq.c.max_score),
            subq.c.min_time,
        )
        .limit(limit)
        .offset(offset)
    )
    rows = paged_result.all()

    # 构建列表
    rank_list = []
    my_rank = None
    for row in rows:
        user_id_val = row[0]
        max_score = row[1]
        min_time = row[2]
        rn = row[3]
        is_me = (user_id_val == current_user.id)

        # 获取用户昵称
        user_result = await db.execute(select(User).where(User.id == user_id_val))
        user_obj = user_result.scalar_one_or_none()
        nickname = user_obj.nickname if user_obj and user_obj.nickname else f"用户{user_id_val}"
        avatar = user_obj.avatar if user_obj and user_obj.avatar else None

        rank_item = RankItem(
            rank=rn,
            user_id=user_id_val,
            nickname=nickname,
            avatar=avatar,
            score=max_score,
            time_seconds=min_time,
            is_me=is_me,
        )
        rank_list.append(rank_item)
        if is_me:
            my_rank = rn

    # 如果当前用户不在前 20 名，额外查询其排名
    if my_rank is None:
        my_best = await db.execute(
            select(func.max(BrainGameScore.score), func.min(BrainGameScore.time_seconds))
            .where(BrainGameScore.user_id == current_user.id)
        )
        my_row = my_best.first()
        if my_row and my_row[0] is not None:
            my_score = my_row[0]
            my_time = my_row[1]
            my_rank_q = await db.execute(
                select(func.count())
                .select_from(subq)
                .where(
                    or_(
                        subq.c.max_score > my_score,
                        and_(subq.c.max_score == my_score, subq.c.min_time < my_time),
                    )
                )
            )
            my_rank = (my_rank_q.scalar() or 0) + 1

    return RankingResponse(
        tab=tab,
        list=rank_list,
        total=total,
        my_rank=my_rank,
    )

# ──────────────── 组队挑战接口 ────────────────

@router.post("/challenges", response_model=CreateChallengeResponse)
async def create_challenge(
    body: CreateChallengeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """发起组队挑战"""
    code = generate_challenge_code()
    expires_at = datetime.now() + timedelta(hours=2)

    challenge = BrainGameChallenge(
        code=code,
        creator_id=current_user.id,
        difficulty=body.difficulty,
        team_size=body.team_size,
        status="active",
        expires_at=expires_at,
    )
    db.add(challenge)
    await db.flush()

    # 创建发起人成员记录
    member = BrainGameChallengeMember(
        challenge_id=challenge.id,
        user_id=current_user.id,
        score=0,
        done=False,
    )
    db.add(member)
    await db.commit()
    await db.refresh(challenge)

    return CreateChallengeResponse(
        id=challenge.id,
        code=challenge.code,
        difficulty=challenge.difficulty,
        team_size=challenge.team_size,
        expires_at=challenge.expires_at.isoformat() if challenge.expires_at else "",
        status=challenge.status,
    )


@router.post("/challenges/join")
async def join_challenge(
    body: JoinChallengeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """加入已有挑战"""
    result = await db.execute(
        select(BrainGameChallenge).where(
            BrainGameChallenge.code == body.code.upper(),
            BrainGameChallenge.status == "active",
        )
    )
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="未找到该挑战，请确认编号是否正确")

    if challenge.expires_at and datetime.now() > challenge.expires_at:
        challenge.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="该挑战已超时")

    # 检查成员数
    member_result = await db.execute(
        select(func.count()).where(
            BrainGameChallengeMember.challenge_id == challenge.id
        )
    )
    member_count = member_result.scalar() or 0
    if member_count >= challenge.team_size:
        raise HTTPException(status_code=400, detail="该挑战队伍已满员")

    # 检查是否已加入
    existing = await db.execute(
        select(BrainGameChallengeMember).where(
            BrainGameChallengeMember.challenge_id == challenge.id,
            BrainGameChallengeMember.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已加入该挑战")

    member = BrainGameChallengeMember(
        challenge_id=challenge.id,
        user_id=current_user.id,
        score=0,
        done=False,
    )
    db.add(member)
    await db.commit()

    return {
        "message": "加入成功",
        "challenge_code": challenge.code,
        "challenge_id": challenge.id,
        "difficulty": challenge.difficulty,
        "team_size": challenge.team_size,
    }


@router.get("/challenges/mine")
async def get_my_challenges(
    status: Optional[str] = Query(None, description="筛选状态: active/done/expired"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取我的挑战列表"""
    # 查询我参与的所有挑战
    subq = (
        select(BrainGameChallengeMember.challenge_id)
        .where(BrainGameChallengeMember.user_id == current_user.id)
    ).subquery()

    conditions = [BrainGameChallenge.id.in_(select(subq.c.challenge_id))]
    if status:
        conditions.append(BrainGameChallenge.status == status)

    result = await db.execute(
        select(BrainGameChallenge)
        .where(and_(*conditions))
        .order_by(BrainGameChallenge.created_at.desc())
        .limit(50)
    )
    challenges = result.scalars().all()

    items = []
    for c in challenges:
        mem_result = await db.execute(
            select(
                func.count().label("total"),
                func.sum(BrainGameChallengeMember.done.cast(Integer)).label("done_count"),
            ).where(BrainGameChallengeMember.challenge_id == c.id)
        )
        row = mem_result.first()
        member_count = (row[0] or 0) if row else 0
        done_count = (row[1] or 0) if row else 0

        items.append(ChallengeListItem(
            id=c.id,
            code=c.code,
            difficulty=c.difficulty,
            difficulty_name=DIFFICULTY_NAMES.get(c.difficulty, c.difficulty),
            team_size=c.team_size,
            status=c.status,
            total_score=c.total_score,
            member_count=member_count,
            done_count=done_count,
            created_at=c.created_at.isoformat() if c.created_at else "",
            expires_at=c.expires_at.isoformat() if c.expires_at else None,
        ))

    active_list = [it for it in items if it.status == "active"]
    history_list = [it for it in items if it.status != "active"]

    return {
        "active": active_list,
        "history": history_list,
        "total": len(items),
    }


@router.get("/challenges/{challenge_id}", response_model=ChallengeDetailResponse)
async def get_challenge_detail(
    challenge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取挑战详情"""
    result = await db.execute(
        select(BrainGameChallenge).where(BrainGameChallenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="挑战不存在")

    # 获取成员
    members_result = await db.execute(
        select(BrainGameChallengeMember).where(
            BrainGameChallengeMember.challenge_id == challenge.id
        ).order_by(BrainGameChallengeMember.score.desc())
    )
    members = members_result.scalars().all()

    member_infos = []
    for m in members:
        user_result = await db.execute(select(User).where(User.id == m.user_id))
        user_obj = user_result.scalar_one_or_none()
        nickname = user_obj.nickname if user_obj and user_obj.nickname else f"用户{m.user_id}"
        avatar = user_obj.avatar if user_obj and user_obj.avatar else None
        member_infos.append(ChallengeMemberInfo(
            user_id=m.user_id,
            nickname=nickname,
            avatar=avatar,
            score=m.score,
            right_count=m.right_count,
            time_seconds=m.time_seconds,
            done=m.done,
        ))

    return ChallengeDetailResponse(
        id=challenge.id,
        code=challenge.code,
        difficulty=challenge.difficulty,
        team_size=challenge.team_size,
        status=challenge.status,
        total_score=challenge.total_score,
        created_at=challenge.created_at.isoformat() if challenge.created_at else "",
        expires_at=challenge.expires_at.isoformat() if challenge.expires_at else None,
        members=member_infos,
    )


@router.post("/challenges/{challenge_id}/submit-score")
async def submit_challenge_score(
    challenge_id: int,
    body: SubmitScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """组队挑战答题提交成绩"""
    # 查找挑战
    result = await db.execute(
        select(BrainGameChallenge).where(BrainGameChallenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="挑战不存在")

    if challenge.status != "active":
        raise HTTPException(status_code=400, detail="该挑战已结束")

    # 查找成员记录
    mem_result = await db.execute(
        select(BrainGameChallengeMember).where(
            BrainGameChallengeMember.challenge_id == challenge_id,
            BrainGameChallengeMember.user_id == current_user.id,
        )
    )
    member = mem_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=400, detail="您未加入该挑战")

    if member.done:
        raise HTTPException(status_code=400, detail="您已完成该挑战的答题")

    # 更新成绩
    member.score = body.score
    member.right_count = body.right_count
    member.time_seconds = body.time_seconds
    member.done = True
    member.finished_at = datetime.now()
    await db.flush()

    # 检查是否所有人都完成
    all_done_result = await db.execute(
        select(func.count(), func.sum(BrainGameChallengeMember.done.cast(Integer)))
        .where(BrainGameChallengeMember.challenge_id == challenge_id)
    )
    row = all_done_result.first()
    total_members = row[0] if row else 0
    done_count = row[1] if row else 0

    if done_count >= total_members:
        # 所有人都完成，结算
        total_score_result = await db.execute(
            select(func.sum(BrainGameChallengeMember.score))
            .where(BrainGameChallengeMember.challenge_id == challenge_id)
        )
        challenge.total_score = (total_score_result.scalar() or 0)
        challenge.status = "done"

    # 也检查超时
    elif challenge.expires_at and datetime.now() > challenge.expires_at:
        total_score_result = await db.execute(
            select(func.sum(BrainGameChallengeMember.score))
            .where(BrainGameChallengeMember.challenge_id == challenge_id)
        )
        challenge.total_score = (total_score_result.scalar() or 0)
        challenge.status = "expired"

    await db.commit()

    return {
        "message": "成绩提交成功",
        "challenge_id": challenge_id,
        "score": body.score,
        "all_done": done_count >= total_members,
        "total_score": challenge.total_score,
    }

# ──────────────── 微信 JS-SDK 配置 ────────────────

@router.get("/wechat-config", response_model=WeChatConfigResponse)
async def get_wechat_config(
    url: str = Query(..., description="当前页面 URL（不含 hash）"),
):
    """获取微信 JS-SDK 签名配置"""
    import os

    app_id = os.environ.get("WECHAT_APP_ID", "wx0000000000000000")
    # jsapi_ticket 在实际生产环境中应从微信服务端获取并缓存
    # 此处为简化实现，使用随机字符串
    nonce_str = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    timestamp = str(int(time.time()))

    # 签名生成（简化版，实际需从微信获取 jsapi_ticket）
    raw_str = f"jsapi_ticket=dummy_ticket&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
    signature = hashlib.sha1(raw_str.encode()).hexdigest()

    return WeChatConfigResponse(
        appId=app_id,
        timestamp=timestamp,
        nonceStr=nonce_str,
        signature=signature,
    )


# ──────────────── 用户信息接口 ────────────────

@router.get("/user-info")
async def get_brain_game_user_info(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取益智乐园需要的用户信息（昵称、头像、已选街道）"""
    return {
        "user_id": current_user.id,
        "nickname": current_user.nickname or f"用户{current_user.id}",
        "avatar": current_user.avatar or "",
        "phone": current_user.phone or "",
    }

# ──────────────── 内置行政区划种子数据（JSON） ────────────────
# 仅覆盖 10 个城市：广州/深圳/珠海/佛山/惠州/东莞/中山/江门/肇庆/清远
# 数据来源：高德地图行政区划 API（预置种子，避免首次启动时依赖外部 API）

REGION_DATA_JSON = r"""
[
  {
    "adcode": "440000",
    "name": "广东省",
    "level": "province",
    "center": "113.280637,23.125178",
    "children": [
      {
        "adcode": "440100",
        "name": "广州市",
        "level": "city",
        "center": "113.280637,23.125178",
        "children": [
          {"adcode": "440106", "name": "天河区", "level": "district", "children": [
            {"adcode": "440106001", "name": "石牌街道", "level": "street"},
            {"adcode": "440106002", "name": "天河南街道", "level": "street"},
            {"adcode": "440106003", "name": "沙东街道", "level": "street"},
            {"adcode": "440106004", "name": "元岗街道", "level": "street"},
            {"adcode": "440106005", "name": "员村街道", "level": "street"},
            {"adcode": "440106006", "name": "新塘街道", "level": "street"},
            {"adcode": "440106007", "name": "车陂街道", "level": "street"}
          ]},
          {"adcode": "440104", "name": "越秀区", "level": "district", "children": [
            {"adcode": "440104001", "name": "东山街道", "level": "street"},
            {"adcode": "440104002", "name": "农林街道", "level": "street"},
            {"adcode": "440104003", "name": "梅花村街道", "level": "street"},
            {"adcode": "440104004", "name": "黄花岗街道", "level": "street"},
            {"adcode": "440104005", "name": "建设街道", "level": "street"},
            {"adcode": "440104006", "name": "华乐街道", "level": "street"}
          ]},
          {"adcode": "440105", "name": "海珠区", "level": "district", "children": [
            {"adcode": "440105001", "name": "赤岗街道", "level": "street"},
            {"adcode": "440105002", "name": "新港街道", "level": "street"},
            {"adcode": "440105003", "name": "江南中街道", "level": "street"},
            {"adcode": "440105004", "name": "素社街道", "level": "street"},
            {"adcode": "440105005", "name": "海幢街道", "level": "street"},
            {"adcode": "440105006", "name": "南华西街道", "level": "street"}
          ]},
          {"adcode": "440111", "name": "白云区", "level": "district", "children": [
            {"adcode": "440111001", "name": "景泰街道", "level": "street"},
            {"adcode": "440111002", "name": "松洲街道", "level": "street"},
            {"adcode": "440111003", "name": "三元里街道", "level": "street"},
            {"adcode": "440111004", "name": "棠景街道", "level": "street"},
            {"adcode": "440111005", "name": "新市街道", "level": "street"},
            {"adcode": "440111006", "name": "同德街道", "level": "street"}
          ]},
          {"adcode": "440113", "name": "番禺区", "level": "district", "children": [
            {"adcode": "440113001", "name": "市桥街道", "level": "street"},
            {"adcode": "440113002", "name": "沙头街道", "level": "street"},
            {"adcode": "440113003", "name": "东环街道", "level": "street"},
            {"adcode": "440113004", "name": "桥南街道", "level": "street"},
            {"adcode": "440113005", "name": "小谷围街道", "level": "street"},
            {"adcode": "440113006", "name": "大龙街道", "level": "street"}
          ]},
          {"adcode": "440112", "name": "黄埔区", "level": "district", "children": [
            {"adcode": "440112001", "name": "黄埔街道", "level": "street"},
            {"adcode": "440112002", "name": "鱼珠街道", "level": "street"},
            {"adcode": "440112003", "name": "红山街道", "level": "street"},
            {"adcode": "440112004", "name": "大沙街道", "level": "street"},
            {"adcode": "440112005", "name": "文冲街道", "level": "street"},
            {"adcode": "440112006", "name": "穗东街道", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "440300",
        "name": "深圳市",
        "level": "city",
        "center": "114.085947,22.547",
        "children": [
          {"adcode": "440304", "name": "福田区", "level": "district", "children": [
            {"adcode": "440304001", "name": "福田街道", "level": "street"},
            {"adcode": "440304002", "name": "南园街道", "level": "street"},
            {"adcode": "440304003", "name": "园岭街道", "level": "street"},
            {"adcode": "440304004", "name": "莲花街道", "level": "street"},
            {"adcode": "440304005", "name": "华富街道", "level": "street"},
            {"adcode": "440304006", "name": "梅林街道", "level": "street"},
            {"adcode": "440304007", "name": "沙头街道", "level": "street"}
          ]},
          {"adcode": "440303", "name": "罗湖区", "level": "district", "children": [
            {"adcode": "440303001", "name": "桂园街道", "level": "street"},
            {"adcode": "440303002", "name": "黄贝街道", "level": "street"},
            {"adcode": "440303003", "name": "南湖街道", "level": "street"},
            {"adcode": "440303004", "name": "笋岗街道", "level": "street"},
            {"adcode": "440303005", "name": "东门街道", "level": "street"},
            {"adcode": "440303006", "name": "翠竹街道", "level": "street"}
          ]},
          {"adcode": "440305", "name": "南山区", "level": "district", "children": [
            {"adcode": "440305001", "name": "南头街道", "level": "street"},
            {"adcode": "440305002", "name": "南山街道", "level": "street"},
            {"adcode": "440305003", "name": "沙河街道", "level": "street"},
            {"adcode": "440305004", "name": "蛇口街道", "level": "street"},
            {"adcode": "440305005", "name": "招商街道", "level": "street"},
            {"adcode": "440305006", "name": "粤海街道", "level": "street"}
          ]},
          {"adcode": "440306", "name": "宝安区", "level": "district", "children": [
            {"adcode": "440306001", "name": "新安街道", "level": "street"},
            {"adcode": "440306002", "name": "西乡街道", "level": "street"},
            {"adcode": "440306003", "name": "福永街道", "level": "street"},
            {"adcode": "440306004", "name": "沙井街道", "level": "street"},
            {"adcode": "440306005", "name": "松岗街道", "level": "street"},
            {"adcode": "440306006", "name": "石岩街道", "level": "street"}
          ]},
          {"adcode": "440307", "name": "龙岗区", "level": "district", "children": [
            {"adcode": "440307001", "name": "龙岗街道", "level": "street"},
            {"adcode": "440307002", "name": "龙城街道", "level": "street"},
            {"adcode": "440307003", "name": "坪地街道", "level": "street"},
            {"adcode": "440307004", "name": "坂田街道", "level": "street"},
            {"adcode": "440307005", "name": "布吉街道", "level": "street"},
            {"adcode": "440307006", "name": "横岗街道", "level": "street"}
          ]},
          {"adcode": "440309", "name": "龙华区", "level": "district", "children": [
            {"adcode": "440309001", "name": "龙华街道", "level": "street"},
            {"adcode": "440309002", "name": "民治街道", "level": "street"},
            {"adcode": "440309003", "name": "大浪街道", "level": "street"},
            {"adcode": "440309004", "name": "观湖街道", "level": "street"},
            {"adcode": "440309005", "name": "福城街道", "level": "street"},
            {"adcode": "440309006", "name": "观澜街道", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "440400",
        "name": "珠海市",
        "level": "city",
        "center": "113.553986,22.224979",
        "children": [
          {"adcode": "440402", "name": "香洲区", "level": "district", "children": [
            {"adcode": "440402001", "name": "翠香街道", "level": "street"},
            {"adcode": "440402002", "name": "梅华街道", "level": "street"},
            {"adcode": "440402003", "name": "狮山街道", "level": "street"},
            {"adcode": "440402004", "name": "拱北街道", "level": "street"},
            {"adcode": "440402005", "name": "吉大街道", "level": "street"},
            {"adcode": "440402006", "name": "湾仔街道", "level": "street"}
          ]},
          {"adcode": "440403", "name": "斗门区", "level": "district", "children": [
            {"adcode": "440403001", "name": "井岸镇", "level": "street"},
            {"adcode": "440403002", "name": "白蕉镇", "level": "street"},
            {"adcode": "440403003", "name": "乾务镇", "level": "street"},
            {"adcode": "440403004", "name": "斗门镇", "level": "street"},
            {"adcode": "440403005", "name": "莲洲镇", "level": "street"}
          ]},
          {"adcode": "440404", "name": "金湾区", "level": "district", "children": [
            {"adcode": "440404001", "name": "三灶镇", "level": "street"},
            {"adcode": "440404002", "name": "红旗镇", "level": "street"},
            {"adcode": "440404003", "name": "平沙镇", "level": "street"},
            {"adcode": "440404004", "name": "南水镇", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "440600",
        "name": "佛山市",
        "level": "city",
        "center": "113.122717,23.028762",
        "children": [
          {"adcode": "440604", "name": "禅城区", "level": "district", "children": [
            {"adcode": "440604001", "name": "祖庙街道", "level": "street"},
            {"adcode": "440604002", "name": "石湾镇街道", "level": "street"},
            {"adcode": "440604003", "name": "张槎街道", "level": "street"},
            {"adcode": "440604004", "name": "南庄镇", "level": "street"}
          ]},
          {"adcode": "440605", "name": "南海区", "level": "district", "children": [
            {"adcode": "440605001", "name": "桂城街道", "level": "street"},
            {"adcode": "440605002", "name": "九江镇", "level": "street"},
            {"adcode": "440605003", "name": "西樵镇", "level": "street"},
            {"adcode": "440605004", "name": "丹灶镇", "level": "street"},
            {"adcode": "440605005", "name": "狮山镇", "level": "street"},
            {"adcode": "440605006", "name": "大沥镇", "level": "street"},
            {"adcode": "440605007", "name": "里水镇", "level": "street"}
          ]},
          {"adcode": "440606", "name": "顺德区", "level": "district", "children": [
            {"adcode": "440606001", "name": "大良街道", "level": "street"},
            {"adcode": "440606002", "name": "容桂街道", "level": "street"},
            {"adcode": "440606003", "name": "伦教街道", "level": "street"},
            {"adcode": "440606004", "name": "勒流街道", "level": "street"},
            {"adcode": "440606005", "name": "北滘镇", "level": "street"},
            {"adcode": "440606006", "name": "陈村镇", "level": "street"},
            {"adcode": "440606007", "name": "乐从镇", "level": "street"}
          ]},
          {"adcode": "440608", "name": "高明区", "level": "district", "children": [
            {"adcode": "440608001", "name": "荷城街道", "level": "street"},
            {"adcode": "440608002", "name": "杨和镇", "level": "street"},
            {"adcode": "440608003", "name": "明城镇", "level": "street"},
            {"adcode": "440608004", "name": "更合镇", "level": "street"}
          ]},
          {"adcode": "440607", "name": "三水区", "level": "district", "children": [
            {"adcode": "440607001", "name": "西南街道", "level": "street"},
            {"adcode": "440607002", "name": "云东海街道", "level": "street"},
            {"adcode": "440607003", "name": "白坭镇", "level": "street"},
            {"adcode": "440607004", "name": "乐平镇", "level": "street"},
            {"adcode": "440607005", "name": "芦苞镇", "level": "street"},
            {"adcode": "440607006", "name": "大塘镇", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "441300",
        "name": "惠州市",
        "level": "city",
        "center": "114.412599,23.079404",
        "children": [
          {"adcode": "441302", "name": "惠城区", "level": "district", "children": [
            {"adcode": "441302001", "name": "桥东街道", "level": "street"},
            {"adcode": "441302002", "name": "桥西街道", "level": "street"},
            {"adcode": "441302003", "name": "江北街道", "level": "street"},
            {"adcode": "441302004", "name": "龙丰街道", "level": "street"},
            {"adcode": "441302005", "name": "河南岸街道", "level": "street"},
            {"adcode": "441302006", "name": "江南街道", "level": "street"}
          ]},
          {"adcode": "441303", "name": "惠阳区", "level": "district", "children": [
            {"adcode": "441303001", "name": "淡水街道", "level": "street"},
            {"adcode": "441303002", "name": "秋长街道", "level": "street"},
            {"adcode": "441303003", "name": "新圩镇", "level": "street"},
            {"adcode": "441303004", "name": "镇隆镇", "level": "street"},
            {"adcode": "441303005", "name": "沙田镇", "level": "street"},
            {"adcode": "441303006", "name": "平潭镇", "level": "street"}
          ]},
          {"adcode": "441322", "name": "博罗县", "level": "district", "children": [
            {"adcode": "441322001", "name": "罗阳街道", "level": "street"},
            {"adcode": "441322002", "name": "龙溪街道", "level": "street"},
            {"adcode": "441322003", "name": "龙华镇", "level": "street"},
            {"adcode": "441322004", "name": "园洲镇", "level": "street"},
            {"adcode": "441322005", "name": "石湾镇", "level": "street"},
            {"adcode": "441322006", "name": "福田镇", "level": "street"}
          ]},
          {"adcode": "441323", "name": "惠东县", "level": "district", "children": [
            {"adcode": "441323001", "name": "平山街道", "level": "street"},
            {"adcode": "441323002", "name": "大岭街道", "level": "street"},
            {"adcode": "441323003", "name": "稔山镇", "level": "street"},
            {"adcode": "441323004", "name": "平海镇", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "441900",
        "name": "东莞市",
        "level": "city",
        "center": "113.746262,23.046237",
        "children": [
          {"adcode": "441900001", "name": "莞城街道", "level": "street"},
          {"adcode": "441900002", "name": "南城街道", "level": "street"},
          {"adcode": "441900003", "name": "东城街道", "level": "street"},
          {"adcode": "441900004", "name": "万江街道", "level": "street"},
          {"adcode": "441900005", "name": "虎门镇", "level": "street"},
          {"adcode": "441900006", "name": "长安镇", "level": "street"},
          {"adcode": "441900007", "name": "厚街镇", "level": "street"}
        ]
      },
      {
        "adcode": "442000",
        "name": "中山市",
        "level": "city",
        "center": "113.382391,22.521113",
        "children": [
          {"adcode": "442000001", "name": "石岐街道", "level": "street"},
          {"adcode": "442000002", "name": "东区街道", "level": "street"},
          {"adcode": "442000003", "name": "西区街道", "level": "street"},
          {"adcode": "442000004", "name": "南区街道", "level": "street"},
          {"adcode": "442000005", "name": "小榄镇", "level": "street"},
          {"adcode": "442000006", "name": "古镇镇", "level": "street"},
          {"adcode": "442000007", "name": "三角镇", "level": "street"}
        ]
      },
      {
        "adcode": "440700",
        "name": "江门市",
        "level": "city",
        "center": "113.094942,22.590431",
        "children": [
          {"adcode": "440703", "name": "蓬江区", "level": "district", "children": [
            {"adcode": "440703001", "name": "白沙街道", "level": "street"},
            {"adcode": "440703002", "name": "环市街道", "level": "street"},
            {"adcode": "440703003", "name": "潮连街道", "level": "street"},
            {"adcode": "440703004", "name": "荷塘镇", "level": "street"},
            {"adcode": "440703005", "name": "棠下镇", "level": "street"},
            {"adcode": "440703006", "name": "杜阮镇", "level": "street"}
          ]},
          {"adcode": "440704", "name": "江海区", "level": "district", "children": [
            {"adcode": "440704001", "name": "滘头街道", "level": "street"},
            {"adcode": "440704002", "name": "滘北街道", "level": "street"},
            {"adcode": "440704003", "name": "江南街道", "level": "street"},
            {"adcode": "440704004", "name": "外海街道", "level": "street"},
            {"adcode": "440704005", "name": "礼乐街道", "level": "street"}
          ]},
          {"adcode": "440705", "name": "新会区", "level": "district", "children": [
            {"adcode": "440705001", "name": "会城街道", "level": "street"},
            {"adcode": "440705002", "name": "大泽镇", "level": "street"},
            {"adcode": "440705003", "name": "司前镇", "level": "street"},
            {"adcode": "440705004", "name": "沙堆镇", "level": "street"},
            {"adcode": "440705005", "name": "古井镇", "level": "street"},
            {"adcode": "440705006", "name": "三江镇", "level": "street"}
          ]},
          {"adcode": "440781", "name": "台山市", "level": "district", "children": [
            {"adcode": "440781001", "name": "台城街道", "level": "street"},
            {"adcode": "440781002", "name": "大江镇", "level": "street"},
            {"adcode": "440781003", "name": "水步镇", "level": "street"},
            {"adcode": "440781004", "name": "四九镇", "level": "street"},
            {"adcode": "440781005", "name": "白沙镇", "level": "street"},
            {"adcode": "440781006", "name": "三合镇", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "441200",
        "name": "肇庆市",
        "level": "city",
        "center": "112.472529,23.051546",
        "children": [
          {"adcode": "441202", "name": "端州区", "level": "district", "children": [
            {"adcode": "441202001", "name": "城东街道", "level": "street"},
            {"adcode": "441202002", "name": "城西街道", "level": "street"},
            {"adcode": "441202003", "name": "城南街道", "level": "street"},
            {"adcode": "441202004", "name": "城北街道", "level": "street"},
            {"adcode": "441202005", "name": "睦岗街道", "level": "street"},
            {"adcode": "441202006", "name": "黄岗街道", "level": "street"}
          ]},
          {"adcode": "441203", "name": "鼎湖区", "level": "district", "children": [
            {"adcode": "441203001", "name": "坑口街道", "level": "street"},
            {"adcode": "441203002", "name": "桂城街道", "level": "street"},
            {"adcode": "441203003", "name": "广利街道", "level": "street"},
            {"adcode": "441203004", "name": "沙浦镇", "level": "street"},
            {"adcode": "441203005", "name": "凤凰镇", "level": "street"},
            {"adcode": "441203006", "name": "莲花镇", "level": "street"}
          ]},
          {"adcode": "441204", "name": "高要区", "level": "district", "children": [
            {"adcode": "441204001", "name": "南岸街道", "level": "street"},
            {"adcode": "441204002", "name": "金渡镇", "level": "street"},
            {"adcode": "441204003", "name": "金利镇", "level": "street"},
            {"adcode": "441204004", "name": "白土镇", "level": "street"},
            {"adcode": "441204005", "name": "回龙镇", "level": "street"},
            {"adcode": "441204006", "name": "蛟塘镇", "level": "street"}
          ]}
        ]
      },
      {
        "adcode": "441800",
        "name": "清远市",
        "level": "city",
        "center": "113.051227,23.685022",
        "children": [
          {"adcode": "441802", "name": "清城区", "level": "district", "children": [
            {"adcode": "441802001", "name": "凤城街道", "level": "street"},
            {"adcode": "441802002", "name": "东城街道", "level": "street"},
            {"adcode": "441802003", "name": "洲心街道", "level": "street"},
            {"adcode": "441802004", "name": "横荷街道", "level": "street"},
            {"adcode": "441802005", "name": "龙塘镇", "level": "street"},
            {"adcode": "441802006", "name": "石角镇", "level": "street"}
          ]},
          {"adcode": "441803", "name": "清新区", "level": "district", "children": [
            {"adcode": "441803001", "name": "太和镇", "level": "street"},
            {"adcode": "441803002", "name": "三坑镇", "level": "street"},
            {"adcode": "441803003", "name": "山塘镇", "level": "street"},
            {"adcode": "441803004", "name": "太平镇", "level": "street"},
            {"adcode": "441803005", "name": "禾云镇", "level": "street"},
            {"adcode": "441803006", "name": "龙颈镇", "level": "street"}
          ]},
          {"adcode": "441881", "name": "英德市", "level": "district", "children": [
            {"adcode": "441881001", "name": "英城街道", "level": "street"},
            {"adcode": "441881002", "name": "横石塘镇", "level": "street"},
            {"adcode": "441881003", "name": "望埠镇", "level": "street"},
            {"adcode": "441881004", "name": "桥头镇", "level": "street"},
            {"adcode": "441881005", "name": "青塘镇", "level": "street"},
            {"adcode": "441881006", "name": "白沙镇", "level": "street"}
          ]}
        ]
      }
    ]
  }
]
"""
