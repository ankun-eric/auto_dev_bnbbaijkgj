import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import AllergyRecord, HealthProfile, MedicationRecord, User
from app.services.ai_service import drug_interaction_check, drug_query, identify_drug_from_image
from app.utils.cos_helper import try_cos_upload

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


@router.post("/identify")
async def identify_drug(
    file: UploadFile = File(...),
    family_member_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()

    cos_url = await try_cos_upload(db, content, file.filename or "drug.jpg", file.content_type, "drugs/")
    if cos_url:
        image_url = cos_url
    else:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename or "drug.jpg")[1]
        filename = f"drug_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        image_url = f"/uploads/{filename}"

    image_desc = f"用户上传了一张药品图片，文件名: {file.filename}, 大小: {len(content)} bytes"

    result = await identify_drug_from_image(image_desc, db)

    return {
        "image_url": image_url,
        "analysis": result,
    }
