"""[BUG_FIX_用药识别千图一答 2026-05-16] 用药识别接口（视觉模型 + OCR + 药品库三重识别）

历史问题：旧版 /api/drugs/identify 把 image_url 当字符串拼进 prompt 给纯文本大模型，
模型"看不见"图片只看到一段网址，于是凭印象编出一个常见药品，导致"千图一答"。

本次修复彻底重构：
- /api/drugs/identify（旧）：保持接口契约，但内部走真正的视觉模型链路
- /api/drugs/identify-v2（新）：支持多图、结构化输出，并自动创建用药咨询 ChatSession 供后续追问
"""
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    AllergyRecord,
    ChatMessage,
    ChatSession,
    DrugIdentifyDetail,
    HealthProfile,
    MedicationRecord,
    MessageRole,
    OcrCallRecord,
    SessionType,
    User,
)
from app.services.ai_service import (
    drug_interaction_check,
    drug_query,
    identify_drug_from_image,
    identify_drug_structured,
)
from app.services.ocr_service import check_image_quality, smart_ocr_recognize
from app.utils.cos_helper import try_cos_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drugs", tags=["药品"])


@router.get("/search")
async def search_drug(
    name: str = Query(..., description="药品名称"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allergy_result = await db.execute(select(AllergyRecord).where(AllergyRecord.user_id == current_user.id))
    allergies = [a.allergy_name for a in allergy_result.scalars().all()]

    med_result = await db.execute(
        select(MedicationRecord).where(MedicationRecord.user_id == current_user.id, MedicationRecord.status == "active")
    )
    medications = [m.medicine_name for m in med_result.scalars().all()]

    user_profile = {"allergies": allergies, "medications": medications}

    result = await drug_query(name, user_profile, db)
    return {"drug_name": name, "analysis": result}


@router.post("/interaction-check")
async def check_interaction(
    drugs: List[str] = Query(..., description="药品列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(drugs) < 2:
        return {"message": "请提供至少两种药品进行相互作用检查", "result": ""}

    result = await drug_interaction_check(drugs, db)
    return {"drugs": drugs, "analysis": result}


async def _upload_and_get_url(
    db: AsyncSession,
    content: bytes,
    filename: Optional[str],
    content_type: Optional[str],
) -> str:
    """统一的图片上传：优先 COS，失败则落本地 uploads 目录。"""
    cos_url = await try_cos_upload(
        db,
        content,
        filename or "drug.jpg",
        content_type,
        "drugs/",
    )
    if cos_url:
        return cos_url
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(filename or "drug.jpg")[1] or ".jpg"
    saved_name = f"drug_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, saved_name)
    with open(filepath, "wb") as f:
        f.write(content)
    return f"/uploads/{saved_name}"


@router.post("/identify")
async def identify_drug(
    file: UploadFile = File(...),
    family_member_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUG_FIX_用药识别千图一答 2026-05-16] 修复版：走真正的视觉模型 + OCR 链路。

    旧版只把"文件名"和"大小"当成图片描述喂给纯文本模型，根本看不到图片，
    所以无论传什么图都返回相同药品。修复后：
    1. 同步把图片上传到云存储拿到 URL；
    2. 调用 OCR 提取药盒上的真实文字；
    3. 把图片 URL（多模态）+ OCR 文字一起发给视觉大模型做识别；
    4. 输出结果绑定真实图片内容，不再"千图一答"。
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片为空")

    image_url = await _upload_and_get_url(db, content, file.filename, file.content_type)

    # OCR 提取药盒文字（任一可用 OCR 厂商）
    ocr_text = ""
    try:
        quality = check_image_quality(content)
        if quality.get("ok", True):
            ocr_text, _provider = await smart_ocr_recognize(content, db, None)
    except Exception as e:
        logger.warning("identify_drug OCR failed (will fallback to vision only): %s", e)
        ocr_text = ""

    # 真正的视觉模型识别
    analysis = await identify_drug_from_image(
        image_description="用户在 AI 对话首页通过拍照识药入口上传了一张药盒图，请基于图片真实视觉内容识别药品。",
        db=db,
        image_urls=[image_url],
        ocr_text=ocr_text or None,
    )

    return {
        "image_url": image_url,
        "ocr_text": ocr_text,
        "analysis": analysis,
    }


@router.post("/identify-v2")
async def identify_drug_v2(
    files: List[UploadFile] = File(..., description="药盒图片（支持 1~3 张）"),
    family_member_id: Optional[int] = Form(None),
    create_session: bool = Form(True, description="识别成功是否自动建一个 ChatSession 供后续追问"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUG_FIX_用药识别千图一答 2026-05-16] 用药识别 v2：

    - 支持一次最多 3 张图（同图多药 / 多图同药 / 多图多药均可）；
    - 输出严格的结构化 JSON：``{recognized, confidence, medicines, raw_ocr_text, next_action, summary_markdown}``；
    - 识别成功后自动写入 ``drug_identify_detail`` 与 ``ocr_call_record``，并按需建一个
      ``drug_query`` 类型的 ChatSession，让用户在 AI 对话里直接针对识别结果追问；
    - 识别失败时返回 ``next_action='retake'`` 引导用户重拍，绝不胡编。
    """
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少 1 张药盒图")
    if len(files) > 3:
        files = files[:3]

    image_urls: List[str] = []
    ocr_texts: List[str] = []
    last_provider = "unknown"
    for f in files:
        data = await f.read()
        if not data:
            continue
        url = await _upload_and_get_url(db, data, f.filename, f.content_type)
        image_urls.append(url)
        try:
            quality = check_image_quality(data)
            if not quality.get("ok", True):
                continue
            text, provider = await smart_ocr_recognize(data, db, None)
            if text:
                ocr_texts.append(text)
                last_provider = provider or last_provider
        except Exception as e:
            logger.warning("identify_drug_v2 OCR fail (continue, vision will handle): %s", e)
            continue

    if not image_urls:
        raise HTTPException(status_code=400, detail="所有图片内容均为空，无法识别")

    merged_ocr = "\n\n---\n\n".join(ocr_texts) if ocr_texts else ""

    # 用户健康档案（仅用于 LLM 个性化提醒，不影响识别本身）
    user_profile: Dict[str, Any] = {}
    try:
        hp_result = await db.execute(
            select(HealthProfile).where(HealthProfile.user_id == current_user.id)
        )
        hp = hp_result.scalar_one_or_none()
        if hp:
            user_profile["gender"] = hp.gender
        alg_result = await db.execute(
            select(AllergyRecord).where(AllergyRecord.user_id == current_user.id)
        )
        user_profile["allergies"] = [a.allergy_name for a in alg_result.scalars().all()]
        med_result = await db.execute(
            select(MedicationRecord).where(
                MedicationRecord.user_id == current_user.id,
                MedicationRecord.status == "active",
            )
        )
        user_profile["medications"] = [m.medicine_name for m in med_result.scalars().all()]
    except Exception:
        user_profile = {}

    structured = await identify_drug_structured(
        image_urls=image_urls,
        ocr_text=merged_ocr or None,
        user_profile=user_profile or None,
        db=db,
    )

    # 写 OCR 调用流水
    record = OcrCallRecord(
        scene_name="拍照识药",
        provider_name=last_provider,
        status="success" if structured.get("recognized") else "failed",
        ocr_raw_text=merged_ocr,
        ai_structured_result=structured,
        original_image_url=image_urls[0] if image_urls else None,
        image_count=len(image_urls),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    session_id: Optional[int] = None
    primary_drug_name: Optional[str] = None
    medicines = structured.get("medicines") or []
    if medicines and isinstance(medicines, list) and isinstance(medicines[0], dict):
        primary_drug_name = (
            medicines[0].get("name")
            or medicines[0].get("brand")
            or "用药识别"
        )

    # 落 DrugIdentifyDetail
    detail = DrugIdentifyDetail(
        user_id=current_user.id,
        user_phone=getattr(current_user, "phone", None),
        user_nickname=getattr(current_user, "nickname", None),
        drug_name=primary_drug_name,
        drug_category=medicines[0].get("category") if medicines else None,
        dosage=medicines[0].get("usage") if medicines else None,
        precautions=medicines[0].get("precautions") if medicines else None,
        provider_name=last_provider,
        original_image_url=image_urls[0],
        ocr_raw_text=merged_ocr,
        ai_structured_result=structured,
        ocr_call_record_id=record.id,
        family_member_id=family_member_id,
        status="success" if structured.get("recognized") else "failed",
    )
    db.add(detail)
    await db.flush()
    await db.refresh(detail)

    # 建立可继续追问的 ChatSession
    if create_session and structured.get("recognized"):
        session = ChatSession(
            user_id=current_user.id,
            session_type=SessionType.drug_query,
            title=primary_drug_name or "拍照识药",
            family_member_id=family_member_id,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        session_id = session.id
        # 关联 detail 到 session（便于 drug_chat /init 拉药品列表）
        detail.session_id = session_id

        # 把识别结果以一组消息写入会话历史
        user_msg = ChatMessage(
            session_id=session_id,
            role=MessageRole.user,
            content="（拍照识药）我上传了药盒图，请识别这是什么药",
            image_urls=image_urls,
        )
        db.add(user_msg)
        ai_msg = ChatMessage(
            session_id=session_id,
            role=MessageRole.assistant,
            content=structured.get("summary_markdown") or "识别完成，请继续追问。",
            message_metadata={
                "source": "drug_identify_v2",
                "recognized": structured.get("recognized"),
                "confidence": structured.get("confidence"),
                "medicines": structured.get("medicines"),
            },
        )
        db.add(ai_msg)
        session.message_count = 2
        await db.flush()

    return {
        "session_id": session_id,
        "image_urls": image_urls,
        "ocr_text": merged_ocr,
        "record_id": record.id,
        "detail_id": detail.id,
        **structured,
    }
