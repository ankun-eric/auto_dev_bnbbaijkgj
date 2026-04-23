"""预约表单库管理（BUG-PRODUCT-APPT-001）

将原来"表单"按钮偷偷为每个商品建一张表单的潜规则，升级为显式的全局表单库：
- 表单作为可复用资源，多个商品可绑定同一张表单
- 提供完整的 CRUD / 启用停用 / 字段管理接口
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    AppointmentForm,
    AppointmentFormField,
    Product,
)
from app.schemas.products import (
    AppointmentFormCreate,
    AppointmentFormFieldCreate,
    AppointmentFormFieldResponse,
    AppointmentFormFieldUpdate,
    AppointmentFormResponse,
    AppointmentFormUpdate,
)

router = APIRouter(prefix="/api/admin/appointment-forms", tags=["预约表单库"])


async def _to_response(db: AsyncSession, form: AppointmentForm) -> dict:
    field_cnt = (await db.execute(
        select(func.count(AppointmentFormField.id)).where(AppointmentFormField.form_id == form.id)
    )).scalar() or 0
    product_cnt = (await db.execute(
        select(func.count(Product.id)).where(Product.custom_form_id == form.id)
    )).scalar() or 0
    return {
        "id": form.id,
        "name": form.name,
        "description": form.description or "",
        "status": getattr(form, "status", "active") or "active",
        "field_count": int(field_cnt),
        "product_count": int(product_cnt),
        "created_at": form.created_at,
    }


@router.get("")
async def list_forms(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AppointmentForm)
    count_query = select(func.count(AppointmentForm.id))
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(AppointmentForm.name.like(kw))
        count_query = count_query.where(AppointmentForm.name.like(kw))
    if status:
        query = query.where(AppointmentForm.status == status)
        count_query = count_query.where(AppointmentForm.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(AppointmentForm.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    forms = list(result.scalars().all())
    items = [await _to_response(db, f) for f in forms]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_form(
    data: AppointmentFormCreate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="表单名称不能为空")
    form = AppointmentForm(
        name=data.name.strip(),
        description=data.description,
        status=data.status or "active",
    )
    db.add(form)
    await db.flush()
    await db.refresh(form)
    return await _to_response(db, form)


@router.put("/{form_id}")
async def update_form(
    form_id: int,
    data: AppointmentFormUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    form = (await db.execute(
        select(AppointmentForm).where(AppointmentForm.id == form_id)
    )).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="表单不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(form, key, value)
    form.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(form)
    return await _to_response(db, form)


@router.delete("/{form_id}")
async def delete_form(
    form_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    form = (await db.execute(
        select(AppointmentForm).where(AppointmentForm.id == form_id)
    )).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="表单不存在")

    # 若被商品引用，改为"禁用"（保护历史数据）
    used = (await db.execute(
        select(func.count(Product.id)).where(Product.custom_form_id == form_id)
    )).scalar() or 0
    if used > 0:
        raise HTTPException(
            status_code=409,
            detail=f"该表单正被 {used} 个商品引用，无法删除。请先解绑或将其停用",
        )

    # 先删字段再删表单，避免外键阻断
    fields = (await db.execute(
        select(AppointmentFormField).where(AppointmentFormField.form_id == form_id)
    )).scalars().all()
    for f in fields:
        await db.delete(f)
    await db.delete(form)
    return {"message": "表单已删除"}


@router.get("/{form_id}/fields")
async def list_form_fields(
    form_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    form = (await db.execute(
        select(AppointmentForm).where(AppointmentForm.id == form_id)
    )).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail="表单不存在")
    fields_result = await db.execute(
        select(AppointmentFormField)
        .where(AppointmentFormField.form_id == form_id)
        .order_by(AppointmentFormField.sort_order.asc())
    )
    items = [AppointmentFormFieldResponse.model_validate(f) for f in fields_result.scalars().all()]
    return {"items": items, "form_id": form_id}


@router.post("/{form_id}/fields")
async def create_form_field(
    form_id: int,
    data: AppointmentFormFieldCreate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    form_row = (await db.execute(
        select(AppointmentForm).where(AppointmentForm.id == form_id)
    )).scalar_one_or_none()
    if not form_row:
        raise HTTPException(status_code=404, detail="表单不存在")
    field = AppointmentFormField(
        form_id=form_id,
        field_type=data.field_type,
        label=data.label,
        placeholder=data.placeholder,
        required=data.required,
        options=data.options,
        sort_order=data.sort_order,
    )
    db.add(field)
    await db.flush()
    await db.refresh(field)
    return AppointmentFormFieldResponse.model_validate(field)


@router.put("/{form_id}/fields/{field_id}")
async def update_form_field(
    form_id: int,
    field_id: int,
    data: AppointmentFormFieldUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    field = (await db.execute(
        select(AppointmentFormField).where(
            AppointmentFormField.id == field_id,
            AppointmentFormField.form_id == form_id,
        )
    )).scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(field, key, value)
    await db.flush()
    await db.refresh(field)
    return AppointmentFormFieldResponse.model_validate(field)


@router.delete("/{form_id}/fields/{field_id}")
async def delete_form_field(
    form_id: int,
    field_id: int,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    field = (await db.execute(
        select(AppointmentFormField).where(
            AppointmentFormField.id == field_id,
            AppointmentFormField.form_id == form_id,
        )
    )).scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")
    await db.delete(field)
    return {"message": "字段已删除"}
