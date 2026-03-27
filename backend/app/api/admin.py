from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, require_role, verify_password
from app.models.models import (
    AIModelConfig,
    Article,
    ContentStatus,
    Expert,
    MemberLevel,
    Notification,
    NotificationType,
    Order,
    OrderStatus,
    PaymentStatus,
    PointsMallItem,
    PointsRecord,
    PointsType,
    ServiceCategory,
    ServiceItem,
    SystemConfig,
    User,
    UserRole,
    Video,
)
from app.schemas.admin import (
    AIModelConfigCreate,
    AIModelConfigResponse,
    AIModelConfigUpdate,
    DashboardStats,
    SystemConfigUpdate,
)
from app.schemas.user import RegisterSettingsResponse
from app.schemas.content import ArticleCreate, ArticleResponse, ArticleUpdate, VideoCreate, VideoResponse
from app.schemas.service import ServiceCategoryCreate, ServiceCategoryResponse, ServiceItemCreate, ServiceItemResponse, ServiceItemUpdate
from app.services.register_service import get_register_settings, save_register_settings

router = APIRouter(prefix="/api/admin", tags=["管理后台"])

admin_dep = require_role("admin")


class AdminLoginRequest(BaseModel):
    phone: str
    password: str


@router.post("/login")
async def admin_login(data: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == data.phone, User.role == UserRole.admin))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="手机号或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="手机号或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = create_access_token({"sub": str(user.id)})
    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.nickname or "管理员",
            "phone": user.phone,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        },
    }


# ── AI配置 ──

@router.get("/ai-config")
async def list_ai_configs(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelConfig).order_by(AIModelConfig.created_at.desc()))
    items = [AIModelConfigResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items}


@router.post("/ai-config", response_model=AIModelConfigResponse)
async def create_ai_config(
    data: AIModelConfigCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.is_active:
        await db.execute(update(AIModelConfig).values(is_active=False))

    config = AIModelConfig(
        provider_name=data.provider_name,
        base_url=data.base_url,
        model_name=data.model_name,
        api_key_encrypted=data.api_key,
        is_active=data.is_active,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return AIModelConfigResponse.model_validate(config)


@router.put("/ai-config/{config_id}", response_model=AIModelConfigResponse)
async def update_ai_config(
    config_id: int,
    data: AIModelConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelConfig).where(AIModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    if data.is_active:
        await db.execute(update(AIModelConfig).where(AIModelConfig.id != config_id).values(is_active=False))

    if data.provider_name is not None:
        config.provider_name = data.provider_name
    if data.base_url is not None:
        config.base_url = data.base_url
    if data.model_name is not None:
        config.model_name = data.model_name
    if data.api_key is not None:
        config.api_key_encrypted = data.api_key
    if data.is_active is not None:
        config.is_active = data.is_active

    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)
    return AIModelConfigResponse.model_validate(config)


@router.delete("/ai-config/{config_id}")
async def delete_ai_config(
    config_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelConfig).where(AIModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    await db.delete(config)
    return {"message": "删除成功"}


@router.post("/ai-config/test")
async def test_ai_config(
    data: AIModelConfigCreate,
    current_user=Depends(admin_dep),
):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{data.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {data.api_key}", "Content-Type": "application/json"},
                json={"model": data.model_name, "messages": [{"role": "user", "content": "你好"}], "max_tokens": 50},
            )
            if resp.status_code == 200:
                return {"success": True, "message": "连接测试成功"}
            return {"success": False, "message": f"API返回状态码 {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}


# ── 用户管理 ──

@router.get("/users")
async def list_users(
    keyword: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    count_query = select(func.count(User.id))

    if keyword:
        query = query.where(User.phone.contains(keyword) | User.nickname.contains(keyword))
        count_query = count_query.where(User.phone.contains(keyword) | User.nickname.contains(keyword))
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if status:
        query = query.where(User.status == status)
        count_query = count_query.where(User.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for u in result.scalars().all():
        items.append({
            "id": u.id,
            "phone": u.phone,
            "nickname": u.nickname,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "member_level": u.member_level,
            "points": u.points,
            "status": u.status,
            "created_at": u.created_at.isoformat(),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    status: str = Query(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if status not in ("active", "disabled", "banned"):
        raise HTTPException(status_code=400, detail="无效的状态值")

    user.status = status
    user.updated_at = datetime.utcnow()
    return {"message": f"用户状态已更新为 {status}"}


# ── 服务分类管理 ──

@router.get("/services/categories")
async def admin_list_categories(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceCategory).order_by(ServiceCategory.sort_order.asc()))
    items = [ServiceCategoryResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items}


@router.post("/services/categories", response_model=ServiceCategoryResponse)
async def admin_create_category(
    data: ServiceCategoryCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cat = ServiceCategory(**data.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return ServiceCategoryResponse.model_validate(cat)


@router.put("/services/categories/{cat_id}", response_model=ServiceCategoryResponse)
async def admin_update_category(
    cat_id: int,
    data: ServiceCategoryCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceCategory).where(ServiceCategory.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")

    for key, value in data.model_dump().items():
        setattr(cat, key, value)
    await db.flush()
    await db.refresh(cat)
    return ServiceCategoryResponse.model_validate(cat)


@router.delete("/services/categories/{cat_id}")
async def admin_delete_category(
    cat_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceCategory).where(ServiceCategory.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    cat.status = "deleted"
    return {"message": "删除成功"}


# ── 服务项目管理 ──

@router.get("/services/items")
async def admin_list_items(
    category_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(ServiceItem)
    count_query = select(func.count(ServiceItem.id))

    if category_id:
        query = query.where(ServiceItem.category_id == category_id)
        count_query = count_query.where(ServiceItem.category_id == category_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(ServiceItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ServiceItemResponse.model_validate(i) for i in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/services/items", response_model=ServiceItemResponse)
async def admin_create_item(
    data: ServiceItemCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    item = ServiceItem(**data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return ServiceItemResponse.model_validate(item)


@router.put("/services/items/{item_id}", response_model=ServiceItemResponse)
async def admin_update_item(
    item_id: int,
    data: ServiceItemUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceItem).where(ServiceItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="项目不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(item)
    return ServiceItemResponse.model_validate(item)


@router.delete("/services/items/{item_id}")
async def admin_delete_item(
    item_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceItem).where(ServiceItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="项目不存在")
    item.status = "deleted"
    return {"message": "删除成功"}


# ── 订单管理 ──

@router.get("/orders")
async def admin_list_orders(
    order_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order)
    count_query = select(func.count(Order.id))

    if order_status:
        query = query.where(Order.order_status == order_status)
        count_query = count_query.where(Order.order_status == order_status)
    if payment_status:
        query = query.where(Order.payment_status == payment_status)
        count_query = count_query.where(Order.payment_status == payment_status)
    if keyword:
        query = query.where(Order.order_no.contains(keyword))
        count_query = count_query.where(Order.order_no.contains(keyword))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    from app.schemas.order import OrderResponse
    result = await db.execute(
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [OrderResponse.model_validate(o) for o in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/orders/{order_id}/refund")
async def admin_refund_order(
    order_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order.payment_status = PaymentStatus.refunded
    order.order_status = OrderStatus.cancelled
    order.updated_at = datetime.utcnow()

    if order.points_deduction > 0:
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        order_user = user_result.scalar_one_or_none()
        if order_user:
            order_user.points += order.points_deduction
            pr = PointsRecord(
                user_id=order.user_id,
                points=order.points_deduction,
                type=PointsType.redeem,
                description=f"退款退还积分 {order.order_no}",
                order_id=order.id,
            )
            db.add(pr)

    notification = Notification(
        user_id=order.user_id,
        title="订单退款通知",
        content=f"您的订单 {order.order_no} 已退款。",
        type=NotificationType.order,
    )
    db.add(notification)

    return {"message": "退款成功"}


# ── 内容管理 ──

@router.get("/content/articles")
async def admin_list_articles(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Article)
    count_query = select(func.count(Article.id))

    if status:
        query = query.where(Article.status == status)
        count_query = count_query.where(Article.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ArticleResponse.model_validate(a) for a in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/content/articles", response_model=ArticleResponse)
async def admin_create_article(
    data: ArticleCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    article = Article(
        **data.model_dump(),
        author_id=current_user.id,
        status=ContentStatus.published,
    )
    db.add(article)
    await db.flush()
    await db.refresh(article)
    return ArticleResponse.model_validate(article)


@router.put("/content/articles/{article_id}", response_model=ArticleResponse)
async def admin_update_article(
    article_id: int,
    data: ArticleUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(article, key, value)
    article.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(article)
    return ArticleResponse.model_validate(article)


@router.delete("/content/articles/{article_id}")
async def admin_delete_article(
    article_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    article.status = ContentStatus.archived
    return {"message": "删除成功"}


@router.get("/content/videos")
async def admin_list_videos(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Video)
    count_query = select(func.count(Video.id))

    if status:
        query = query.where(Video.status == status)
        count_query = count_query.where(Video.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Video.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [VideoResponse.model_validate(v) for v in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/content/videos", response_model=VideoResponse)
async def admin_create_video(
    data: VideoCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    video = Video(
        **data.model_dump(),
        author_id=current_user.id,
        status=ContentStatus.published,
    )
    db.add(video)
    await db.flush()
    await db.refresh(video)
    return VideoResponse.model_validate(video)


@router.put("/content/videos/{video_id}", response_model=VideoResponse)
async def admin_update_video(
    video_id: int,
    data: VideoCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    for key, value in data.model_dump().items():
        setattr(video, key, value)
    await db.flush()
    await db.refresh(video)
    return VideoResponse.model_validate(video)


@router.delete("/content/videos/{video_id}")
async def admin_delete_video(
    video_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    video.status = ContentStatus.archived
    return {"message": "删除成功"}


# ── 积分商城管理 ──

@router.get("/points/mall")
async def admin_list_mall_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(PointsMallItem.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(PointsMallItem)
        .order_by(PointsMallItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    from app.schemas.points import PointsMallItemResponse
    items = [PointsMallItemResponse.model_validate(i) for i in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/points/mall")
async def admin_create_mall_item(
    name: str = Query(...),
    description: str = Query(""),
    type: str = Query("virtual"),
    price_points: int = Query(...),
    stock: int = Query(0),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    item = PointsMallItem(
        name=name,
        description=description,
        type=type,
        price_points=price_points,
        stock=stock,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    from app.schemas.points import PointsMallItemResponse
    return PointsMallItemResponse.model_validate(item)


@router.put("/points/mall/{item_id}")
async def admin_update_mall_item(
    item_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    price_points: Optional[int] = None,
    stock: Optional[int] = None,
    status: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    if name is not None:
        item.name = name
    if description is not None:
        item.description = description
    if price_points is not None:
        item.price_points = price_points
    if stock is not None:
        item.stock = stock
    if status is not None:
        item.status = status

    return {"message": "更新成功"}


@router.delete("/points/mall/{item_id}")
async def admin_delete_mall_item(
    item_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")
    item.status = "deleted"
    return {"message": "删除成功"}


@router.get("/points/rules")
async def get_points_rules(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key.like("points_%")))
    configs = result.scalars().all()
    rules = {c.config_key: c.config_value for c in configs}
    if not rules:
        rules = {
            "points_signin_base": "5",
            "points_signin_bonus_per_day": "2",
            "points_signin_max_bonus_days": "7",
            "points_task_checkin": "10",
            "points_review": "10",
            "points_invite": "50",
        }
    return {"rules": rules}


@router.put("/points/rules")
async def update_points_rules(
    rules: dict,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for key, value in rules.items():
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(config_key=key, config_value=str(value), config_type="points")
            db.add(config)
    return {"message": "积分规则更新成功"}


# ── 仪表盘 ──

@router.get("/dashboard", response_model=DashboardStats)
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    total_orders_result = await db.execute(select(func.count(Order.id)))
    total_orders = total_orders_result.scalar() or 0

    revenue_result = await db.execute(select(func.sum(Order.paid_amount)).where(Order.payment_status == PaymentStatus.paid))
    total_revenue = float(revenue_result.scalar() or 0)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    today_users_result = await db.execute(select(func.count(User.id)).where(User.created_at >= today_start))
    today_new_users = today_users_result.scalar() or 0

    today_orders_result = await db.execute(select(func.count(Order.id)).where(Order.created_at >= today_start))
    today_orders = today_orders_result.scalar() or 0

    today_revenue_result = await db.execute(
        select(func.sum(Order.paid_amount)).where(Order.created_at >= today_start, Order.payment_status == PaymentStatus.paid)
    )
    today_revenue = float(today_revenue_result.scalar() or 0)

    active_experts_result = await db.execute(select(func.count(Expert.id)).where(Expert.status == "active"))
    active_experts = active_experts_result.scalar() or 0

    total_articles_result = await db.execute(select(func.count(Article.id)).where(Article.status == ContentStatus.published))
    total_articles = total_articles_result.scalar() or 0

    return DashboardStats(
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue,
        today_new_users=today_new_users,
        today_orders=today_orders,
        today_revenue=today_revenue,
        active_experts=active_experts,
        total_articles=total_articles,
    )


# ── 系统配置 ──

@router.get("/system/configs")
async def list_system_configs(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemConfig).order_by(SystemConfig.config_key.asc()))
    configs = result.scalars().all()
    items = [
        {
            "id": c.id,
            "config_key": c.config_key,
            "config_value": c.config_value,
            "config_type": c.config_type,
            "description": c.description,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in configs
    ]
    return {"items": items}


@router.put("/system/configs/{config_key}")
async def update_system_config(
    config_key: str,
    data: SystemConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    config = result.scalar_one_or_none()
    if not config:
        config = SystemConfig(config_key=config_key, config_value=data.config_value)
        db.add(config)
    else:
        config.config_value = data.config_value
        config.updated_at = datetime.utcnow()
    return {"message": "配置更新成功"}


# ── 专家管理 ──

@router.get("/experts")
async def admin_list_experts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(Expert.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Expert)
        .order_by(Expert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for e in result.scalars().all():
        items.append({
            "id": e.id,
            "name": e.name,
            "title": e.title,
            "hospital": e.hospital,
            "department": e.department,
            "specialties": e.specialties,
            "avatar": e.avatar,
            "consultation_fee": float(e.consultation_fee) if e.consultation_fee else 0,
            "rating": e.rating,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/experts")
async def admin_create_expert(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    expert = Expert(
        name=data.get("name", ""),
        title=data.get("title"),
        hospital=data.get("hospital"),
        department=data.get("department"),
        specialties=data.get("specialties"),
        introduction=data.get("introduction"),
        avatar=data.get("avatar"),
        consultation_fee=data.get("consultation_fee", 0),
        status=data.get("status", "active"),
    )
    db.add(expert)
    await db.flush()
    await db.refresh(expert)
    return {
        "id": expert.id,
        "name": expert.name,
        "title": expert.title,
        "hospital": expert.hospital,
        "status": expert.status,
    }


@router.put("/experts/{expert_id}")
async def admin_update_expert(
    expert_id: int,
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")

    for field in ["name", "title", "hospital", "department", "specialties", "introduction", "avatar", "consultation_fee", "status"]:
        if field in data:
            setattr(expert, field, data[field])
    return {"message": "更新成功"}


@router.delete("/experts/{expert_id}")
async def admin_delete_expert(
    expert_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")
    expert.status = "deleted"
    return {"message": "删除成功"}


# ── 会员等级管理 ──

@router.get("/points/levels")
async def admin_list_member_levels(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MemberLevel).order_by(MemberLevel.min_points.asc()))
    items = []
    for lv in result.scalars().all():
        items.append({
            "id": lv.id,
            "level_name": lv.level_name,
            "min_points": lv.min_points,
            "max_points": lv.max_points,
            "discount_rate": lv.discount_rate,
            "benefits": lv.benefits,
        })
    return {"items": items}


@router.post("/points/levels")
async def admin_create_or_update_level(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    level_id = data.get("id")
    if level_id:
        result = await db.execute(select(MemberLevel).where(MemberLevel.id == level_id))
        level = result.scalar_one_or_none()
        if level:
            for field in ["level_name", "min_points", "max_points", "discount_rate", "benefits"]:
                if field in data:
                    setattr(level, field, data[field])
            return {"message": "更新成功", "id": level.id}

    level = MemberLevel(
        level_name=data.get("level_name", ""),
        min_points=data.get("min_points", 0),
        max_points=data.get("max_points", 0),
        discount_rate=data.get("discount_rate", 1.0),
        benefits=data.get("benefits"),
    )
    db.add(level)
    await db.flush()
    await db.refresh(level)
    return {"message": "创建成功", "id": level.id}


# ── 积分规则（兼容POST） ──

@router.post("/points/rules")
async def update_points_rules_post(
    rules: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for key, value in rules.items():
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(config_key=key, config_value=str(value), config_type="points")
            db.add(config)
    return {"message": "积分规则更新成功"}


# ── 设置管理 ──

@router.post("/settings/basic")
async def update_basic_settings(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for key, value in data.items():
        config_key = f"basic_{key}"
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(config_key=config_key, config_value=str(value), config_type="basic", description=key))
    return {"message": "基本设置更新成功"}


@router.post("/settings/push")
async def update_push_settings(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for key, value in data.items():
        config_key = f"push_{key}"
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(config_key=config_key, config_value=str(value), config_type="push", description=key))
    return {"message": "推送设置更新成功"}


@router.post("/settings/protocol")
async def update_protocol_settings(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for key, value in data.items():
        config_key = f"protocol_{key}"
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
        config = result.scalar_one_or_none()
        if config:
            config.config_value = str(value)
            config.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(config_key=config_key, config_value=str(value), config_type="protocol", description=key))
    return {"message": "协议设置更新成功"}


@router.get("/settings/register", response_model=RegisterSettingsResponse)
async def get_registration_settings(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    return await get_register_settings(db)


@router.post("/settings/register")
async def update_registration_settings(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    settings = await save_register_settings(db, data)
    return {"message": "注册设置更新成功", "settings": settings}
