from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, require_role, verify_password
from app.models.models import (
    AIModelConfig,
    AIModelTemplate,
    Article,
    ChatMessage,
    ContentStatus,
    Expert,
    MemberLevel,
    MessageRole,
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
    AIModelConfigTestRequest,
    AIModelConfigUpdate,
    AIModelTemplateCreate,
    AIModelTemplateResponse,
    AIModelTemplateUpdate,
    DashboardRecentOrder,
    DashboardStats,
    DashboardTrendPoint,
    SystemConfigUpdate,
)
from app.schemas.points import PointsMallItemCreate, PointsMallItemUpdate
from app.schemas.user import RegisterSettingsResponse
from app.schemas.content import ArticleCreate, ArticleResponse, ArticleUpdate, VideoCreate, VideoResponse, VideoUpdate
from app.schemas.service import ServiceCategoryCreate, ServiceCategoryResponse, ServiceItemCreate, ServiceItemResponse, ServiceItemUpdate
from app.services.register_service import get_register_settings, save_register_settings

router = APIRouter(prefix="/api/admin", tags=["管理后台"])

admin_dep = require_role("admin")


def _day_label(d: date | datetime) -> str:
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%m-%d")


def _rows_to_trend(labels: list[str], rows) -> list[DashboardTrendPoint]:
    counts = dict.fromkeys(labels, 0)
    for row in rows:
        day_val, cnt = row[0], row[1]
        if day_val is None:
            continue
        key = _day_label(day_val) if isinstance(day_val, (date, datetime)) else str(day_val)[5:10]
        if key in counts:
            counts[key] = int(cnt or 0)
    return [DashboardTrendPoint(date=lab, count=counts[lab]) for lab in labels]


def _order_row_status(order: Order) -> str:
    if order.payment_status == PaymentStatus.refunded:
        return "refunded"
    if order.order_status == OrderStatus.completed:
        return "completed"
    if order.payment_status == PaymentStatus.paid:
        return "paid"
    return "pending"


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

def _mask_api_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    visible = len(key) - 7
    if visible < 2:
        visible = 2
    return key[:visible] + "****"


def _ai_config_to_dict(config: AIModelConfig) -> dict:
    return {
        "id": config.id,
        "provider_name": config.provider_name,
        "base_url": config.base_url,
        "model_name": config.model_name,
        "api_key": _mask_api_key(config.api_key_encrypted),
        "is_active": config.is_active,
        "max_tokens": config.max_tokens if config.max_tokens is not None else 4096,
        "temperature": config.temperature if config.temperature is not None else 0.7,
        "template_id": config.template_id,
        "template_synced_at": config.template_synced_at.isoformat() if config.template_synced_at else None,
        "last_test_status": config.last_test_status,
        "last_test_time": config.last_test_time.isoformat() if config.last_test_time else None,
        "last_test_message": config.last_test_message,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@router.get("/ai-config")
async def list_ai_configs(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelConfig).order_by(AIModelConfig.created_at.desc()))
    configs = result.scalars().all()
    items = [_ai_config_to_dict(c) for c in configs]
    return {"items": items}


@router.post("/ai-config")
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
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        template_id=data.template_id,
        template_synced_at=datetime.utcnow() if data.template_id else None,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return _ai_config_to_dict(config)


@router.get("/ai-config/active")
async def get_active_ai_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelConfig).where(AIModelConfig.is_active == True))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="暂无活跃配置")
    return _ai_config_to_dict(config)


@router.get("/ai-config/sync-check")
async def ai_config_sync_check(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIModelConfig).where(AIModelConfig.template_id.isnot(None))
    )
    configs = result.scalars().all()
    need_sync = []
    for cfg in configs:
        tpl_result = await db.execute(
            select(AIModelTemplate).where(AIModelTemplate.id == cfg.template_id)
        )
        tpl = tpl_result.scalar_one_or_none()
        if not tpl:
            continue
        if cfg.template_synced_at is None or cfg.template_synced_at < tpl.updated_at:
            need_sync.append({
                "config_id": cfg.id,
                "config_name": cfg.provider_name,
                "template_id": tpl.id,
                "template_name": tpl.name,
                "template_updated_at": tpl.updated_at.isoformat(),
                "config_synced_at": cfg.template_synced_at.isoformat() if cfg.template_synced_at else None,
            })
    return {"need_sync": need_sync, "count": len(need_sync)}


@router.post("/ai-config/sync")
async def ai_config_sync(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIModelConfig).where(AIModelConfig.template_id.isnot(None))
    )
    configs = result.scalars().all()
    synced = 0
    for cfg in configs:
        tpl_result = await db.execute(
            select(AIModelTemplate).where(AIModelTemplate.id == cfg.template_id)
        )
        tpl = tpl_result.scalar_one_or_none()
        if not tpl:
            continue
        if cfg.template_synced_at is None or cfg.template_synced_at < tpl.updated_at:
            cfg.base_url = tpl.base_url
            cfg.model_name = tpl.model_name
            cfg.provider_name = tpl.name
            cfg.template_synced_at = datetime.utcnow()
            cfg.updated_at = datetime.utcnow()
            synced += 1
    return {"message": f"已同步 {synced} 个配置", "synced": synced}


@router.patch("/ai-config/{config_id}/activate")
async def activate_ai_config(
    config_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelConfig).where(AIModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    await db.execute(update(AIModelConfig).values(is_active=False))
    config.is_active = True
    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)
    return _ai_config_to_dict(config)


@router.put("/ai-config/{config_id}")
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
    if data.max_tokens is not None:
        config.max_tokens = data.max_tokens
    if data.temperature is not None:
        config.temperature = data.temperature

    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)
    return _ai_config_to_dict(config)


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
    data: AIModelConfigTestRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    import time

    base_url = data.base_url
    model_name = data.model_name
    api_key = data.api_key
    config_obj = None

    if data.config_id:
        result = await db.execute(select(AIModelConfig).where(AIModelConfig.id == data.config_id))
        config_obj = result.scalar_one_or_none()
        if not config_obj:
            raise HTTPException(status_code=404, detail="配置不存在")
        base_url = config_obj.base_url
        model_name = config_obj.model_name
        api_key = config_obj.api_key_encrypted

    if not base_url or not model_name or not api_key:
        return {"success": False, "message": "缺少必要的配置信息", "response_time": None, "model_reply": None, "error_detail": "缺少 base_url、model_name 或 api_key"}

    test_message = data.test_message or "你好"
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model_name, "messages": [{"role": "user", "content": test_message}], "max_tokens": 100},
            )
            elapsed = round(time.time() - start_time, 2)

            if resp.status_code == 200:
                resp_data = resp.json()
                model_reply = ""
                try:
                    model_reply = resp_data["choices"][0]["message"]["content"]
                except (KeyError, IndexError):
                    model_reply = str(resp_data)

                if config_obj:
                    config_obj.last_test_status = "success"
                    config_obj.last_test_time = datetime.utcnow()
                    config_obj.last_test_message = (model_reply[:500] if model_reply else "")
                    await db.flush()

                return {
                    "success": True,
                    "message": "连接测试成功",
                    "response_time": elapsed,
                    "model_reply": model_reply,
                    "error_detail": None,
                }
            else:
                error_text = resp.text[:500] if resp.text else ""
                error_detail = f"API返回状态码 {resp.status_code}: {error_text}"

                if config_obj:
                    config_obj.last_test_status = "failed"
                    config_obj.last_test_time = datetime.utcnow()
                    config_obj.last_test_message = error_detail[:500]
                    await db.flush()

                return {
                    "success": False,
                    "message": "连接失败",
                    "response_time": elapsed,
                    "model_reply": None,
                    "error_detail": error_detail,
                }
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        error_detail = f"连接失败: {str(e)}"

        if config_obj:
            config_obj.last_test_status = "failed"
            config_obj.last_test_time = datetime.utcnow()
            config_obj.last_test_message = error_detail[:500]
            await db.flush()

        return {
            "success": False,
            "message": "连接失败",
            "response_time": elapsed if elapsed > 0 else None,
            "model_reply": None,
            "error_detail": error_detail,
        }


# ── AI 模型模板管理 ──

PRESET_ICONS = [
    {"key": "volcano", "label": "火山引擎", "color": "#FF6B35"},
    {"key": "tencent", "label": "腾讯云", "color": "#006eff"},
    {"key": "openai", "label": "OpenAI", "color": "#10a37f"},
    {"key": "deepseek", "label": "DeepSeek", "color": "#4D6BFE"},
    {"key": "baidu", "label": "百度文心", "color": "#2932E1"},
    {"key": "alibaba", "label": "阿里通义", "color": "#FF6A00"},
    {"key": "zhipu", "label": "智谱AI", "color": "#5B5EA6"},
    {"key": "moonshot", "label": "月之暗面", "color": "#000000"},
    {"key": "anthropic", "label": "Anthropic", "color": "#D97757"},
    {"key": "custom", "label": "自定义", "color": "#8c8c8c"},
]


@router.get("/ai-model-templates/icons")
async def get_template_icons(current_user=Depends(admin_dep)):
    return {"items": PRESET_ICONS}


@router.get("/ai-model-templates")
async def list_ai_model_templates(
    status: Optional[int] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(AIModelTemplate)
    if status is not None:
        query = query.where(AIModelTemplate.status == status)
    query = query.order_by(AIModelTemplate.created_at.desc())
    result = await db.execute(query)
    templates = result.scalars().all()
    items = [AIModelTemplateResponse.model_validate(t) for t in templates]
    return {"items": items}


@router.post("/ai-model-templates")
async def create_ai_model_template(
    data: AIModelTemplateCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    template = AIModelTemplate(**data.model_dump())
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return AIModelTemplateResponse.model_validate(template)


@router.put("/ai-model-templates/{template_id}")
async def update_ai_model_template(
    template_id: int,
    data: AIModelTemplateUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelTemplate).where(AIModelTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    template.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(template)
    return AIModelTemplateResponse.model_validate(template)


@router.patch("/ai-model-templates/{template_id}/status")
async def toggle_template_status(
    template_id: int,
    status: int = Body(..., embed=True),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelTemplate).where(AIModelTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    template.status = status
    template.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(template)
    return AIModelTemplateResponse.model_validate(template)


@router.delete("/ai-model-templates/{template_id}")
async def delete_ai_model_template(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIModelTemplate).where(AIModelTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    linked = await db.execute(
        select(func.count(AIModelConfig.id)).where(AIModelConfig.template_id == template_id)
    )
    if (linked.scalar() or 0) > 0:
        raise HTTPException(status_code=400, detail="该模板下存在关联配置，无法删除")

    await db.delete(template)
    return {"message": "删除成功"}


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


@router.put("/services/items/batch-status")
async def admin_batch_update_service_status(
    item_ids: list[int] = Body(...),
    status: str = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceItem).where(ServiceItem.id.in_(item_ids)))
    items = result.scalars().all()
    for item in items:
        item.status = status
    await db.flush()
    return {"updated": len(items)}


@router.put("/services/items/sort")
async def admin_update_service_sort(
    items: list[dict] = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for item_data in items:
        result = await db.execute(select(ServiceItem).where(ServiceItem.id == item_data["id"]))
        item = result.scalar_one_or_none()
        if item and hasattr(item, 'sort_order'):
            item.sort_order = item_data.get("sort_order", 0)
    await db.flush()
    return {"success": True}


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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order)
    count_query = select(func.count(Order.id))

    if order_status:
        statuses = [s.strip() for s in order_status.split(",")]
        if len(statuses) > 1:
            query = query.where(Order.order_status.in_(statuses))
            count_query = count_query.where(Order.order_status.in_(statuses))
        else:
            query = query.where(Order.order_status == order_status)
            count_query = count_query.where(Order.order_status == order_status)
    if payment_status:
        query = query.where(Order.payment_status == payment_status)
        count_query = count_query.where(Order.payment_status == payment_status)
    if keyword:
        query = query.where(Order.order_no.contains(keyword))
        count_query = count_query.where(Order.order_no.contains(keyword))
    if start_date:
        from datetime import datetime as dt
        query = query.where(Order.created_at >= dt.fromisoformat(start_date))
        count_query = count_query.where(Order.created_at >= dt.fromisoformat(start_date))
    if end_date:
        from datetime import datetime as dt
        query = query.where(Order.created_at <= dt.fromisoformat(end_date + "T23:59:59"))
        count_query = count_query.where(Order.created_at <= dt.fromisoformat(end_date + "T23:59:59"))

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


@router.get("/orders/statistics")
async def admin_order_statistics(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    today_count = (await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )).scalar() or 0

    today_amount = (await db.execute(
        select(func.coalesce(func.sum(Order.paid_amount), 0)).where(
            Order.created_at >= today_start,
            Order.payment_status == "paid"
        )
    )).scalar() or 0

    month_count = (await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= month_start)
    )).scalar() or 0

    month_amount = (await db.execute(
        select(func.coalesce(func.sum(Order.paid_amount), 0)).where(
            Order.created_at >= month_start,
            Order.payment_status == "paid"
        )
    )).scalar() or 0

    total_count = (await db.execute(
        select(func.count(Order.id))
    )).scalar() or 0

    total_amount = (await db.execute(
        select(func.coalesce(func.sum(Order.paid_amount), 0)).where(
            Order.payment_status == "paid"
        )
    )).scalar() or 0

    return {
        "today_count": today_count,
        "today_amount": float(today_amount),
        "month_count": month_count,
        "month_amount": float(month_amount),
        "total_count": total_count,
        "total_amount": float(total_amount),
    }


@router.get("/orders/trends")
async def admin_order_trends(
    days: int = Query(7, ge=1, le=30),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    results = []
    for i in range(days - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start.replace(hour=23, minute=59, second=59)

        day_count = (await db.execute(
            select(func.count(Order.id)).where(
                Order.created_at >= day_start,
                Order.created_at <= day_end
            )
        )).scalar() or 0

        day_amount = (await db.execute(
            select(func.coalesce(func.sum(Order.paid_amount), 0)).where(
                Order.created_at >= day_start,
                Order.created_at <= day_end,
                Order.payment_status == "paid"
            )
        )).scalar() or 0

        results.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": day_count,
            "amount": float(day_amount),
        })

    return {"trends": results}


@router.get("/orders/distribution")
async def admin_order_distribution(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    category_results = (await db.execute(
        select(
            ServiceItem.name,
            func.count(Order.id).label("count")
        ).join(ServiceItem, Order.service_item_id == ServiceItem.id)
        .group_by(ServiceItem.name)
    )).all()

    category_distribution = [{"name": r[0] or "未知", "count": r[1]} for r in category_results]

    status_results = (await db.execute(
        select(
            Order.order_status,
            func.count(Order.id).label("count")
        ).group_by(Order.order_status)
    )).all()

    status_distribution = [{"status": r[0], "count": r[1]} for r in status_results]

    return {
        "category_distribution": category_distribution,
        "status_distribution": status_distribution,
    }


@router.put("/orders/{order_id}/confirm")
async def admin_confirm_order(
    order_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.order import OrderResponse
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.order_status != "pending" or order.payment_status != "paid":
        raise HTTPException(status_code=400, detail="只有已支付待确认的订单可以确认")
    order.order_status = "confirmed"
    await db.flush()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.put("/orders/{order_id}/start-service")
async def admin_start_service(
    order_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.order import OrderResponse
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.order_status != "confirmed":
        raise HTTPException(status_code=400, detail="只有已确认的订单可以开始服务")
    order.order_status = "processing"
    await db.flush()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.put("/orders/{order_id}/complete")
async def admin_complete_order(
    order_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.order import OrderResponse
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.order_status != "processing":
        raise HTTPException(status_code=400, detail="只有服务中的订单可以完成")
    order.order_status = "completed"
    await db.flush()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.put("/orders/{order_id}/cancel")
async def admin_cancel_order(
    order_id: int,
    reason: Optional[str] = Body(None),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.order import OrderResponse
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order.order_status = "cancelled"
    if reason and hasattr(order, 'notes'):
        order.notes = f"取消原因: {reason}"
    await db.flush()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.put("/orders/{order_id}/refund")
async def admin_refund_order(
    order_id: int,
    reason: Optional[str] = Body(None),
    refund_amount: Optional[float] = Body(None),
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
    article_data = data.model_dump(exclude_unset=True)
    article_status = article_data.pop("status", None) or "published"
    article = Article(
        **article_data,
        author_id=current_user.id,
        status=article_status,
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
    video_data = data.model_dump()
    dur = video_data.get("duration")
    if dur is not None:
        if isinstance(dur, str) and ':' in dur:
            parts = dur.split(':')
            video_data['duration'] = int(parts[0]) * 60 + int(parts[1])
        else:
            try:
                video_data['duration'] = int(dur)
            except (ValueError, TypeError):
                video_data['duration'] = 0
    video = Video(
        **video_data,
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
    data: VideoUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    update_data = data.model_dump(exclude_unset=True)
    if 'duration' in update_data and update_data['duration'] is not None:
        dur = update_data['duration']
        if isinstance(dur, str) and ':' in dur:
            parts = dur.split(':')
            update_data['duration'] = int(parts[0]) * 60 + int(parts[1])
        else:
            try:
                update_data['duration'] = int(dur)
            except (ValueError, TypeError):
                update_data['duration'] = 0
    for key, value in update_data.items():
        if hasattr(video, key):
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
    data: PointsMallItemCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    item = PointsMallItem(
        name=data.name,
        description=data.description,
        type=data.type,
        price_points=data.price_points,
        stock=data.stock,
        images=data.images,
        status=data.status or "active",
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    from app.schemas.points import PointsMallItemResponse
    return PointsMallItemResponse.model_validate(item)


@router.put("/points/mall/{item_id}")
async def admin_update_mall_item(
    item_id: int,
    data: PointsMallItemUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    await db.flush()
    await db.refresh(item)
    from app.schemas.points import PointsMallItemResponse
    return PointsMallItemResponse.model_validate(item)


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


# ── 积分兑换记录 ──

@router.get("/points/exchange-records")
async def admin_list_exchange_records(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import PointsExchange
    query = select(PointsExchange)
    count_query = select(func.count(PointsExchange.id))

    if keyword:
        user_subq = select(User.id).where(
            or_(User.nickname.contains(keyword), User.phone.contains(keyword))
        )
        query = query.where(PointsExchange.user_id.in_(user_subq))
        count_query = count_query.where(PointsExchange.user_id.in_(user_subq))

    if start_date:
        from datetime import datetime as dt
        query = query.where(PointsExchange.created_at >= dt.fromisoformat(start_date))
        count_query = count_query.where(PointsExchange.created_at >= dt.fromisoformat(start_date))
    if end_date:
        from datetime import datetime as dt
        query = query.where(PointsExchange.created_at <= dt.fromisoformat(end_date + "T23:59:59"))
        count_query = count_query.where(PointsExchange.created_at <= dt.fromisoformat(end_date + "T23:59:59"))

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(PointsExchange.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    records = (await db.execute(query)).scalars().all()

    from app.schemas.points import PointsExchangeResponse
    items = [PointsExchangeResponse.model_validate(r) for r in records]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── 仪表盘 ──

@router.get("/dashboard", response_model=DashboardStats, response_model_by_alias=True)
@router.get("/dashboard/stats", response_model=DashboardStats, response_model_by_alias=True)
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

    ai_calls_result = await db.execute(select(func.count(ChatMessage.id)).where(ChatMessage.role == MessageRole.assistant))
    ai_calls = ai_calls_result.scalar() or 0

    end_day = datetime.utcnow().date()
    start_day = end_day - timedelta(days=6)
    trend_window_start = datetime.combine(start_day, datetime.min.time())
    trend_labels = [_day_label(start_day + timedelta(days=i)) for i in range(7)]

    ug_rows = (
        await db.execute(
            select(func.date(User.created_at), func.count(User.id))
            .where(User.created_at >= trend_window_start)
            .group_by(func.date(User.created_at))
        )
    ).all()
    user_growth = _rows_to_trend(trend_labels, ug_rows)

    ot_rows = (
        await db.execute(
            select(func.date(Order.created_at), func.count(Order.id))
            .where(Order.created_at >= trend_window_start)
            .group_by(func.date(Order.created_at))
        )
    ).all()
    order_trend = _rows_to_trend(trend_labels, ot_rows)

    recent_orders: list[DashboardRecentOrder] = []
    ro_result = await db.execute(
        select(Order, User, ServiceItem)
        .join(User, Order.user_id == User.id)
        .join(ServiceItem, Order.service_item_id == ServiceItem.id)
        .order_by(Order.created_at.desc())
        .limit(5)
    )
    for order, u, svc in ro_result.all():
        nickname = (u.nickname or "").strip() or (u.phone or f"用户{u.id}")
        created = order.created_at or datetime.utcnow()
        recent_orders.append(
            DashboardRecentOrder(
                id=order.order_no,
                user=nickname,
                service=svc.name or "",
                amount=float(order.total_amount or 0),
                status=_order_row_status(order),
                time=created.strftime("%Y-%m-%d %H:%M"),
            )
        )

    return DashboardStats(
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue,
        today_new_users=today_new_users,
        today_orders=today_orders,
        today_revenue=today_revenue,
        active_experts=active_experts,
        total_articles=total_articles,
        user_growth=user_growth,
        order_trend=order_trend,
        recent_orders=recent_orders,
        ai_calls=ai_calls,
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
        count_result = await db.execute(
            select(func.count(User.id)).where(
                User.points >= lv.min_points,
                User.points <= lv.max_points,
            )
        )
        member_count = count_result.scalar() or 0
        benefits_str = lv.benefits
        if isinstance(lv.benefits, dict):
            benefits_str = lv.benefits.get("desc", "")
        items.append({
            "id": lv.id,
            "name": lv.level_name,
            "icon": lv.icon or "",
            "minPoints": lv.min_points,
            "maxPoints": lv.max_points,
            "discount": int(lv.discount_rate * 100) if lv.discount_rate else 100,
            "benefits": benefits_str or "",
            "color": lv.color or "#52c41a",
            "memberCount": member_count,
        })
    return {"items": items}


@router.post("/points/levels")
async def admin_create_or_update_level(
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    level_id = data.get("id")
    level_name = data.get("name") or data.get("level_name", "")
    icon = data.get("icon", "")
    min_points = data.get("minPoints") if data.get("minPoints") is not None else data.get("min_points", 0)
    max_points = data.get("maxPoints") if data.get("maxPoints") is not None else data.get("max_points", 0)
    discount_raw = data.get("discount")
    discount_rate = (discount_raw / 100.0) if discount_raw is not None else data.get("discount_rate", 1.0)
    benefits = data.get("benefits")
    color = data.get("color")

    if level_id:
        result = await db.execute(select(MemberLevel).where(MemberLevel.id == level_id))
        level = result.scalar_one_or_none()
        if level:
            level.level_name = level_name
            level.icon = icon
            level.min_points = min_points
            level.max_points = max_points
            level.discount_rate = discount_rate
            level.benefits = benefits
            level.color = color
            return {"message": "更新成功", "id": level.id}

    level = MemberLevel(
        level_name=level_name,
        icon=icon,
        min_points=min_points,
        max_points=max_points,
        discount_rate=discount_rate,
        benefits=benefits,
        color=color,
    )
    db.add(level)
    await db.flush()
    await db.refresh(level)
    return {"message": "创建成功", "id": level.id}


@router.put("/points/levels/{level_id}")
async def admin_update_member_level(
    level_id: int,
    data: dict = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MemberLevel).where(MemberLevel.id == level_id))
    level = result.scalar_one_or_none()
    if not level:
        raise HTTPException(status_code=404, detail="等级不存在")
    if "name" in data:
        level.level_name = data["name"]
    if "icon" in data:
        level.icon = data["icon"]
    if "minPoints" in data:
        level.min_points = data["minPoints"]
    if "maxPoints" in data:
        level.max_points = data["maxPoints"]
    if "discount" in data:
        level.discount_rate = data["discount"] / 100.0
    if "benefits" in data:
        level.benefits = data["benefits"]
    if "color" in data:
        level.color = data["color"]
    return {"message": "更新成功", "id": level.id}


@router.delete("/points/levels/{level_id}")
async def admin_delete_member_level(
    level_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MemberLevel).where(MemberLevel.id == level_id))
    level = result.scalar_one_or_none()
    if not level:
        raise HTTPException(status_code=404, detail="等级不存在")
    await db.delete(level)
    return {"message": "删除成功"}


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


@router.post("/settings/push", deprecated=True)
async def update_push_settings(
    current_user=Depends(admin_dep),
):
    raise HTTPException(
        status_code=410,
        detail="此接口已废弃。短信配置请使用 /api/admin/sms/config，微信推送请使用 /api/admin/wechat-push/config，邮件通知请使用 /api/admin/email-notify/config",
    )


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
