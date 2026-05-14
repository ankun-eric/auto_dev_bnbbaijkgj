import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import PromptTemplate, PromptTypeConfig, User
from app.services.ai_service import call_ai_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/prompt-templates", tags=["Prompt模板管理"])

# [PRD-PROMPT-CONFIG-V1 2026-05-14] 类型集合从 prompt_type_config 表动态读取，
# 兼容性兜底：当 DB 尚未迁移到位时，仍允许下列硬编码集合作为合法值。
_FALLBACK_VALID_PROMPT_TYPES = {
    "checkup_report",
    "drug_general",
    "drug_personal",
    "drug_interaction",
    "drug_query",
    "trend_analysis",
    "checkup_report_interpret",
    "checkup_report_compare",
    "drug_chat_opening_single",
    "drug_chat_opening_multi",
}

_FALLBACK_DISPLAY_NAMES = {
    "checkup_report": "体检报告解读（旧 · 结构化，已下线）",
    "drug_general": "药物识别通用建议",
    "drug_personal": "药物识别个性化建议",
    "drug_interaction": "药物相互作用分析",
    "drug_query": "用药咨询对话",
    "trend_analysis": "趋势解读（已下线）",
    "checkup_report_interpret": "体检报告解读（对话式）",
    "checkup_report_compare": "报告对比（对话式）",
    "drug_chat_opening_single": "用药对话首条消息（单药）",
    "drug_chat_opening_multi": "用药对话首条消息（多药）",
}


async def _load_type_configs(db: AsyncSession, include_offline: bool = False) -> list[PromptTypeConfig]:
    stmt = select(PromptTypeConfig).order_by(
        PromptTypeConfig.business_group.asc(),
        PromptTypeConfig.sort_order.asc(),
        PromptTypeConfig.id.asc(),
    )
    if not include_offline:
        stmt = stmt.where(PromptTypeConfig.is_online == True)  # noqa: E712
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def _is_valid_prompt_type(db: AsyncSession, prompt_type: str) -> bool:
    """合法即：prompt_type_config 中存在 type_key（无论上下线），或在兜底集合中。"""
    res = await db.execute(
        select(PromptTypeConfig).where(PromptTypeConfig.type_key == prompt_type)
    )
    if res.scalar_one_or_none():
        return True
    return prompt_type in _FALLBACK_VALID_PROMPT_TYPES


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
    # [PRD-PROMPT-CONFIG-V1 2026-05-14] 新增 business_group + allowed_button_types
    business_group: Optional[str] = None
    allowed_button_types: List[str] = []
    description: Optional[str] = None
    preview_input_default: Optional[str] = None
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
    include_offline: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    # [PRD-PROMPT-CONFIG-V1 2026-05-14] 从 prompt_type_config 加载 is_online=1 的类型；
    # 已下线类型默认隐藏（前端高级模式可传 include_offline=1）
    configs = await _load_type_configs(db, include_offline=bool(include_offline))

    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.is_active == True)  # noqa: E712
    )
    active_templates = {t.prompt_type: t for t in result.scalars().all()}

    groups: list[PromptTemplateGroupResponse] = []
    seen = set()
    for cfg in configs:
        seen.add(cfg.type_key)
        tpl = active_templates.get(cfg.type_key)
        groups.append(PromptTemplateGroupResponse(
            prompt_type=cfg.type_key,
            display_name=cfg.display_name,
            business_group=cfg.business_group,
            allowed_button_types=list(cfg.allowed_button_types or []),
            description=cfg.description,
            preview_input_default=cfg.preview_input_default,
            active_template=PromptTemplateResponse.model_validate(tpl) if tpl else None,
        ))

    # 兜底：当配置表为空时仍返回兜底列表，保证不会出现"下拉永远为空"
    if not configs:
        for pt in _FALLBACK_VALID_PROMPT_TYPES:
            tpl = active_templates.get(pt)
            groups.append(PromptTemplateGroupResponse(
                prompt_type=pt,
                display_name=_FALLBACK_DISPLAY_NAMES.get(pt, pt),
                business_group=None,
                allowed_button_types=[],
                active_template=PromptTemplateResponse.model_validate(tpl) if tpl else None,
            ))

    return groups


@router.get("/{prompt_type}", response_model=PromptTemplateHistoryResponse)
async def get_prompt_template(
    prompt_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if not await _is_valid_prompt_type(db, prompt_type):
        raise HTTPException(status_code=400, detail=f"无效的模板类型: {prompt_type}")

    cfg_res = await db.execute(
        select(PromptTypeConfig).where(PromptTypeConfig.type_key == prompt_type)
    )
    cfg = cfg_res.scalar_one_or_none()
    display_name = cfg.display_name if cfg else _FALLBACK_DISPLAY_NAMES.get(prompt_type, prompt_type)

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
        display_name=display_name,
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
    if not await _is_valid_prompt_type(db, prompt_type):
        raise HTTPException(status_code=400, detail=f"无效的模板类型: {prompt_type}")
    # 取展示名
    cfg_res = await db.execute(select(PromptTypeConfig).where(PromptTypeConfig.type_key == prompt_type))
    cfg = cfg_res.scalar_one_or_none()
    default_name = cfg.display_name if cfg else _FALLBACK_DISPLAY_NAMES.get(prompt_type, prompt_type)

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
        name=body.name or default_name,
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
    if not await _is_valid_prompt_type(db, prompt_type):
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
    if not await _is_valid_prompt_type(db, prompt_type):
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
