import json
import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    ChatMessage,
    ChatSession,
    ChatShareRecord,
    SystemConfig,
    User,
)
from app.schemas.share import (
    ChatShareCreate,
    ChatShareResponse,
    PosterGenerateRequest,
    ShareConfigResponse,
    ShareConfigUpdate,
    SharedConversationResponse,
    SharedMessageItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["对话分享"])
admin_router = APIRouter(prefix="/api/admin", tags=["分享配置管理"])

SHARE_CONFIG_KEY = "share_poster_config"

DEFAULT_SHARE_CONFIG = {
    "logo_url": None,
    "product_name": "宾尼小康",
    "slogan": "AI健康管家",
    "qr_code_url": None,
    "background_color": "#ffffff",
    "template": "default",
}


async def _get_share_config(db: AsyncSession) -> dict:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == SHARE_CONFIG_KEY)
    )
    config = result.scalar_one_or_none()
    if config and config.config_value:
        try:
            return {**DEFAULT_SHARE_CONFIG, **json.loads(config.config_value)}
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_SHARE_CONFIG)


async def _save_share_config(db: AsyncSession, data: dict):
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == SHARE_CONFIG_KEY)
    )
    config = result.scalar_one_or_none()
    value_str = json.dumps(data, ensure_ascii=False)
    if config:
        config.config_value = value_str
        config.updated_at = datetime.utcnow()
    else:
        db.add(SystemConfig(
            config_key=SHARE_CONFIG_KEY,
            config_value=value_str,
            config_type="json",
            description="分享海报配置",
        ))
    await db.flush()


@router.post("/chat/share", response_model=ChatShareResponse)
async def create_share(
    data: ChatShareCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == data.session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == data.message_id)
    )
    target_msg = msg_result.scalar_one_or_none()
    if not target_msg or target_msg.session_id != data.session_id:
        raise HTTPException(status_code=404, detail="消息不存在")

    if target_msg.role.value if hasattr(target_msg.role, "value") else target_msg.role == "user":
        user_msg = target_msg
        ai_result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == data.session_id,
                ChatMessage.id > target_msg.id,
                ChatMessage.role == "assistant",
            ).order_by(ChatMessage.id.asc()).limit(1)
        )
        ai_msg = ai_result.scalar_one_or_none()
        if not ai_msg:
            raise HTTPException(status_code=400, detail="该消息没有对应的AI回复")
    else:
        ai_msg = target_msg
        user_result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == data.session_id,
                ChatMessage.id < target_msg.id,
                ChatMessage.role == "user",
            ).order_by(ChatMessage.id.desc()).limit(1)
        )
        user_msg = user_result.scalar_one_or_none()
        if not user_msg:
            raise HTTPException(status_code=400, detail="找不到对应的用户消息")

    existing = await db.execute(
        select(ChatShareRecord).where(
            ChatShareRecord.user_message_id == user_msg.id,
            ChatShareRecord.ai_message_id == ai_msg.id,
        )
    )
    existing_share = existing.scalar_one_or_none()
    if existing_share:
        return ChatShareResponse(
            share_token=existing_share.share_token,
            share_url=f"/share/{existing_share.share_token}",
        )

    share_token = uuid.uuid4().hex[:32]
    share_record = ChatShareRecord(
        share_token=share_token,
        session_id=data.session_id,
        user_message_id=user_msg.id,
        ai_message_id=ai_msg.id,
        user_id=current_user.id,
    )
    db.add(share_record)
    await db.flush()

    return ChatShareResponse(
        share_token=share_token,
        share_url=f"/share/{share_token}",
    )


@router.get("/share/{share_token}", response_model=SharedConversationResponse)
async def view_shared_conversation(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatShareRecord).where(ChatShareRecord.share_token == share_token)
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="分享链接不存在或已失效")

    share.view_count = (share.view_count or 0) + 1

    session_result = await db.execute(
        select(ChatSession).where(ChatSession.id == share.session_id)
    )
    session = session_result.scalar_one_or_none()

    user_result = await db.execute(
        select(User).where(User.id == share.user_id)
    )
    user = user_result.scalar_one_or_none()

    user_msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == share.user_message_id)
    )
    user_msg = user_msg_result.scalar_one_or_none()

    ai_msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == share.ai_message_id)
    )
    ai_msg = ai_msg_result.scalar_one_or_none()

    if not user_msg or not ai_msg:
        raise HTTPException(status_code=404, detail="消息数据缺失")

    await db.flush()

    return SharedConversationResponse(
        session_title=session.title if session else None,
        session_type=session.session_type.value if session and hasattr(session.session_type, "value") else (session.session_type if session else None),
        user_nickname=user.nickname if user else None,
        user_message=SharedMessageItem(
            role="user",
            content=user_msg.content,
            created_at=user_msg.created_at,
        ),
        ai_message=SharedMessageItem(
            role="assistant",
            content=ai_msg.content,
            created_at=ai_msg.created_at,
        ),
        view_count=share.view_count,
        created_at=share.created_at,
    )


@router.post("/chat/share/poster")
async def generate_poster(
    data: PosterGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == data.session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id == data.message_id,
            ChatMessage.session_id == data.session_id,
        )
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")

    share_cfg = await _get_share_config(db)

    ai_content = data.ai_content_preview or msg.content or ""
    if len(ai_content) > 300:
        ai_content = ai_content[:297] + "..."

    poster_filename = f"poster_{uuid.uuid4().hex}.png"
    poster_dir = os.path.join("uploads", "posters")
    os.makedirs(poster_dir, exist_ok=True)
    poster_path = os.path.join(poster_dir, poster_filename)

    try:
        _generate_poster_image(
            output_path=poster_path,
            product_name=share_cfg.get("product_name", "宾尼小康"),
            slogan=share_cfg.get("slogan", "AI健康管家"),
            ai_content=ai_content,
            background_color=share_cfg.get("background_color", "#ffffff"),
            user_nickname=current_user.nickname or "用户",
        )
    except Exception as e:
        logger.error("Poster generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"海报生成失败: {str(e)}")

    poster_url = f"/uploads/posters/{poster_filename}"
    return {"poster_url": poster_url}


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        current_line = ""
        for char in paragraph:
            test = current_line + char
            bbox = font.getbbox(test)
            w = bbox[2] - bbox[0]
            if w > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = char
            else:
                current_line = test
        if current_line:
            lines.append(current_line)
    return lines


def _generate_poster_image(
    output_path: str,
    product_name: str,
    slogan: str,
    ai_content: str,
    background_color: str,
    user_nickname: str,
):
    width, height = 750, 1334
    bg_color = _hex_to_rgb(background_color) if background_color.startswith("#") else (255, 255, 255)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except (OSError, IOError):
        try:
            title_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 36)
            body_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
            small_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

    padding = 60
    y_cursor = 80

    draw.rounded_rectangle(
        [padding - 20, 40, width - padding + 20, height - 40],
        radius=20,
        fill=(250, 250, 252),
        outline=(220, 220, 230),
        width=2,
    )

    draw.text((padding, y_cursor), product_name, font=title_font, fill=(51, 51, 51))
    y_cursor += 50
    draw.text((padding, y_cursor), slogan, font=small_font, fill=(153, 153, 153))
    y_cursor += 50

    draw.line([(padding, y_cursor), (width - padding, y_cursor)], fill=(230, 230, 235), width=1)
    y_cursor += 30

    draw.text((padding, y_cursor), f"{user_nickname} 的健康咨询", font=body_font, fill=(102, 102, 102))
    y_cursor += 50

    content_lines = _wrap_text(ai_content, body_font, width - padding * 2)
    max_lines = 20
    for line in content_lines[:max_lines]:
        draw.text((padding, y_cursor), line, font=body_font, fill=(68, 68, 68))
        y_cursor += 34
    if len(content_lines) > max_lines:
        draw.text((padding, y_cursor), "...", font=body_font, fill=(153, 153, 153))
        y_cursor += 34

    y_cursor = height - 120
    draw.line([(padding, y_cursor), (width - padding, y_cursor)], fill=(230, 230, 235), width=1)
    y_cursor += 20

    draw.text((padding, y_cursor), "扫码了解更多健康知识", font=small_font, fill=(153, 153, 153))
    draw.text((padding, y_cursor + 30), "— 宾尼小康 AI健康管家 —", font=small_font, fill=(180, 180, 180))

    img.save(output_path, "PNG", quality=95)


# ──── Admin share config ────


@admin_router.get("/settings/share-config", response_model=ShareConfigResponse)
async def admin_get_share_config(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    cfg = await _get_share_config(db)
    return ShareConfigResponse(**cfg)


@admin_router.put("/settings/share-config", response_model=ShareConfigResponse)
async def admin_update_share_config(
    data: ShareConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    cfg = await _get_share_config(db)
    update_data = data.model_dump(exclude_unset=True)
    cfg.update(update_data)
    await _save_share_config(db, cfg)
    return ShareConfigResponse(**cfg)
