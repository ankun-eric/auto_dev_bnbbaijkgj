import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import PromptTemplate, User
from app.services.ai_service import call_ai_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/prompt-templates", tags=["Prompt模板管理"])

VALID_PROMPT_TYPES = {
    "checkup_report",
    "drug_general",
    "drug_personal",
    "drug_interaction",
    "trend_analysis",
}

TYPE_DISPLAY_NAMES = {
    "checkup_report": "体检报告解读",
    "drug_general": "药物识别通用建议",
    "drug_personal": "药物识别个性化建议",
    "drug_interaction": "药物相互作用分析",
    "trend_analysis": "趋势解读",
}


class PromptTemplateResponse(BaseModel):
    id: int
    name: str
    prompt_type: str
    content: str
    version: int
    is_active: bool
    parent_id: Optional[int] = None
    preview_input: Optional[str] = None

    model_config = {"from_attributes": True}


class PromptTemplateGroupResponse(BaseModel):
    prompt_type: str
    display_name: str
    active_template: Optional[PromptTemplateResponse] = None


class PromptTemplateHistoryResponse(BaseModel):
    prompt_type: str
    display_name: str
    active: Optional[PromptTemplateResponse] = None
    history: List[PromptTemplateResponse] = []


class PromptTemplateUpdate(BaseModel):
    content: str
    name: Optional[str] = None
    preview_input: Optional[str] = None


class PromptPreviewRequest(BaseModel):
    input_text: str


class PromptPreviewResponse(BaseModel):
    prompt_type: str
    input_text: str
    ai_result: Any


class RollbackResponse(BaseModel):
    message: str
    active_version: int


@router.get("", response_model=List[PromptTemplateGroupResponse])
async def list_prompt_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.is_active == True)  # noqa: E712
    )
    active_templates = {t.prompt_type: t for t in result.scalars().all()}

    groups = []
    for pt in VALID_PROMPT_TYPES:
        tpl = active_templates.get(pt)
        groups.append(PromptTemplateGroupResponse(
            prompt_type=pt,
            display_name=TYPE_DISPLAY_NAMES.get(pt, pt),
            active_template=PromptTemplateResponse.model_validate(tpl) if tpl else None,
        ))
    return groups


@router.get("/{prompt_type}", response_model=PromptTemplateHistoryResponse)
async def get_prompt_template(
    prompt_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if prompt_type not in VALID_PROMPT_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的模板类型: {prompt_type}")

    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.prompt_type == prompt_type)
        .order_by(PromptTemplate.version.desc())
    )
    templates = result.scalars().all()

    active = None
    history = []
    for t in templates:
        resp = PromptTemplateResponse.model_validate(t)
        if t.is_active:
            active = resp
        else:
            history.append(resp)

    return PromptTemplateHistoryResponse(
        prompt_type=prompt_type,
        display_name=TYPE_DISPLAY_NAMES.get(prompt_type, prompt_type),
        active=active,
        history=history,
    )


@router.put("/{prompt_type}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    prompt_type: str,
    body: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if prompt_type not in VALID_PROMPT_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的模板类型: {prompt_type}")

    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == prompt_type,
            PromptTemplate.is_active == True,  # noqa: E712
        )
    )
    current_active = result.scalar_one_or_none()

    new_version = 1
    parent_id = None

    if current_active:
        current_active.is_active = False
        new_version = current_active.version + 1
        parent_id = current_active.id
        await db.flush()

    new_template = PromptTemplate(
        name=body.name or TYPE_DISPLAY_NAMES.get(prompt_type, prompt_type),
        prompt_type=prompt_type,
        content=body.content,
        version=new_version,
        is_active=True,
        parent_id=parent_id,
        preview_input=body.preview_input,
        created_by=current_user.id,
    )
    db.add(new_template)
    await db.flush()
    await db.refresh(new_template)

    return PromptTemplateResponse.model_validate(new_template)


@router.post("/{prompt_type}/preview", response_model=PromptPreviewResponse)
async def preview_prompt_template(
    prompt_type: str,
    body: PromptPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if prompt_type not in VALID_PROMPT_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的模板类型: {prompt_type}")

    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == prompt_type,
            PromptTemplate.is_active == True,  # noqa: E712
        )
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="该类型暂无激活模板")

    system_prompt = tpl.content
    messages = [{"role": "user", "content": f"以下是OCR识别的文字内容:\n\n{body.input_text}"}]

    try:
        raw = await call_ai_model(messages, system_prompt, db)
        if isinstance(raw, dict):
            ai_result = raw
        else:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            try:
                ai_result = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                ai_result = {"raw_result": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI调用失败: {str(e)}")

    return PromptPreviewResponse(
        prompt_type=prompt_type,
        input_text=body.input_text,
        ai_result=ai_result,
    )


@router.post("/{prompt_type}/rollback/{version}", response_model=RollbackResponse)
async def rollback_prompt_template(
    prompt_type: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if prompt_type not in VALID_PROMPT_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的模板类型: {prompt_type}")

    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == prompt_type,
            PromptTemplate.version == version,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")

    active_result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == prompt_type,
            PromptTemplate.is_active == True,  # noqa: E712
        )
    )
    current_active = active_result.scalar_one_or_none()

    if current_active and current_active.id == target.id:
        raise HTTPException(status_code=400, detail="该版本已经是当前激活版本")

    if current_active:
        current_active.is_active = False
        await db.flush()

    max_ver_result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.prompt_type == prompt_type).order_by(PromptTemplate.version.desc())
    )
    max_tpl = max_ver_result.scalars().first()
    new_version = (max_tpl.version + 1) if max_tpl else 1

    new_template = PromptTemplate(
        name=target.name,
        prompt_type=prompt_type,
        content=target.content,
        version=new_version,
        is_active=True,
        parent_id=target.id,
        preview_input=target.preview_input,
        created_by=current_user.id,
    )
    db.add(new_template)
    await db.flush()

    return RollbackResponse(
        message=f"已回滚到版本 {version} 的内容，当前版本为 {new_version}",
        active_version=new_version,
    )
