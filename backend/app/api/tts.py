import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import SystemConfig, User
from app.schemas.tts import (
    TTSConfigFullResponse,
    TTSConfigResponse,
    TTSConfigUpdate,
    TTSSynthesizeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["TTS语音播报"])
admin_router = APIRouter(prefix="/api/admin", tags=["TTS管理"])

TTS_CONFIG_KEY = "tts_config"

DEFAULT_TTS_CONFIG = {
    "enabled": False,
    "default_mode": "free",
    "h5_mode": None,
    "miniprogram_mode": None,
    "app_mode": None,
    "cloud_provider": "aliyun",
    "cloud_api_key": None,
    "voice_gender": "female",
    "speed": 1.0,
    "pitch": 1.0,
}


async def _get_tts_config(db: AsyncSession) -> dict:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == TTS_CONFIG_KEY)
    )
    config = result.scalar_one_or_none()
    if config and config.config_value:
        try:
            return {**DEFAULT_TTS_CONFIG, **json.loads(config.config_value)}
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_TTS_CONFIG)


async def _save_tts_config(db: AsyncSession, data: dict):
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == TTS_CONFIG_KEY)
    )
    config = result.scalar_one_or_none()
    value_str = json.dumps(data, ensure_ascii=False)
    if config:
        config.config_value = value_str
        config.updated_at = datetime.utcnow()
    else:
        db.add(SystemConfig(
            config_key=TTS_CONFIG_KEY,
            config_value=value_str,
            config_type="json",
            description="TTS语音播报配置",
        ))
    await db.flush()


@router.get("/api/settings/tts-config", response_model=TTSConfigResponse)
async def get_tts_config_for_platform(
    platform: str = Query("h5", description="平台: h5/miniprogram/app"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_tts_config(db)
    platform_key = f"{platform}_mode"
    platform_mode = cfg.get(platform_key)
    return TTSConfigResponse(
        enabled=cfg.get("enabled", False),
        default_mode=cfg.get("default_mode", "free"),
        platform_override=platform_mode,
        cloud_provider=cfg.get("cloud_provider"),
        voice_gender=cfg.get("voice_gender", "female"),
        speed=cfg.get("speed", 1.0),
        pitch=cfg.get("pitch", 1.0),
    )


@admin_router.get("/settings/tts-config", response_model=TTSConfigFullResponse)
async def admin_get_tts_config(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    cfg = await _get_tts_config(db)
    return TTSConfigFullResponse(**cfg)


@admin_router.put("/settings/tts-config", response_model=TTSConfigFullResponse)
async def admin_update_tts_config(
    data: TTSConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    cfg = await _get_tts_config(db)
    update_data = data.model_dump(exclude_unset=True)
    cfg.update(update_data)
    await _save_tts_config(db, cfg)
    return TTSConfigFullResponse(**cfg)


@router.post("/api/tts/synthesize")
async def tts_synthesize(
    data: TTSSynthesizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_tts_config(db)
    if not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="TTS语音播报功能未启用")

    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本内容不能为空")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="文本长度不能超过5000字")

    voice_gender = data.voice_gender or cfg.get("voice_gender", "female")
    speed = data.speed if data.speed is not None else cfg.get("speed", 1.0)
    pitch = data.pitch if data.pitch is not None else cfg.get("pitch", 1.0)

    provider = cfg.get("cloud_provider", "aliyun")
    api_key = cfg.get("cloud_api_key")

    if not api_key:
        raise HTTPException(status_code=500, detail="TTS云端服务未配置API Key")

    audio_filename = f"tts_{uuid.uuid4().hex}.mp3"
    audio_dir = os.path.join("uploads", "tts")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, audio_filename)

    try:
        if provider == "aliyun":
            audio_data = await _synthesize_aliyun(text, api_key, voice_gender, speed, pitch)
        elif provider == "tencent":
            audio_data = await _synthesize_tencent(text, api_key, voice_gender, speed, pitch)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的TTS服务商: {provider}")

        with open(audio_path, "wb") as f:
            f.write(audio_data)

        audio_url = f"/uploads/tts/{audio_filename}"
        return {"audio_url": audio_url, "text_length": len(text), "provider": provider}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("TTS synthesize failed: %s", e)
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


async def _synthesize_aliyun(text: str, api_key: str, voice_gender: str, speed: float, pitch: float) -> bytes:
    import httpx

    voice_map = {
        "female": "xiaoyun",
        "male": "xiaogang",
    }
    voice = voice_map.get(voice_gender, "xiaoyun")
    speech_rate = int((speed - 1.0) * 500)
    pitch_rate = int((pitch - 1.0) * 500)

    url = "https://nls-gateway.aliyuncs.com/stream/v1/tts"
    params = {
        "appkey": api_key,
        "text": text,
        "format": "mp3",
        "voice": voice,
        "speech_rate": speech_rate,
        "pitch_rate": pitch_rate,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        if resp.headers.get("content-type", "").startswith("audio/"):
            return resp.content
        raise Exception(f"Aliyun TTS error: {resp.text[:500]}")


async def _synthesize_tencent(text: str, api_key: str, voice_gender: str, speed: float, pitch: float) -> bytes:
    import httpx
    import base64

    voice_type = 1001 if voice_gender == "female" else 1002
    speed_val = speed

    url = "https://tts.cloud.tencent.com/stream"
    payload = {
        "Action": "TextToStreamAudio",
        "AppId": 0,
        "Text": text,
        "VoiceType": voice_type,
        "Speed": speed_val,
        "Codec": "mp3",
        "SessionId": uuid.uuid4().hex,
        "SecretId": api_key,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        if resp.headers.get("content-type", "").startswith("audio/"):
            return resp.content
        data = resp.json()
        if "Audio" in data:
            return base64.b64decode(data["Audio"])
        raise Exception(f"Tencent TTS error: {resp.text[:500]}")
