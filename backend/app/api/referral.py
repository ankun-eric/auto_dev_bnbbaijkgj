import os

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.models import User
from app.schemas.user import LandingPageResponse, ShareLinkResponse

router = APIRouter(tags=["推荐"])

DEFAULT_BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


@router.get("/api/users/share-link", response_model=ShareLinkResponse)
async def get_share_link(current_user: User = Depends(get_current_user)):
    base_url = os.getenv("BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return ShareLinkResponse(
        share_link=f"{base_url}/landing?ref={current_user.user_no}",
        user_no=current_user.user_no or "",
    )


@router.get("/api/landing", response_model=LandingPageResponse)
async def get_landing_page():
    return LandingPageResponse(
        brand_name="宾尼小康",
        tagline="AI智能健康管家",
        features=[
            "AI智能健康问答",
            "体检报告智能解读",
            "中医体质辨识",
            "个性化健康计划",
            "家庭健康档案管理",
        ],
    )
