from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import FamilyInvitation, FamilyMember, User

router = APIRouter(tags=["扫码路由"])

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


@router.get("/api/scan")
async def scan_dispatch(
    type: str = Query(..., description="扫码类型"),
    code: str = Query(..., description="业务码"),
    db: AsyncSession = Depends(get_db),
):
    if type == "family_invite":
        return await _handle_family_invite(code, db)

    raise HTTPException(status_code=400, detail=f"不支持的扫码类型: {type}")


async def _handle_family_invite(code: str, db: AsyncSession):
    result = await db.execute(
        select(FamilyInvitation).where(FamilyInvitation.invite_code == code)
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请码不存在")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="该邀请已失效")

    if invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        await db.flush()
        raise HTTPException(status_code=400, detail="邀请已过期")

    inviter_result = await db.execute(
        select(User).where(User.id == invitation.inviter_user_id)
    )
    inviter = inviter_result.scalar_one_or_none()

    member_result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == invitation.member_id)
    )
    member = member_result.scalar_one_or_none()

    redirect_url = f"{BASE_URL}/family-invite-confirm?code={code}"

    return {
        "type": "family_invite",
        "redirect_url": redirect_url,
        "invitation": {
            "invite_code": invitation.invite_code,
            "status": invitation.status,
            "inviter_nickname": inviter.nickname if inviter else None,
            "inviter_avatar": inviter.avatar if inviter else None,
            "member_nickname": member.nickname if member else None,
            "expires_at": invitation.expires_at.isoformat(),
            "created_at": invitation.created_at.isoformat(),
        },
    }
