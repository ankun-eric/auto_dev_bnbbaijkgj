"""PRD-405 AI 对话模式首页配置 API。

提供：
- GET /api/ai-home-config 用户端读取（公开）
- GET /api/admin/ai-home-config admin 读取
- PUT /api/admin/ai-home-config admin 整体保存
- PATCH /api/admin/ai-home-config/{module} admin 按模块保存
- POST /api/admin/ai-home-config/upload-image admin 上传图片
- GET /api/admin/ai-home-config/logs admin 操作日志列表
- GET /api/admin/ai-home-config/logs/{id} admin 操作日志详情
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import AIHomeConfigLog, AppSetting
from app.schemas.ai_home_config import (
    AIHomeConfigLogDetail,
    AIHomeConfigLogItem,
    AIHomeConfigLogList,
    AIHomeConfigPayload,
    AIHomeConfigResponse,
    AIHomeModulePatch,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI对话首页配置"])

admin_dep = require_role("admin")

CONFIG_KEY = "ai_home_config"
CHAT_IDLE_TIMEOUT_KEY = "chat_idle_timeout_minutes"

VALID_MODULES = {
    "welcome",
    "topbar",
    "input",
    "session",
    "floating_button",
    "banner",
    "func_grid",
    "quick_tags",
    "recommended_questions",
    "all",
}


# ──────────────── 工具：读写配置 ────────────────


async def _load_config(db: AsyncSession) -> Dict[str, Any]:
    """读取配置，返回 dict（合并默认值）。"""
    result = await db.execute(select(AppSetting).where(AppSetting.key == CONFIG_KEY))
    setting = result.scalar_one_or_none()
    if not setting or not setting.value:
        cfg = AIHomeConfigPayload().model_dump()
    else:
        try:
            stored = json.loads(setting.value)
        except json.JSONDecodeError:
            stored = {}
        cfg = AIHomeConfigPayload(**stored).model_dump() if isinstance(stored, dict) else AIHomeConfigPayload().model_dump()

    # 同步空闲超时：从 chat_idle_timeout_minutes 读取最新值
    timeout_setting = (
        await db.execute(select(AppSetting).where(AppSetting.key == CHAT_IDLE_TIMEOUT_KEY))
    ).scalar_one_or_none()
    if timeout_setting and timeout_setting.value:
        try:
            cfg.setdefault("session", {})["idle_timeout_minutes"] = int(timeout_setting.value)
        except (TypeError, ValueError):
            pass

    return cfg


async def _save_config(db: AsyncSession, cfg: Dict[str, Any]) -> AppSetting:
    result = await db.execute(select(AppSetting).where(AppSetting.key == CONFIG_KEY))
    setting = result.scalar_one_or_none()
    value_json = json.dumps(cfg, ensure_ascii=False, default=str)
    if not setting:
        setting = AppSetting(
            key=CONFIG_KEY,
            value=value_json,
            description="AI 对话模式首页配置（JSON 聚合）",
        )
        db.add(setting)
    else:
        setting.value = value_json
    await db.flush()
    await db.refresh(setting)

    # 同步 chat_idle_timeout_minutes
    timeout_minutes = cfg.get("session", {}).get("idle_timeout_minutes")
    if isinstance(timeout_minutes, int) and timeout_minutes > 0:
        ts_res = await db.execute(
            select(AppSetting).where(AppSetting.key == CHAT_IDLE_TIMEOUT_KEY)
        )
        ts = ts_res.scalar_one_or_none()
        if not ts:
            db.add(
                AppSetting(
                    key=CHAT_IDLE_TIMEOUT_KEY,
                    value=str(timeout_minutes),
                    description="空闲超时分钟数（聚合自 ai_home_config.session）",
                )
            )
        else:
            ts.value = str(timeout_minutes)
        await db.flush()
    return setting


def _normalize_recommended(items: Any) -> Any:
    """为 recommended_questions 自动生成缺失的 id。"""
    if not isinstance(items, list):
        return items
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if not it.get("id"):
            it["id"] = uuid.uuid4().hex
        out.append(it)
    return out


def _summarize(module: str, before: Dict[str, Any], after: Dict[str, Any]) -> str:
    if module == "all":
        return "整体保存 AI 对话首页配置"
    return f"修改了 {module} 模块"


def _diff_changed(before: Any, after: Any) -> bool:
    return json.dumps(before, ensure_ascii=False, sort_keys=True, default=str) != json.dumps(
        after, ensure_ascii=False, sort_keys=True, default=str
    )


async def _write_log(
    db: AsyncSession,
    operator: Any,
    module: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
    request: Request,
):
    if not _diff_changed(before, after):
        return None
    operator_id = getattr(operator, "id", None) if operator else None
    operator_name = (
        getattr(operator, "nickname", None)
        or getattr(operator, "username", None)
        or getattr(operator, "phone", None)
        or "admin"
    )
    ip = request.client.host if request and request.client else None
    log = AIHomeConfigLog(
        operator_id=operator_id,
        operator_name=str(operator_name)[:64],
        module=module,
        summary=_summarize(module, before, after),
        before_json=before,
        after_json=after,
        operator_ip=ip[:64] if ip else None,
    )
    db.add(log)
    await db.flush()
    return log


def _validate_floating_target_path(target_path: Any):
    if not isinstance(target_path, str) or not target_path.startswith("/"):
        raise HTTPException(status_code=400, detail="floating_button.target_path 必须是以 / 开头的项目内路径")


def _validate_idle_timeout(minutes: Any):
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="idle_timeout_minutes 必须为正整数")
    if m <= 0 or m > 24 * 60:
        raise HTTPException(status_code=400, detail="idle_timeout_minutes 取值范围 1~1440")


def _validate_payload(cfg: Dict[str, Any]):
    fb = cfg.get("floating_button") or {}
    if fb.get("enabled"):
        _validate_floating_target_path(fb.get("target_path"))
    sess = cfg.get("session") or {}
    if "idle_timeout_minutes" in sess:
        _validate_idle_timeout(sess["idle_timeout_minutes"])
    grids = cfg.get("func_grid") or {}
    if grids.get("columns") not in (2, 3, 4, None):
        raise HTTPException(status_code=400, detail="func_grid.columns 仅支持 2/3/4")
    welcome = cfg.get("welcome") or {}
    greetings = welcome.get("greetings") or {}
    for k in ("morning", "afternoon", "evening"):
        arr = greetings.get(k, [])
        if not isinstance(arr, list) or len(arr) < 1:
            raise HTTPException(status_code=400, detail=f"welcome.greetings.{k} 至少 1 条")
        if len(arr) > 20:
            raise HTTPException(status_code=400, detail=f"welcome.greetings.{k} 不超过 20 条")
    if not welcome.get("subtitles") or len(welcome.get("subtitles", [])) < 1:
        raise HTTPException(status_code=400, detail="welcome.subtitles 至少 1 条")
    rqs = cfg.get("recommended_questions") or []
    if len(rqs) > 20:
        raise HTTPException(status_code=400, detail="recommended_questions 最多 20 条")


# ──────────────── 接口：用户端读取（公开） ────────────────


@router.get("/api/ai-home-config", response_model=AIHomeConfigResponse)
async def get_public_config(db: AsyncSession = Depends(get_db)):
    cfg = await _load_config(db)
    setting = (
        await db.execute(select(AppSetting).where(AppSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    return AIHomeConfigResponse(
        config=AIHomeConfigPayload(**cfg),
        updated_at=setting.updated_at if setting else None,
    )


# ──────────────── 接口：admin 读取 ────────────────


@router.get("/api/admin/ai-home-config", response_model=AIHomeConfigResponse)
async def admin_get_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _load_config(db)
    setting = (
        await db.execute(select(AppSetting).where(AppSetting.key == CONFIG_KEY))
    ).scalar_one_or_none()
    return AIHomeConfigResponse(
        config=AIHomeConfigPayload(**cfg),
        updated_at=setting.updated_at if setting else None,
    )


# ──────────────── 接口：admin 整体保存 ────────────────


@router.put("/api/admin/ai-home-config", response_model=AIHomeConfigResponse)
async def admin_put_config(
    payload: AIHomeConfigPayload,
    request: Request,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    new_cfg = payload.model_dump()
    new_cfg["recommended_questions"] = _normalize_recommended(new_cfg.get("recommended_questions"))
    _validate_payload(new_cfg)

    before = await _load_config(db)
    setting = await _save_config(db, new_cfg)
    after = await _load_config(db)
    await _write_log(db, current_user, "all", before, after, request)
    await db.commit()
    return AIHomeConfigResponse(
        config=AIHomeConfigPayload(**after),
        updated_at=setting.updated_at,
    )


# ──────────────── 接口：admin 按模块保存 ────────────────


@router.patch(
    "/api/admin/ai-home-config/{module}", response_model=AIHomeConfigResponse
)
async def admin_patch_module(
    module: str,
    patch: AIHomeModulePatch,
    request: Request,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if module not in VALID_MODULES or module == "all":
        raise HTTPException(status_code=400, detail=f"无效模块名：{module}")

    before = await _load_config(db)
    new_cfg = json.loads(json.dumps(before, default=str))  # deep copy
    if module == "recommended_questions":
        new_cfg[module] = _normalize_recommended(patch.data)
    else:
        # 用 schema 中该模块的默认形态合并
        default_full = AIHomeConfigPayload().model_dump()
        if isinstance(patch.data, dict):
            base = new_cfg.get(module) if isinstance(new_cfg.get(module), dict) else default_full[module]
            base.update(patch.data)
            new_cfg[module] = base
        else:
            new_cfg[module] = patch.data

    # 重新经过 schema 校验填充默认值
    new_cfg = AIHomeConfigPayload(**new_cfg).model_dump()
    new_cfg["recommended_questions"] = _normalize_recommended(new_cfg.get("recommended_questions"))
    _validate_payload(new_cfg)

    setting = await _save_config(db, new_cfg)
    after = await _load_config(db)
    await _write_log(db, current_user, module, before, after, request)
    await db.commit()
    return AIHomeConfigResponse(
        config=AIHomeConfigPayload(**after),
        updated_at=setting.updated_at,
    )


# ──────────────── 接口：上传头像/Logo 图片 ────────────────


_ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


@router.post("/api/admin/ai-home-config/upload-image")
async def admin_upload_image(
    file: UploadFile = File(...),
    current_user=Depends(admin_dep),
):
    if (file.content_type or "").lower() not in _ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=400, detail="仅支持 PNG/JPG/WebP 格式")
    content = await file.read()
    if len(content) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 1MB")
    if len(content) < 8:
        raise HTTPException(status_code=400, detail="图片内容为空")
    # 校验文件头
    head = content[:12]
    is_png = head.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpg = head.startswith(b"\xff\xd8\xff")
    is_webp = head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if not (is_png or is_jpg or is_webp):
        raise HTTPException(status_code=400, detail="文件内容与扩展名不匹配")

    upload_dir = os.path.join("uploads", "ai_home_config")
    os.makedirs(upload_dir, exist_ok=True)
    ext = ".png" if is_png else (".jpg" if is_jpg else ".webp")
    name = f"aih_{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(upload_dir, name)
    with open(fpath, "wb") as f:
        f.write(content)
    url = f"/uploads/ai_home_config/{name}"
    return {"url": url, "size": len(content)}


# ──────────────── 接口：操作日志 ────────────────


@router.get("/api/admin/ai-home-config/logs", response_model=AIHomeConfigLogList)
async def admin_list_logs(
    start_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    operator_id: Optional[int] = Query(default=None),
    module: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 90 天保留：自动清理超过 90 天数据
    cutoff = datetime.utcnow() - timedelta(days=90)
    try:
        old_q = select(AIHomeConfigLog).where(AIHomeConfigLog.created_at < cutoff)
        old_logs = (await db.execute(old_q)).scalars().all()
        for ol in old_logs:
            await db.delete(ol)
        await db.flush()
    except Exception as e:  # noqa: BLE001
        logger.debug("清理 90 天前日志跳过：%s", e)

    q = select(AIHomeConfigLog)
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            q = q.where(AIHomeConfigLog.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            q = q.where(AIHomeConfigLog.created_at < ed)
        except ValueError:
            pass
    if operator_id:
        q = q.where(AIHomeConfigLog.operator_id == operator_id)
    if module and module != "all":
        q = q.where(AIHomeConfigLog.module == module)

    # 总数
    from sqlalchemy import func as _func

    total_q = select(_func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    rows = (
        (
            await db.execute(
                q.order_by(desc(AIHomeConfigLog.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    items = [AIHomeConfigLogItem.model_validate(r) for r in rows]
    return AIHomeConfigLogList(items=items, total=int(total))


@router.get(
    "/api/admin/ai-home-config/logs/{log_id}", response_model=AIHomeConfigLogDetail
)
async def admin_get_log(
    log_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(AIHomeConfigLog).where(AIHomeConfigLog.id == log_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="日志不存在")
    return AIHomeConfigLogDetail(
        id=row.id,
        operator_id=row.operator_id,
        operator_name=row.operator_name,
        module=row.module,
        summary=row.summary,
        operator_ip=row.operator_ip,
        created_at=row.created_at,
        before_json=row.before_json,
        after_json=row.after_json,
    )
