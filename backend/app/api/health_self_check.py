"""[PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查（health_self_check）功能 API。

包含三组路由：
- 公开（用户端）：
    GET  /api/health-self-check/dict           列出启用的部位字典（含症状）
    GET  /api/health-self-check/template/{id}  查询某问卷模板的详情（含部位明细）
    POST /api/health-self-check/start          提交问卷 → 触发 AI 分析（同步返回 AI 回答）
- 管理端·部位症状字典：
    GET    /api/admin/body-part-dict
    POST   /api/admin/body-part-dict
    PUT    /api/admin/body-part-dict/{id}
    DELETE /api/admin/body-part-dict/{id}
- 管理端·健康自查问卷模板：
    GET    /api/admin/health-check-templates
    POST   /api/admin/health-check-templates
    GET    /api/admin/health-check-templates/{id}
    PUT    /api/admin/health-check-templates/{id}
    DELETE /api/admin/health-check-templates/{id}
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    BodyPartDict,
    ChatFunctionButton,
    ChatMessage,
    ChatSession,
    FamilyMember,
    HealthCheckTemplate,
    MessageRole,
    SessionType,
    User,
)
from app.schemas.health_self_check import (
    BodyPartDictCreate,
    BodyPartDictResponse,
    BodyPartDictUpdate,
    HealthCheckTemplateCreate,
    HealthCheckTemplateDetail,
    HealthCheckTemplateResponse,
    HealthCheckTemplateUpdate,
    HealthSelfCheckCardPayload,
    HealthSelfCheckStartRequest,
    HealthSelfCheckStartResponse,
)
from app.services.ai_service import call_ai_model

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# 路由对象
# ════════════════════════════════════════════════════════════════

public_router = APIRouter(prefix="/api/health-self-check", tags=["健康自查-用户端"])
admin_router = APIRouter(prefix="/api/admin", tags=["健康自查-管理端"])

admin_dep = require_role("admin")


# ════════════════════════════════════════════════════════════════
# 工具：占位符替换 / 档案上下文构建
# ════════════════════════════════════════════════════════════════


def _format_prompt(template: str, vars_map: dict[str, str]) -> str:
    """把 {占位符} 替换为对应值；不存在则替换为空串，并规整多余空格。"""
    out = template or ""
    for k, v in vars_map.items():
        out = out.replace("{" + k + "}", str(v) if v is not None else "")
    return out


async def _build_archive_context(
    db: AsyncSession, user: User, archive_id: Optional[int]
) -> dict[str, str]:
    """根据 archive_id（家庭成员 ID）或 user 本身构建档案上下文。

    返回字典：name, age, gender, history, allergies, summary。
    archive_id 为 None 或 0 视为「本人」。
    """
    name = (user.nickname or user.username or user.phone or "本人")
    age: Optional[int] = None
    gender: Optional[str] = None
    history_text = "无"
    allergies_text = "无"

    fm: Optional[FamilyMember] = None
    if archive_id:
        fm = await db.get(FamilyMember, archive_id)
        if fm and fm.user_id == user.id:
            name = fm.nickname or fm.relationship_type or name
            gender = fm.gender
            if fm.birthday:
                try:
                    today = datetime.utcnow().date()
                    age = today.year - fm.birthday.year - (
                        (today.month, today.day) < (fm.birthday.month, fm.birthday.day)
                    )
                except Exception:
                    age = None
            if fm.medical_histories:
                try:
                    items = fm.medical_histories if isinstance(fm.medical_histories, list) else []
                    if items:
                        history_text = "、".join(str(x) for x in items[:10])
                except Exception:
                    pass
            if fm.allergies:
                try:
                    items = fm.allergies if isinstance(fm.allergies, list) else []
                    if items:
                        allergies_text = "、".join(str(x) for x in items[:10])
                except Exception:
                    pass

    age_str = str(age) if age is not None else "未知"
    gender_str = gender or "未知"
    summary = f"{name}，{gender_str}，{age_str}岁"
    return {
        "name": name,
        "age": age_str,
        "gender": gender_str,
        "history": history_text,
        "allergies": allergies_text,
        "summary": summary,
    }


# ════════════════════════════════════════════════════════════════
# 公开端点：用户端
# ════════════════════════════════════════════════════════════════


@public_router.get("/dict", response_model=list[BodyPartDictResponse])
async def list_enabled_body_parts(db: AsyncSession = Depends(get_db)):
    """返回所有启用的部位字典，按 sort_order 升序。"""
    result = await db.execute(
        select(BodyPartDict)
        .where(BodyPartDict.enabled == True)  # noqa: E712
        .order_by(BodyPartDict.sort_order.asc(), BodyPartDict.id.asc())
    )
    items = []
    for b in result.scalars().all():
        items.append(BodyPartDictResponse(
            id=b.id,
            name=b.name,
            icon=b.icon,
            symptoms=list(b.symptoms or []),
            sort_order=b.sort_order or 100,
            enabled=bool(b.enabled),
            symptom_count=len(list(b.symptoms or [])),
            created_at=b.created_at,
            updated_at=b.updated_at,
        ))
    return items


@public_router.get("/template/{tpl_id}", response_model=HealthCheckTemplateDetail)
async def get_template_detail(tpl_id: int, db: AsyncSession = Depends(get_db)):
    tpl = await db.get(HealthCheckTemplate, tpl_id)
    if not tpl or not tpl.enabled:
        raise HTTPException(status_code=404, detail="问卷模板不存在或已停用")
    detail = HealthCheckTemplateDetail(
        id=tpl.id, name=tpl.name, description=tpl.description,
        body_parts=list(tpl.body_parts or []),
        duration_options=list(tpl.duration_options or []),
        default_prompt=tpl.default_prompt,
        enabled=bool(tpl.enabled),
        created_at=tpl.created_at, updated_at=tpl.updated_at,
    )
    # 装载部位明细
    part_ids = [int(p.get("id")) for p in (tpl.body_parts or []) if p.get("id") is not None]
    if part_ids:
        r = await db.execute(
            select(BodyPartDict).where(BodyPartDict.id.in_(part_ids))
        )
        id_to_part = {b.id: b for b in r.scalars().all()}
        ordered = []
        for ref in (tpl.body_parts or []):
            pid = int(ref.get("id"))
            b = id_to_part.get(pid)
            if not b or not b.enabled:
                continue
            ordered.append({
                "id": b.id,
                "name": b.name,
                "icon": b.icon,
                "symptoms": list(b.symptoms or []),
                "sort": ref.get("sort", 0),
            })
        detail.body_parts_detail = ordered
    return detail


@public_router.post("/start", response_model=HealthSelfCheckStartResponse)
async def start_health_self_check(
    body: HealthSelfCheckStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户端提交问卷 → 后端拼装 Prompt → 调用 AI → 同步返回 AI 回答。

    后端会同时把「用户侧自查卡片消息」和「AI 回答消息」写入 chat_messages，使用现有 ChatSession 或新建。
    """
    # 1. 校验按钮 + 模板
    btn = await db.get(ChatFunctionButton, body.button_id)
    if not btn or not btn.is_enabled:
        raise HTTPException(status_code=404, detail="功能按钮不存在或已禁用")
    if btn.button_type != "health_self_check":
        raise HTTPException(status_code=400, detail=f"按钮类型必须为 health_self_check，当前 {btn.button_type}")

    tpl = await db.get(HealthCheckTemplate, body.template_id)
    if not tpl or not tpl.enabled:
        raise HTTPException(status_code=400, detail="关联的问卷模板不存在或已停用，请联系管理员")

    # 校验持续时间合法性（在模板配置内）
    duration_opts = list(tpl.duration_options or [])
    if duration_opts and body.duration not in duration_opts:
        raise HTTPException(status_code=400, detail=f"持续时间 {body.duration} 不在模板档位 {duration_opts} 内")

    # 校验部位合法性
    part = await db.get(BodyPartDict, body.body_part_id)
    if not part or not part.enabled:
        raise HTTPException(status_code=400, detail="选定的部位不存在或已停用")
    template_part_ids = {int(p.get("id")) for p in (tpl.body_parts or []) if p.get("id") is not None}
    if template_part_ids and part.id not in template_part_ids:
        raise HTTPException(status_code=400, detail=f"部位 {part.name} 不在模板允许范围内")

    # 校验症状
    if not body.symptoms:
        raise HTTPException(status_code=400, detail="至少选择 1 个症状")
    avail = set(list(part.symptoms or []))
    extra = [s for s in body.symptoms if s not in avail]
    # 兼容：避免脏数据导致 422；只做 warning，不强校验
    if extra:
        logger.warning("[health_self_check] 用户 %s 提交的症状 %s 不在部位 %s 字典内", current_user.id, extra, part.name)

    # 2. 构建档案上下文
    archive_ctx = await _build_archive_context(db, current_user, body.archive_id)

    # 3. 拼装 Prompt（按钮自定义优先；否则用模板默认）
    if btn.prompt_override_enabled and (btn.prompt_override_text or "").strip():
        prompt_template = btn.prompt_override_text or ""
    else:
        prompt_template = tpl.default_prompt or ""

    vars_map = {
        "档案信息": archive_ctx["summary"],
        "档案年龄": archive_ctx["age"],
        "档案性别": archive_ctx["gender"],
        "档案既往病史": archive_ctx["history"],
        "档案过敏史": archive_ctx["allergies"],
        "部位": part.name,
        "症状列表": "、".join(body.symptoms),
        "持续时间": body.duration,
    }
    final_prompt = _format_prompt(prompt_template, vars_map)

    # 4. 获取或新建 ChatSession
    session: Optional[ChatSession] = None
    if body.session_id:
        session = await db.get(ChatSession, body.session_id)
        if session and session.user_id != current_user.id:
            session = None
    if not session:
        session = ChatSession(
            user_id=current_user.id,
            session_type=SessionType.symptom_check,
            title=f"🩺 {part.name}健康自查",
            family_member_id=body.archive_id if body.archive_id else None,
            message_count=0,
        )
        db.add(session)
        await db.flush()

    # 5. 卡片 payload
    card_payload = HealthSelfCheckCardPayload(
        archive_id=body.archive_id,
        archive_name=archive_ctx["name"],
        archive_age=int(archive_ctx["age"]) if archive_ctx["age"].isdigit() else None,
        archive_gender=archive_ctx["gender"],
        body_part={"id": part.id, "name": part.name, "icon": part.icon},
        symptoms=list(body.symptoms),
        duration=body.duration,
        template_id=tpl.id,
        button_id=btn.id,
    )

    # 6. 写入用户侧"自查卡片"消息
    user_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.user,
        content=f"【健康自查】{part.name} · {('/'.join(body.symptoms))[:80]} · 持续 {body.duration}",
    )
    try:
        user_msg.message_metadata = {
            "kind": "health_self_check_card",
            "payload": card_payload.model_dump(),
        }
    except Exception:
        pass
    db.add(user_msg)
    await db.flush()

    # 7. 调用 AI
    system_prompt = (
        "你是一名专业的全科医生助手。回答需通俗、克制，避免给出确定性诊断。"
        "最后请追加一句：「本回答仅供健康参考，不构成诊疗依据，如不适请及时就医。」"
    )
    try:
        ai_text = await call_ai_model(
            messages=[{"role": "user", "content": final_prompt}],
            system_prompt=system_prompt,
            db=db,
        )
        if isinstance(ai_text, dict):
            ai_text = ai_text.get("content", "")
    except Exception as e:  # noqa: BLE001
        logger.error("[health_self_check] AI 调用失败: %s", e)
        ai_text = (
            "很抱歉，AI 分析服务暂时不可用，请稍后重试。\n"
            "本回答仅供健康参考，不构成诊疗依据，如不适请及时就医。"
        )

    ai_msg = ChatMessage(
        session_id=session.id,
        role=MessageRole.assistant,
        content=ai_text or "",
    )
    db.add(ai_msg)
    session.message_count = (session.message_count or 0) + 2
    await db.commit()

    return HealthSelfCheckStartResponse(
        session_id=session.id,
        user_message_id=user_msg.id,
        ai_message_id=ai_msg.id,
        ai_content=ai_text or "",
        card_payload=card_payload,
    )


# ════════════════════════════════════════════════════════════════
# 管理端：部位症状字典 CRUD
# ════════════════════════════════════════════════════════════════


def _to_part_response(b: BodyPartDict) -> BodyPartDictResponse:
    return BodyPartDictResponse(
        id=b.id, name=b.name, icon=b.icon,
        symptoms=list(b.symptoms or []),
        sort_order=b.sort_order or 100,
        enabled=bool(b.enabled),
        symptom_count=len(list(b.symptoms or [])),
        created_at=b.created_at, updated_at=b.updated_at,
    )


@admin_router.get("/body-part-dict")
async def admin_list_body_parts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    enabled: Optional[bool] = Query(None),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(BodyPartDict).order_by(BodyPartDict.sort_order.asc(), BodyPartDict.id.asc())
    cnt_stmt = select(func.count(BodyPartDict.id))
    if enabled is not None:
        stmt = stmt.where(BodyPartDict.enabled == enabled)
        cnt_stmt = cnt_stmt.where(BodyPartDict.enabled == enabled)
    total = (await db.execute(cnt_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [_to_part_response(b) for b in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@admin_router.post("/body-part-dict", response_model=BodyPartDictResponse)
async def admin_create_body_part(
    body: BodyPartDictCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 唯一性校验
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="部位名称不能为空")
    chk = await db.execute(select(BodyPartDict).where(BodyPartDict.name == name))
    if chk.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"部位 {name} 已存在")
    if not body.symptoms:
        raise HTTPException(status_code=400, detail="症状列表至少 1 项")
    # 同部位症状去重
    seen = set()
    syms: list[str] = []
    for s in body.symptoms:
        s = (s or "").strip()
        if s and s not in seen:
            syms.append(s)
            seen.add(s)
    obj = BodyPartDict(
        name=name, icon=body.icon, symptoms=syms,
        sort_order=body.sort_order if body.sort_order is not None else 100,
        enabled=bool(body.enabled),
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return _to_part_response(obj)


@admin_router.put("/body-part-dict/{part_id}", response_model=BodyPartDictResponse)
async def admin_update_body_part(
    part_id: int,
    body: BodyPartDictUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    obj = await db.get(BodyPartDict, part_id)
    if not obj:
        raise HTTPException(status_code=404, detail="部位不存在")
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        new_name = (data["name"] or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="部位名称不能为空")
        # 唯一性（排除自身）
        chk = await db.execute(
            select(BodyPartDict).where(BodyPartDict.name == new_name, BodyPartDict.id != part_id)
        )
        if chk.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"部位名称 {new_name} 已被占用")
        obj.name = new_name
    if "icon" in data:
        obj.icon = data["icon"]
    if "symptoms" in data and data["symptoms"] is not None:
        seen = set(); syms: list[str] = []
        for s in data["symptoms"]:
            s = (s or "").strip()
            if s and s not in seen:
                syms.append(s); seen.add(s)
        obj.symptoms = syms
    if "sort_order" in data and data["sort_order"] is not None:
        obj.sort_order = data["sort_order"]
    if "enabled" in data and data["enabled"] is not None:
        obj.enabled = bool(data["enabled"])
    await db.flush()
    await db.refresh(obj)
    return _to_part_response(obj)


@admin_router.delete("/body-part-dict/{part_id}")
async def admin_delete_body_part(
    part_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    obj = await db.get(BodyPartDict, part_id)
    if not obj:
        raise HTTPException(status_code=404, detail="部位不存在")
    # 检查是否被模板引用
    tpl_rows = (await db.execute(select(HealthCheckTemplate))).scalars().all()
    for tpl in tpl_rows:
        for ref in (tpl.body_parts or []):
            if int(ref.get("id", 0)) == part_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"部位 {obj.name} 被模板「{tpl.name}」引用，无法删除，请先停用或从模板移除",
                )
    await db.delete(obj)
    await db.flush()
    return {"message": "删除成功"}


# ════════════════════════════════════════════════════════════════
# 管理端：健康自查问卷模板 CRUD
# ════════════════════════════════════════════════════════════════


async def _template_with_ref_count(db: AsyncSession, tpl: HealthCheckTemplate) -> HealthCheckTemplateResponse:
    cnt_res = await db.execute(
        select(func.count(ChatFunctionButton.id))
        .where(ChatFunctionButton.health_check_template_id == tpl.id)
    )
    cnt = cnt_res.scalar() or 0
    return HealthCheckTemplateResponse(
        id=tpl.id, name=tpl.name, description=tpl.description,
        body_parts=list(tpl.body_parts or []),
        duration_options=list(tpl.duration_options or []),
        default_prompt=tpl.default_prompt or "",
        enabled=bool(tpl.enabled),
        reference_button_count=cnt,
        created_at=tpl.created_at, updated_at=tpl.updated_at,
    )


@admin_router.get("/health-check-templates")
async def admin_list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(HealthCheckTemplate.id)))).scalar() or 0
    rows = (await db.execute(
        select(HealthCheckTemplate)
        .order_by(HealthCheckTemplate.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    items = [await _template_with_ref_count(db, t) for t in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.post("/health-check-templates", response_model=HealthCheckTemplateResponse)
async def admin_create_template(
    body: HealthCheckTemplateCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if not body.body_parts:
        raise HTTPException(status_code=400, detail="至少勾选 1 个部位")
    if len(body.duration_options) < 2:
        raise HTTPException(status_code=400, detail="持续时间档位至少 2 档")
    obj = HealthCheckTemplate(
        name=body.name, description=body.description,
        body_parts=[p.model_dump() for p in body.body_parts],
        duration_options=list(body.duration_options),
        default_prompt=body.default_prompt,
        enabled=bool(body.enabled),
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return await _template_with_ref_count(db, obj)


@admin_router.get("/health-check-templates/{tpl_id}", response_model=HealthCheckTemplateDetail)
async def admin_get_template(
    tpl_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(HealthCheckTemplate, tpl_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    base = await _template_with_ref_count(db, tpl)
    detail = HealthCheckTemplateDetail(**base.model_dump())
    # 装载 body_parts_detail
    part_ids = [int(p.get("id")) for p in (tpl.body_parts or []) if p.get("id") is not None]
    if part_ids:
        r = await db.execute(select(BodyPartDict).where(BodyPartDict.id.in_(part_ids)))
        id_to = {b.id: b for b in r.scalars().all()}
        ordered = []
        for ref in (tpl.body_parts or []):
            pid = int(ref.get("id"))
            b = id_to.get(pid)
            if not b:
                continue
            ordered.append({
                "id": b.id, "name": b.name, "icon": b.icon,
                "symptoms": list(b.symptoms or []), "sort": ref.get("sort", 0),
                "enabled": bool(b.enabled),
            })
        detail.body_parts_detail = ordered
    return detail


@admin_router.put("/health-check-templates/{tpl_id}", response_model=HealthCheckTemplateResponse)
async def admin_update_template(
    tpl_id: int,
    body: HealthCheckTemplateUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(HealthCheckTemplate, tpl_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        tpl.name = data["name"]
    if "description" in data:
        tpl.description = data["description"]
    if "body_parts" in data and data["body_parts"] is not None:
        if not data["body_parts"]:
            raise HTTPException(status_code=400, detail="至少勾选 1 个部位")
        tpl.body_parts = [p if isinstance(p, dict) else p.model_dump() for p in data["body_parts"]]
    if "duration_options" in data and data["duration_options"] is not None:
        if len(data["duration_options"]) < 2:
            raise HTTPException(status_code=400, detail="持续时间档位至少 2 档")
        tpl.duration_options = list(data["duration_options"])
    if "default_prompt" in data and data["default_prompt"] is not None:
        tpl.default_prompt = data["default_prompt"]
    if "enabled" in data and data["enabled"] is not None:
        tpl.enabled = bool(data["enabled"])
    await db.flush()
    await db.refresh(tpl)
    return await _template_with_ref_count(db, tpl)


@admin_router.delete("/health-check-templates/{tpl_id}")
async def admin_delete_template(
    tpl_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    tpl = await db.get(HealthCheckTemplate, tpl_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    # 检查引用
    cnt = (await db.execute(
        select(func.count(ChatFunctionButton.id))
        .where(ChatFunctionButton.health_check_template_id == tpl_id)
    )).scalar() or 0
    if cnt > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该模板被 {cnt} 个功能按钮引用，请先解除引用或停用模板",
        )
    await db.delete(tpl)
    await db.flush()
    return {"message": "删除成功"}
