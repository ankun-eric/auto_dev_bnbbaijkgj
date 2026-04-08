import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import DrugIdentifyDetail, ShareLink, User

router = APIRouter(prefix="/api/drug-identify", tags=["拍照识药分享"])


class DrugShareCreateResponse(BaseModel):
    share_url: str
    share_token: str
    record_id: int


class DrugShareViewResponse(BaseModel):
    record_id: int
    drug_name: str | None = None
    drug_category: str | None = None
    dosage: str | None = None
    precautions: str | None = None
    ai_structured_result: dict | list | None = None
    original_image_url: str | None = None
    created_at: datetime
    view_count: int


@router.post("/{record_id}/share", response_model=DrugShareCreateResponse)
async def create_drug_share(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DrugIdentifyDetail).where(
            DrugIdentifyDetail.id == record_id,
            DrugIdentifyDetail.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    existing_result = await db.execute(
        select(ShareLink).where(
            ShareLink.link_type == "drug",
            ShareLink.record_id == record_id,
            ShareLink.user_id == current_user.id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return DrugShareCreateResponse(
            share_url=f"/api/drug-identify/share/{existing.link_token}",
            share_token=existing.link_token,
            record_id=record_id,
        )

    token = secrets.token_urlsafe(32)
    share_link = ShareLink(
        link_token=token,
        link_type="drug",
        record_id=record_id,
        user_id=current_user.id,
        view_count=0,
    )
    db.add(share_link)
    await db.flush()

    return DrugShareCreateResponse(
        share_url=f"/api/drug-identify/share/{token}",
        share_token=token,
        record_id=record_id,
    )


@router.get("/share/{token}", response_model=DrugShareViewResponse)
async def view_drug_share(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    link_result = await db.execute(
        select(ShareLink).where(
            ShareLink.link_token == token,
            ShareLink.link_type == "drug",
        )
    )
    link = link_result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="分享链接无效")

    record_result = await db.execute(
        select(DrugIdentifyDetail).where(DrugIdentifyDetail.id == link.record_id)
    )
    record = record_result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    link.view_count = (link.view_count or 0) + 1
    await db.flush()

    return DrugShareViewResponse(
        record_id=record.id,
        drug_name=record.drug_name,
        drug_category=record.drug_category,
        dosage=record.dosage,
        precautions=record.precautions,
        ai_structured_result=record.ai_structured_result,
        original_image_url=record.original_image_url,
        created_at=record.created_at,
        view_count=link.view_count,
    )
