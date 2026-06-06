"""
[PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳（独居守护）后端 API

[BUGFIX-SAFETY-ROPE-V1 2026-06-03] v2 锁死版：
- 彻底移除 SMTP 邮件发送（国内场景不需要）→ 根治 create_contact 阻塞导致 "添加成功但列表无记录" 的 Bug
- 紧急联系人：手机号必填，且必须是 bini-health 已注册用户；保存时写入 matched_user_id
- 关系字段统一为 7 芯片：子女 / 配偶 / 父母 / 邻居 / 朋友 / 护工 / 其他
- 邮箱字段保留为可选（兼容旧数据库），不再强制
- 新增 GET /contacts/check-phone：表单失焦时校验手机号是否已注册
- 预警通知改走 SystemMessage（matched_user_id）

[BUGFIX-TIMEZONE-BJ-20260605] 全局北京时间修复：
- 新增 _to_bj_str() / _to_bj_display() 工具函数
- 所有对外返回的时间字符串统一转为北京时间（UTC+8）
- 系统消息中的硬编码（UTC）后缀改为北京时间显示
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional


def _to_bj_str(dt: Optional[datetime]) -> Optional[str]:
    """将 datetime 转为北京时间字符串 "YYYY-MM-DD HH:MM:SS"。"""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _to_bj_display(dt: datetime) -> str:
    """将 datetime 转为北京时间显示字符串，格式 YYYY-MM-DD HH:MM。"""
    return dt.strftime("%Y-%m-%d %H:%M")

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.core.security import get_current_user
from app.models.models import SystemMessage, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/safety-rope", tags=["数字安全绳"])


# ─────────────── Schemas ───────────────


class CheckinRequest(BaseModel):
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_address: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    threshold_hours: Optional[int] = Field(None, description="超时阈值，仅支持 24/48")
    paused: Optional[bool] = None
    paused_days: Optional[int] = Field(None, description="暂停天数；为空且 paused=True 表示无限期")


# 7 芯片关系白名单
ALLOWED_RELATIONS = {"子女", "配偶", "父母", "邻居", "朋友", "护工", "其他"}

_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class ContactCreateRequest(BaseModel):
    name: str = Field(..., max_length=50, min_length=1)
    phone: str = Field(..., max_length=20)
    relation: Optional[str] = Field(None, max_length=20)
    # 兼容字段：邮箱不再强制，前端表单已删除
    email: Optional[str] = Field(None, max_length=200)
    wechat_openid: Optional[str] = Field(None, max_length=100)


class ContactUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    relation: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=200)
    wechat_openid: Optional[str] = Field(None, max_length=100)
    sort_order: Optional[int] = Field(None, ge=1, le=3)


# ─────────────── Helpers ───────────────


async def _ensure_tables(db: AsyncSession) -> None:
    """确保 4 张表存在（兼容 MySQL / SQLite）。"""
    is_sqlite = "sqlite" in str(db.bind.url) if db.bind else False

    if is_sqlite:
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_config ("
            " user_id INTEGER PRIMARY KEY,"
            " threshold_hours INTEGER NOT NULL DEFAULT 48,"
            " status VARCHAR(20) NOT NULL DEFAULT 'normal',"
            " paused_until DATETIME NULL,"
            " last_warning_pre_at DATETIME NULL,"
            " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_checkin ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL,"
            " checkin_at DATETIME NOT NULL,"
            " location_lat REAL NULL,"
            " location_lng REAL NULL,"
            " location_address VARCHAR(255) NULL"
            ")"
        ))
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_contact ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL,"
            " name VARCHAR(50) NOT NULL,"
            " email VARCHAR(200) NULL,"
            " phone VARCHAR(20) NULL,"
            " relation VARCHAR(20) NULL,"
            " wechat_openid VARCHAR(100) NULL,"
            " matched_user_id INTEGER NULL,"
            " sort_order INTEGER NOT NULL DEFAULT 1,"
            " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_alert ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL,"
            " triggered_at DATETIME NOT NULL,"
            " last_checkin_at DATETIME NULL,"
            " last_location VARCHAR(255) NULL,"
            " notified_contacts TEXT NULL,"
            " resolved_at DATETIME NULL,"
            " resolved_location VARCHAR(255) NULL"
            ")"
        ))
    else:
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_config ("
            " user_id INT NOT NULL,"
            " threshold_hours INT NOT NULL DEFAULT 48,"
            " status VARCHAR(20) NOT NULL DEFAULT 'normal',"
            " paused_until DATETIME NULL,"
            " last_warning_pre_at DATETIME NULL,"
            " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
            " PRIMARY KEY (user_id)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        ))
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_checkin ("
            " id BIGINT NOT NULL AUTO_INCREMENT,"
            " user_id INT NOT NULL,"
            " checkin_at DATETIME NOT NULL,"
            " location_lat DECIMAL(10,6) NULL,"
            " location_lng DECIMAL(10,6) NULL,"
            " location_address VARCHAR(255) NULL,"
            " PRIMARY KEY (id),"
            " KEY idx_srci_user_time (user_id, checkin_at)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        ))
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_contact ("
            " id BIGINT NOT NULL AUTO_INCREMENT,"
            " user_id INT NOT NULL,"
            " name VARCHAR(50) NOT NULL,"
            " email VARCHAR(200) NULL,"
            " phone VARCHAR(20) NULL,"
            " relation VARCHAR(20) NULL,"
            " wechat_openid VARCHAR(100) NULL,"
            " matched_user_id INT NULL,"
            " sort_order INT NOT NULL DEFAULT 1,"
            " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " PRIMARY KEY (id),"
            " KEY idx_srct_user (user_id)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        ))
        await db.execute(text(
            "CREATE TABLE IF NOT EXISTS safety_rope_alert ("
            " id BIGINT NOT NULL AUTO_INCREMENT,"
            " user_id INT NOT NULL,"
            " triggered_at DATETIME NOT NULL,"
            " last_checkin_at DATETIME NULL,"
            " last_location VARCHAR(255) NULL,"
            " notified_contacts TEXT NULL,"
            " resolved_at DATETIME NULL,"
            " resolved_location VARCHAR(255) NULL,"
            " PRIMARY KEY (id),"
            " KEY idx_sra_user (user_id, triggered_at)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        ))

    # 兼容旧表：补加 matched_user_id 列、email 允许 NULL
    try:
        if is_sqlite:
            # SQLite 不支持 ALTER COLUMN，仅尝试添加列
            try:
                await db.execute(text("ALTER TABLE safety_rope_contact ADD COLUMN matched_user_id INTEGER NULL"))
            except Exception:
                pass
        else:
            # MySQL：添加 matched_user_id 列（如已存在会失败，吞掉）
            try:
                await db.execute(text(
                    "ALTER TABLE safety_rope_contact ADD COLUMN matched_user_id INT NULL"
                ))
            except Exception:
                pass
            # 把 email 改为允许 NULL
            try:
                await db.execute(text(
                    "ALTER TABLE safety_rope_contact MODIFY email VARCHAR(200) NULL"
                ))
            except Exception:
                pass
    except Exception:
        pass

    await db.commit()


async def _get_or_create_config(db: AsyncSession, user_id: int) -> dict:
    row = (await db.execute(text(
        "SELECT user_id, threshold_hours, status, paused_until, last_warning_pre_at "
        "FROM safety_rope_config WHERE user_id = :uid"
    ), {"uid": user_id})).first()
    if row:
        return {
            "user_id": row[0],
            "threshold_hours": row[1],
            "status": row[2],
            "paused_until": _parse_dt(row[3]),
            "last_warning_pre_at": _parse_dt(row[4]),
        }
    await db.execute(text(
        "INSERT INTO safety_rope_config (user_id, threshold_hours, status) "
        "VALUES (:uid, 48, 'normal')"
    ), {"uid": user_id})
    await db.commit()
    return {
        "user_id": user_id,
        "threshold_hours": 48,
        "status": "normal",
        "paused_until": None,
        "last_warning_pre_at": None,
    }


def _parse_dt(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "").split(".")[0])
        except Exception:
            try:
                return datetime.strptime(v[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None
    return None


async def _get_last_checkin(db: AsyncSession, user_id: int) -> Optional[dict]:
    row = (await db.execute(text(
        "SELECT id, checkin_at, location_lat, location_lng, location_address "
        "FROM safety_rope_checkin WHERE user_id = :uid "
        "ORDER BY checkin_at DESC LIMIT 1"
    ), {"uid": user_id})).first()
    if not row:
        return None
    return {
        "id": row[0],
        "checkin_at": _parse_dt(row[1]),
        "location_lat": float(row[2]) if row[2] is not None else None,
        "location_lng": float(row[3]) if row[3] is not None else None,
        "location_address": row[4],
    }


def _compute_runtime_state(cfg: dict, last_checkin: Optional[dict], now: Optional[datetime] = None) -> dict:
    if now is None:
        now = datetime.now()
    threshold_hours = int(cfg.get("threshold_hours") or 48)
    paused_until = cfg.get("paused_until")
    status = cfg.get("status") or "normal"

    if status == "paused":
        if paused_until is None or (isinstance(paused_until, datetime) and paused_until > now):
            return {
                "runtime_status": "paused",
                "next_checkin_at": None,
                "remaining_hours": None,
                "paused_until": _to_bj_str(paused_until),
            }

    if not last_checkin or not last_checkin.get("checkin_at"):
        return {
            "runtime_status": "normal",
            "next_checkin_at": None,
            "remaining_hours": None,
            "paused_until": None,
        }

    last_at = last_checkin["checkin_at"]
    deadline = last_at + timedelta(hours=threshold_hours)
    delta = (deadline - now).total_seconds() / 3600.0

    if delta > 1:
        runtime = "normal"
    elif delta > 0:
        runtime = "near_timeout"
    else:
        runtime = "alerting" if status == "alerting" else "near_timeout"

    return {
        "runtime_status": runtime,
        "next_checkin_at": _to_bj_str(deadline),
        "remaining_hours": round(delta, 2),
        "paused_until": None,
    }


async def _send_system_message(db: AsyncSession, recipient_user_id: int, title: str,
                                content: str, message_type: str = "safety_rope") -> None:
    db.add(SystemMessage(
        message_type=message_type,
        recipient_user_id=recipient_user_id,
        title=title,
        content=content,
    ))


async def _find_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    """根据手机号查找已注册用户。"""
    if not phone:
        return None
    phone = phone.strip()
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


# ─────────────── API: Status ───────────────


@router.get("/status")
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    cfg = await _get_or_create_config(db, current_user.id)
    last = await _get_last_checkin(db, current_user.id)
    runtime = _compute_runtime_state(cfg, last)
    contacts_count = (await db.execute(text(
        "SELECT COUNT(1) FROM safety_rope_contact WHERE user_id = :uid"
    ), {"uid": current_user.id})).scalar() or 0

    today_checked = False
    if last and last.get("checkin_at"):
        today_checked = last["checkin_at"].date() == datetime.now().date()

    return {
        "config": {
            "threshold_hours": cfg["threshold_hours"],
            "status": cfg["status"],
            "paused_until": _to_bj_str(cfg.get("paused_until")),
        },
        "last_checkin": {
            "checkin_at": _to_bj_str(last["checkin_at"]) if last else None,
            "location_address": last.get("location_address") if last else None,
            "location_lat": last.get("location_lat") if last else None,
            "location_lng": last.get("location_lng") if last else None,
        } if last else None,
        "runtime_status": runtime["runtime_status"],
        "next_checkin_at": runtime["next_checkin_at"],
        "remaining_hours": runtime["remaining_hours"],
        "today_checked": today_checked,
        "contacts_count": int(contacts_count),
    }


# ─────────────── API: Config ───────────────


@router.put("/config")
async def update_config(
    body: ConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    cfg = await _get_or_create_config(db, current_user.id)

    new_threshold = cfg["threshold_hours"]
    new_status = cfg["status"]
    new_paused_until = cfg.get("paused_until")

    if body.threshold_hours is not None:
        if body.threshold_hours not in (24, 48):
            raise HTTPException(400, "threshold_hours 仅支持 24 或 48")
        new_threshold = body.threshold_hours

    if body.paused is True:
        new_status = "paused"
        if body.paused_days and body.paused_days > 0:
            new_paused_until = datetime.now() + timedelta(days=body.paused_days)
        else:
            new_paused_until = None
    elif body.paused is False:
        new_status = "normal"
        new_paused_until = None

    await db.execute(text(
        "UPDATE safety_rope_config SET threshold_hours=:t, status=:s, paused_until=:p, "
        "updated_at=CURRENT_TIMESTAMP WHERE user_id=:uid"
    ), {"t": new_threshold, "s": new_status, "p": new_paused_until, "uid": current_user.id})
    await db.commit()

    return await get_status(current_user=current_user, db=db)


# ─────────────── API: Checkin ───────────────


@router.post("/checkin")
async def checkin(
    body: CheckinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    cfg = await _get_or_create_config(db, current_user.id)

    now = datetime.now()
    await db.execute(text(
        "INSERT INTO safety_rope_checkin (user_id, checkin_at, location_lat, location_lng, location_address) "
        "VALUES (:uid, :t, :lat, :lng, :addr)"
    ), {
        "uid": current_user.id,
        "t": now,
        "lat": body.location_lat,
        "lng": body.location_lng,
        "addr": (body.location_address or "")[:255] if body.location_address else None,
    })

    was_alerting = cfg.get("status") == "alerting"
    if was_alerting:
        await db.execute(text(
            "UPDATE safety_rope_config SET status='normal', updated_at=CURRENT_TIMESTAMP WHERE user_id=:uid"
        ), {"uid": current_user.id})
        alert_row = (await db.execute(text(
            "SELECT id FROM safety_rope_alert WHERE user_id=:uid AND resolved_at IS NULL "
            "ORDER BY triggered_at DESC LIMIT 1"
        ), {"uid": current_user.id})).first()
        if alert_row:
            await db.execute(text(
                "UPDATE safety_rope_alert SET resolved_at=:t, resolved_location=:loc WHERE id=:aid"
            ), {"t": now, "loc": (body.location_address or "")[:255] if body.location_address else None,
                "aid": alert_row[0]})
        # 通知联系人解除（仅站内信，给 matched_user_id）
        contacts = (await db.execute(text(
            "SELECT name, matched_user_id FROM safety_rope_contact WHERE user_id=:uid ORDER BY sort_order"
        ), {"uid": current_user.id})).fetchall()
        user_name = current_user.nickname or current_user.phone or f"用户{current_user.id}"
        loc_text = body.location_address or "（未提供位置）"
        for c in contacts:
            matched_uid = c[1]
            if matched_uid:
                await _send_system_message(
                    db, matched_uid,
                    f"【数字安全绳·已平安解除】{user_name}",
                    f"{user_name} 已于 {_to_bj_display(now)}（北京时间）重新签到。最新位置：{loc_text}。之前的预警已自动解除。",
                    message_type="safety_rope_resolved",
                )

    await db.commit()
    return {"success": True, "checkin_at": _to_bj_str(now), "alert_resolved": was_alerting}


@router.get("/checkins")
async def list_checkins(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    limit = max(1, min(100, limit))
    rows = (await db.execute(text(
        "SELECT id, checkin_at, location_address FROM safety_rope_checkin "
        "WHERE user_id=:uid ORDER BY checkin_at DESC LIMIT :lim"
    ), {"uid": current_user.id, "lim": limit})).fetchall()
    return {
        "items": [
            {
                "id": r[0],
                "checkin_at": _to_bj_str(r[1]),
                "location_address": r[2],
            }
            for r in rows
        ],
        "total": len(rows),
    }


# ─────────────── API: Contacts ───────────────


@router.get("/contacts/check-phone")
async def check_phone(
    phone: str = Query(..., max_length=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """表单失焦时校验：手机号是否为 bini-health 已注册用户。"""
    phone = (phone or "").strip()
    if not _PHONE_RE.match(phone):
        return {"valid": False, "registered": False, "reason": "手机号格式不正确"}

    user = await _find_user_by_phone(db, phone)
    if not user:
        return {
            "valid": True,
            "registered": False,
            "reason": "该手机号还未注册 bini-health，请先邀请 TA 注册",
        }
    name = user.nickname or f"用户{user.id}"
    return {
        "valid": True,
        "registered": True,
        "user_id": user.id,
        "name": name,
        "reason": f"✓ 已识别用户：{name}",
    }


@router.get("/contacts")
async def list_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    rows = (await db.execute(text(
        "SELECT id, name, email, phone, relation, wechat_openid, sort_order, matched_user_id "
        "FROM safety_rope_contact WHERE user_id=:uid ORDER BY sort_order, id"
    ), {"uid": current_user.id})).fetchall()
    return {
        "items": [
            {
                "id": r[0],
                "name": r[1],
                "email": r[2],
                "phone": r[3],
                "relation": r[4],
                "wechat_openid": r[5],
                "sort_order": r[6],
                "matched_user_id": r[7],
            } for r in rows
        ],
        "max_count": 3,
    }


@router.post("/contacts")
async def create_contact(
    body: ContactCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)

    # 校验：姓名
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "请填写姓名")

    # 校验：手机号必填 + 格式
    phone = (body.phone or "").strip()
    if not _PHONE_RE.match(phone):
        raise HTTPException(400, "请填写正确的 11 位手机号")

    # 校验：必须是 bini-health 已注册用户
    matched_user = await _find_user_by_phone(db, phone)
    if not matched_user:
        raise HTTPException(400, "该手机号还未注册 bini-health，请先邀请 TA 注册")

    # 校验：关系字段（如填写）必须在 7 芯片白名单内
    relation = (body.relation or "").strip() or None
    if relation and relation not in ALLOWED_RELATIONS:
        raise HTTPException(400, f"关系必须是以下之一：{'/'.join(ALLOWED_RELATIONS)}")

    cnt = (await db.execute(text(
        "SELECT COUNT(1) FROM safety_rope_contact WHERE user_id=:uid"
    ), {"uid": current_user.id})).scalar() or 0
    if cnt >= 3:
        raise HTTPException(400, "紧急联系人最多 3 位")
    sort_order = int(cnt) + 1

    await db.execute(text(
        "INSERT INTO safety_rope_contact (user_id, name, email, phone, relation, wechat_openid, sort_order, matched_user_id) "
        "VALUES (:uid, :name, :email, :phone, :rel, :openid, :so, :mid)"
    ), {
        "uid": current_user.id,
        "name": name,
        "email": body.email,  # 兼容：保留为 NULL
        "phone": phone,
        "rel": relation,
        "openid": body.wechat_openid,
        "so": sort_order,
        "mid": matched_user.id,
    })
    await db.commit()

    # 给被设为联系人的注册用户发站内信（必达，不走邮件）
    inviter_name = current_user.nickname or current_user.phone or f"用户{current_user.id}"
    try:
        await _send_system_message(
            db, matched_user.id,
            f"【数字安全绳】您被 {inviter_name} 设为紧急联系人",
            f"{inviter_name} 已将您设为「数字安全绳」紧急联系人。"
            f"当 TA 连续未签到超过设定时长时，您将收到预警通知，"
            f"届时请尽快联系 TA，确认其安全。",
            message_type="safety_rope_invite",
        )
        await db.commit()
    except Exception as exc:
        logger.warning("safety_rope: send invite system message failed: %s", exc)

    return {
        "success": True,
        "matched_user_id": matched_user.id,
        "matched_name": matched_user.nickname or f"用户{matched_user.id}",
    }


@router.put("/contacts/{contact_id}")
async def update_contact(
    contact_id: int,
    body: ContactUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    row = (await db.execute(text(
        "SELECT id FROM safety_rope_contact WHERE id=:cid AND user_id=:uid"
    ), {"cid": contact_id, "uid": current_user.id})).first()
    if not row:
        raise HTTPException(404, "联系人不存在")

    # 如果修改了手机号，需重新校验注册状态
    new_matched_id = None
    if body.phone is not None:
        phone = body.phone.strip()
        if not _PHONE_RE.match(phone):
            raise HTTPException(400, "请填写正确的 11 位手机号")
        u = await _find_user_by_phone(db, phone)
        if not u:
            raise HTTPException(400, "该手机号还未注册 bini-health")
        new_matched_id = u.id

    if body.relation is not None:
        rel = body.relation.strip()
        if rel and rel not in ALLOWED_RELATIONS:
            raise HTTPException(400, f"关系必须是以下之一：{'/'.join(ALLOWED_RELATIONS)}")

    updates = []
    params: dict[str, Any] = {"cid": contact_id, "uid": current_user.id}
    for fld in ("name", "email", "phone", "relation", "wechat_openid", "sort_order"):
        v = getattr(body, fld)
        if v is not None:
            updates.append(f"{fld}=:{fld}")
            params[fld] = v
    if new_matched_id is not None:
        updates.append("matched_user_id=:mid")
        params["mid"] = new_matched_id

    if updates:
        await db.execute(text(
            f"UPDATE safety_rope_contact SET {', '.join(updates)} WHERE id=:cid AND user_id=:uid"
        ), params)
        await db.commit()
    return {"success": True}


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    await db.execute(text(
        "DELETE FROM safety_rope_contact WHERE id=:cid AND user_id=:uid"
    ), {"cid": contact_id, "uid": current_user.id})
    await db.commit()
    return {"success": True}


# ─────────────── API: Alerts ───────────────


@router.get("/alerts")
async def list_alerts(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    limit = max(1, min(100, limit))
    rows = (await db.execute(text(
        "SELECT id, triggered_at, last_checkin_at, last_location, notified_contacts, "
        "resolved_at, resolved_location FROM safety_rope_alert "
        "WHERE user_id=:uid ORDER BY triggered_at DESC LIMIT :lim"
    ), {"uid": current_user.id, "lim": limit})).fetchall()
    items = []
    for r in rows:
        contacts = r[4]
        if isinstance(contacts, str):
            import json
            try:
                contacts = json.loads(contacts)
            except Exception:
                contacts = []
        items.append({
            "id": r[0],
            "triggered_at": _to_bj_str(r[1]),
            "last_checkin_at": _to_bj_str(r[2]),
            "last_location": r[3],
            "notified_contacts": contacts or [],
            "resolved_at": _to_bj_str(r[5]),
            "resolved_location": r[6],
        })
    return {"items": items, "total": len(items)}


# ─────────────── Scanner (called by scheduler) ───────────────


async def scan_and_notify() -> dict[str, int]:
    """扫描所有用户，对到期者触发预警/提前提醒。供 APScheduler 周期调用。
    
    [BUGFIX-SAFETY-ROPE-V1 2026-06-03] 改为只走站内信，移除邮件通道。
    """
    import json
    stats = {"scanned": 0, "pre_warned": 0, "alerted": 0}
    async with async_session() as db:
        try:
            await _ensure_tables(db)
            cfg_rows = (await db.execute(text(
                "SELECT user_id, threshold_hours, status, paused_until, last_warning_pre_at "
                "FROM safety_rope_config"
            ))).fetchall()
            now = datetime.now()
            for cfg_row in cfg_rows:
                stats["scanned"] += 1
                uid, threshold_hours, status, paused_until, last_warn_pre = cfg_row
                if status == "paused":
                    if paused_until is None or (isinstance(paused_until, datetime) and paused_until > now):
                        continue
                    await db.execute(text(
                        "UPDATE safety_rope_config SET status='normal', paused_until=NULL WHERE user_id=:uid"
                    ), {"uid": uid})

                last = await _get_last_checkin(db, uid)
                if not last:
                    continue
                last_at = last["checkin_at"]
                deadline = last_at + timedelta(hours=int(threshold_hours or 48))
                hours_left = (deadline - now).total_seconds() / 3600.0

                # 提前 1 小时提醒（且本次签到周期内未发过）
                if 0 < hours_left <= 1 and (last_warn_pre is None or last_warn_pre < last_at):
                    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
                    if user:
                        await _send_system_message(
                            db, uid,
                            "该签到啦",
                            "还有 1 小时就到签到时间啦，记得打开 App 点一下「我今天平安」~",
                            message_type="safety_rope_pre_warning",
                        )
                        await db.execute(text(
                            "UPDATE safety_rope_config SET last_warning_pre_at=:t WHERE user_id=:uid"
                        ), {"t": now, "uid": uid})
                        stats["pre_warned"] += 1

                # 超时：仅当当前不是 alerting 才触发（避免重复）
                if hours_left <= 0 and status != "alerting":
                    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
                    if not user:
                        continue
                    user_name = user.nickname or user.phone or f"用户{uid}"
                    contacts = (await db.execute(text(
                        "SELECT id, name, phone, matched_user_id FROM safety_rope_contact "
                        "WHERE user_id=:uid ORDER BY sort_order"
                    ), {"uid": uid})).fetchall()
                    notified = []
                    for c in contacts:
                        c_id, c_name, c_phone, c_matched = c
                        content = (
                            f"【数字安全绳预警】您是 {user_name} 的紧急联系人。"
                            f"TA 已经连续 {threshold_hours} 小时没有签到了。"
                            f"📅 最后签到时间：{_to_bj_display(last_at)}（北京时间）"
                            f"📍 最后签到位置：{last.get('location_address') or '（未提供）'}"
                            f"📞 TA 的手机号：{(user.phone or '未提供')}"
                            f"建议立刻拨打电话联系 TA；如联系不上，可前往最后签到位置查看；必要时联系当地社区/物业/警方。"
                        )
                        # 站内信（仅当已 matched）
                        ok = False
                        if c_matched:
                            try:
                                await _send_system_message(
                                    db, int(c_matched),
                                    f"【数字安全绳预警】{user_name} 超时未签到",
                                    content,
                                    message_type="safety_rope_alert",
                                )
                                ok = True
                            except Exception as exc:
                                logger.warning("safety_rope: notify contact %s failed: %s", c_id, exc)
                        notified.append({
                            "contact_id": c_id,
                            "name": c_name,
                            "phone": c_phone,
                            "status": "success" if ok else "skipped",
                        })
                    # 给本人发系统消息
                    await _send_system_message(
                        db, uid,
                        "您已超时未签到",
                        "您已超时未签到，系统已通知您的紧急联系人。请尽快重新签到。",
                        message_type="safety_rope_alert",
                    )
                    await db.execute(text(
                        "INSERT INTO safety_rope_alert (user_id, triggered_at, last_checkin_at, "
                        "last_location, notified_contacts) VALUES (:uid, :t, :lc, :loc, :nc)"
                    ), {
                        "uid": uid, "t": now, "lc": last_at,
                        "loc": last.get("location_address"),
                        "nc": json.dumps(notified, ensure_ascii=False),
                    })
                    await db.execute(text(
                        "UPDATE safety_rope_config SET status='alerting' WHERE user_id=:uid"
                    ), {"uid": uid})
                    stats["alerted"] += 1

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("safety_rope: scan_and_notify failed")
    return stats


@router.post("/_internal/scan")
async def trigger_scan(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.role not in ("admin",):
        raise HTTPException(403, "仅管理员可触发")
    return await scan_and_notify()
