import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    AIModelConfig,
    OcrCallRecord,
    OcrCallStatistics,
    OcrProviderConfig,
    OcrSceneTemplate,
    OcrUploadConfig,
)
from app.schemas.ocr import (
    OcrBatchRecognizeResponse,
    OcrCallRecordListResponse,
    OcrCallRecordResponse,
    OcrProviderConfigResponse,
    OcrProviderConfigUpdate,
    OcrProviderStatItem,
    OcrRecognizeResponse,
    OcrSceneTemplateCreate,
    OcrSceneTemplateResponse,
    OcrSceneTemplateUpdate,
    OcrStatisticsResponse,
    OcrTestFullResponse,
    OcrTestResponse,
    OcrUploadConfigResponse,
    OcrUploadConfigUpdate,
)
from app.services.ai_service import call_ai_model
from app.services.ocr_service import (
    check_image_quality,
    ocr_recognize_with_provider,
    smart_ocr_recognize,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["OCR"])
admin_router = APIRouter(prefix="/api/admin/ocr", tags=["OCR Admin"])


def _build_status_label(provider: OcrProviderConfig) -> str:
    if not provider.is_enabled:
        return "未启用"
    if provider.is_preferred:
        return "首选"
    return "已启用"


# ──────────────── Admin: Provider Config ────────────────


@admin_router.get("/providers", response_model=List[OcrProviderConfigResponse])
async def get_providers(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(OcrProviderConfig).order_by(OcrProviderConfig.id)
    )
    providers = result.scalars().all()
    items = []
    for p in providers:
        data = OcrProviderConfigResponse.model_validate(p)
        data.status_label = _build_status_label(p)
        items.append(data)
    return items


@admin_router.put("/providers/{provider}", response_model=OcrProviderConfigResponse)
async def update_provider(
    provider: str,
    body: OcrProviderConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(OcrProviderConfig).where(OcrProviderConfig.provider_name == provider)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="厂商配置不存在")

    if body.config_json is not None:
        cfg.config_json = body.config_json
    if body.is_enabled is not None:
        cfg.is_enabled = body.is_enabled

    await db.flush()
    resp = OcrProviderConfigResponse.model_validate(cfg)
    resp.status_label = _build_status_label(cfg)
    return resp


@admin_router.post("/providers/{provider}/preferred", response_model=OcrProviderConfigResponse)
async def set_preferred(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(select(OcrProviderConfig))
    all_providers = result.scalars().all()
    target = None
    for p in all_providers:
        if p.provider_name == provider:
            target = p
            p.is_preferred = True
        else:
            p.is_preferred = False

    if not target:
        raise HTTPException(status_code=404, detail="厂商配置不存在")

    await db.flush()
    resp = OcrProviderConfigResponse.model_validate(target)
    resp.status_label = _build_status_label(target)
    return resp


@admin_router.post("/providers/{provider}/disable", response_model=OcrProviderConfigResponse)
async def disable_provider(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(OcrProviderConfig).where(OcrProviderConfig.provider_name == provider)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="厂商配置不存在")

    cfg.is_enabled = False
    cfg.is_preferred = False
    await db.flush()
    resp = OcrProviderConfigResponse.model_validate(cfg)
    resp.status_label = _build_status_label(cfg)
    return resp


# ──────────────── Admin: Statistics ────────────────


@admin_router.get("/statistics", response_model=OcrStatisticsResponse)
async def get_statistics(
    period: str = Query("today", regex="^(today|7d|30d|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    query = select(
        OcrCallStatistics.provider_name,
        func.sum(OcrCallStatistics.total_calls).label("total_calls"),
        func.sum(OcrCallStatistics.success_calls).label("success_calls"),
    )

    if period == "today":
        query = query.where(OcrCallStatistics.call_date == date.today())
    elif period == "7d":
        query = query.where(OcrCallStatistics.call_date >= date.today() - timedelta(days=7))
    elif period == "30d":
        query = query.where(OcrCallStatistics.call_date >= date.today() - timedelta(days=30))

    query = query.group_by(OcrCallStatistics.provider_name)
    result = await db.execute(query)
    rows = result.all()

    providers = []
    total_calls = 0
    total_success = 0
    for row in rows:
        tc = int(row.total_calls or 0)
        sc = int(row.success_calls or 0)
        fc = tc - sc
        rate = round(sc / tc * 100, 2) if tc > 0 else 0.0
        providers.append(OcrProviderStatItem(
            provider_name=row.provider_name,
            total_calls=tc,
            success_calls=sc,
            fail_calls=fc,
            success_rate=rate,
        ))
        total_calls += tc
        total_success += sc

    return OcrStatisticsResponse(
        period=period,
        providers=providers,
        total_calls=total_calls,
        total_success=total_success,
    )


# ──────────────── Admin: Scene Templates ────────────────


@admin_router.get("/scenes", response_model=List[OcrSceneTemplateResponse])
async def list_scenes(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(OcrSceneTemplate).order_by(OcrSceneTemplate.id)
    )
    return [OcrSceneTemplateResponse.model_validate(s) for s in result.scalars().all()]


@admin_router.post("/scenes", response_model=OcrSceneTemplateResponse)
async def create_scene(
    body: OcrSceneTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    existing = await db.execute(
        select(OcrSceneTemplate).where(OcrSceneTemplate.scene_name == body.scene_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="场景名称已存在")

    scene = OcrSceneTemplate(
        scene_name=body.scene_name,
        prompt_content=body.prompt_content,
        ai_model_id=body.ai_model_id,
        ocr_provider=body.ocr_provider,
        is_preset=False,
    )
    db.add(scene)
    await db.flush()
    await db.refresh(scene)
    return OcrSceneTemplateResponse.model_validate(scene)


@admin_router.put("/scenes/{scene_id}", response_model=OcrSceneTemplateResponse)
async def update_scene(
    scene_id: int,
    body: OcrSceneTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(OcrSceneTemplate).where(OcrSceneTemplate.id == scene_id)
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    if body.scene_name is not None:
        dup = await db.execute(
            select(OcrSceneTemplate).where(
                OcrSceneTemplate.scene_name == body.scene_name,
                OcrSceneTemplate.id != scene_id,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="场景名称已存在")
        scene.scene_name = body.scene_name
    if body.prompt_content is not None:
        scene.prompt_content = body.prompt_content
    if body.ai_model_id is not None:
        scene.ai_model_id = body.ai_model_id
    if body.ocr_provider is not None:
        scene.ocr_provider = body.ocr_provider

    await db.flush()
    await db.refresh(scene)
    return OcrSceneTemplateResponse.model_validate(scene)


@admin_router.delete("/scenes/{scene_id}")
async def delete_scene(
    scene_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(OcrSceneTemplate).where(OcrSceneTemplate.id == scene_id)
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    if scene.is_preset:
        raise HTTPException(status_code=400, detail="预设场景不可删除")

    await db.delete(scene)
    await db.flush()
    return {"detail": "删除成功"}


# ──────────────── Admin: Upload Limits ────────────────


@admin_router.get("/upload-limits", response_model=OcrUploadConfigResponse)
async def get_upload_limits(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(select(OcrUploadConfig).limit(1))
    cfg = result.scalar_one_or_none()
    if not cfg:
        cfg = OcrUploadConfig(max_batch_count=5, max_file_size_mb=5)
        db.add(cfg)
        await db.flush()
        await db.refresh(cfg)
    return OcrUploadConfigResponse.model_validate(cfg)


@admin_router.put("/upload-limits", response_model=OcrUploadConfigResponse)
async def update_upload_limits(
    body: OcrUploadConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(select(OcrUploadConfig).limit(1))
    cfg = result.scalar_one_or_none()
    if not cfg:
        cfg = OcrUploadConfig()
        db.add(cfg)
        await db.flush()

    if body.max_batch_count is not None:
        cfg.max_batch_count = body.max_batch_count
    if body.max_file_size_mb is not None:
        cfg.max_file_size_mb = body.max_file_size_mb
    await db.flush()
    await db.refresh(cfg)
    return OcrUploadConfigResponse.model_validate(cfg)


# ──────────────── Admin: Test OCR ────────────────


@admin_router.post("/test-ocr", response_model=OcrTestResponse)
async def test_ocr(
    file: UploadFile = File(...),
    provider: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    image_data = await file.read()
    quality = check_image_quality(image_data)
    if not quality["ok"]:
        return OcrTestResponse(success=False, provider_name=provider, error=quality["message"])

    result = await db.execute(
        select(OcrProviderConfig).where(OcrProviderConfig.provider_name == provider)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        return OcrTestResponse(success=False, provider_name=provider, error="厂商配置不存在")

    try:
        text = await ocr_recognize_with_provider(image_data, provider, cfg.config_json or {})
        return OcrTestResponse(success=True, provider_name=provider, ocr_text=text)
    except Exception as e:
        logger.warning("Test OCR failed for %s: %s", provider, e)
        return OcrTestResponse(success=False, provider_name=provider, error=str(e))


@admin_router.post("/test-full", response_model=OcrTestFullResponse)
async def test_full(
    file: UploadFile = File(...),
    provider: str = Form(...),
    scene_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    image_data = await file.read()
    quality = check_image_quality(image_data)
    if not quality["ok"]:
        return OcrTestFullResponse(success=False, provider_name=provider, error=quality["message"])

    result = await db.execute(
        select(OcrProviderConfig).where(OcrProviderConfig.provider_name == provider)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        return OcrTestFullResponse(success=False, provider_name=provider, error="厂商配置不存在")

    try:
        ocr_text = await ocr_recognize_with_provider(image_data, provider, cfg.config_json or {})
    except Exception as e:
        return OcrTestFullResponse(success=False, provider_name=provider, error=f"OCR失败: {e}")

    result = await db.execute(
        select(OcrSceneTemplate).where(OcrSceneTemplate.id == scene_id)
    )
    scene = result.scalar_one_or_none()
    if not scene:
        return OcrTestFullResponse(
            success=True, provider_name=provider, ocr_text=ocr_text,
            error="场景模板不存在，仅返回OCR结果",
        )

    try:
        ai_result = await _call_ai_with_scene(ocr_text, scene, db)
        return OcrTestFullResponse(
            success=True, provider_name=provider, ocr_text=ocr_text, ai_result=ai_result,
        )
    except Exception as e:
        return OcrTestFullResponse(
            success=True, provider_name=provider, ocr_text=ocr_text,
            error=f"AI处理失败: {e}",
        )


# ──────────────── Admin: Records ────────────────


@admin_router.get("/records", response_model=OcrCallRecordListResponse)
async def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider_name: Optional[str] = None,
    status: Optional[str] = None,
    scene_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    query = select(OcrCallRecord)
    count_query = select(func.count(OcrCallRecord.id))

    if provider_name:
        query = query.where(OcrCallRecord.provider_name == provider_name)
        count_query = count_query.where(OcrCallRecord.provider_name == provider_name)
    if status:
        query = query.where(OcrCallRecord.status == status)
        count_query = count_query.where(OcrCallRecord.status == status)
    if scene_name:
        query = query.where(OcrCallRecord.scene_name == scene_name)
        count_query = count_query.where(OcrCallRecord.scene_name == scene_name)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(OcrCallRecord.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [OcrCallRecordResponse.model_validate(r) for r in result.scalars().all()]

    return OcrCallRecordListResponse(items=items, total=total, page=page, page_size=page_size)


@admin_router.post("/records/batch-delete")
async def batch_delete_records(
    ids: List[int],
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的记录ID")
    await db.execute(delete(OcrCallRecord).where(OcrCallRecord.id.in_(ids)))
    await db.flush()
    return {"detail": f"已删除 {len(ids)} 条记录"}


# ──────────────── Business: Recognize ────────────────


@router.post("/recognize", response_model=OcrRecognizeResponse)
async def recognize(
    file: UploadFile = File(...),
    scene_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    image_data = await file.read()
    quality = check_image_quality(image_data)
    if not quality["ok"]:
        return OcrRecognizeResponse(success=False, error=quality["message"])

    scene = None
    preferred_provider = None
    if scene_name:
        result = await db.execute(
            select(OcrSceneTemplate).where(OcrSceneTemplate.scene_name == scene_name)
        )
        scene = result.scalar_one_or_none()
        if scene and scene.ocr_provider:
            preferred_provider = scene.ocr_provider

    try:
        ocr_text, provider_used = await smart_ocr_recognize(image_data, db, preferred_provider)
    except Exception as e:
        record = OcrCallRecord(
            scene_name=scene_name,
            provider_name="unknown",
            status="failed",
            error_message=str(e),
        )
        db.add(record)
        await db.flush()
        return OcrRecognizeResponse(success=False, error=str(e), record_id=record.id)

    ai_result = None
    if scene and scene.prompt_content:
        try:
            ai_result = await _call_ai_with_scene(ocr_text, scene, db)
        except Exception as e:
            logger.warning("AI processing failed: %s", e)
            ai_result = {"error": str(e), "raw_text": ocr_text}

    record = OcrCallRecord(
        scene_name=scene_name,
        provider_name=provider_used,
        status="success",
        ocr_raw_text=ocr_text,
        ai_structured_result=ai_result,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    return OcrRecognizeResponse(
        success=True,
        provider_name=provider_used,
        ocr_text=ocr_text,
        ai_result=ai_result,
        record_id=record.id,
    )


@router.post("/batch-recognize", response_model=OcrBatchRecognizeResponse)
async def batch_recognize(
    files: List[UploadFile] = File(...),
    scene_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    upload_cfg_result = await db.execute(select(OcrUploadConfig).limit(1))
    upload_cfg = upload_cfg_result.scalar_one_or_none()
    max_batch = upload_cfg.max_batch_count if upload_cfg else 5
    max_size_mb = upload_cfg.max_file_size_mb if upload_cfg else 5

    if len(files) > max_batch:
        raise HTTPException(status_code=400, detail=f"批量上传不能超过{max_batch}张")

    results = []
    success_count = 0
    fail_count = 0

    scene = None
    preferred_provider = None
    if scene_name:
        result = await db.execute(
            select(OcrSceneTemplate).where(OcrSceneTemplate.scene_name == scene_name)
        )
        scene = result.scalar_one_or_none()
        if scene and scene.ocr_provider:
            preferred_provider = scene.ocr_provider

    for f in files:
        image_data = await f.read()
        if len(image_data) > max_size_mb * 1024 * 1024:
            results.append(OcrRecognizeResponse(
                success=False, error=f"文件大小超过{max_size_mb}MB限制",
            ))
            fail_count += 1
            continue

        quality = check_image_quality(image_data)
        if not quality["ok"]:
            results.append(OcrRecognizeResponse(success=False, error=quality["message"]))
            fail_count += 1
            continue

        try:
            ocr_text, provider_used = await smart_ocr_recognize(image_data, db, preferred_provider)
        except Exception as e:
            record = OcrCallRecord(
                scene_name=scene_name, provider_name="unknown",
                status="failed", error_message=str(e),
            )
            db.add(record)
            await db.flush()
            results.append(OcrRecognizeResponse(
                success=False, error=str(e), record_id=record.id,
            ))
            fail_count += 1
            continue

        ai_result = None
        if scene and scene.prompt_content:
            try:
                ai_result = await _call_ai_with_scene(ocr_text, scene, db)
            except Exception as e:
                ai_result = {"error": str(e), "raw_text": ocr_text}

        record = OcrCallRecord(
            scene_name=scene_name, provider_name=provider_used,
            status="success", ocr_raw_text=ocr_text, ai_structured_result=ai_result,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)

        results.append(OcrRecognizeResponse(
            success=True, provider_name=provider_used,
            ocr_text=ocr_text, ai_result=ai_result, record_id=record.id,
        ))
        success_count += 1

    return OcrBatchRecognizeResponse(
        results=results, total=len(files),
        success_count=success_count, fail_count=fail_count,
    )


# ──────────────── Helpers ────────────────


async def _call_ai_with_scene(
    ocr_text: str,
    scene: OcrSceneTemplate,
    db: AsyncSession,
) -> dict:
    system_prompt = scene.prompt_content or "请根据以下OCR文字内容进行结构化整理，返回JSON格式。"
    messages = [{"role": "user", "content": f"以下是OCR识别的文字内容:\n\n{ocr_text}"}]

    result = await call_ai_model(messages, system_prompt, db)

    if isinstance(result, dict):
        return result

    try:
        text = result.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:] if lines else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"raw_result": result}
