"""
[PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳（独居守护）后端 API

提供：
- 配置管理（阈值/暂停/状态）
- 签到（每日平安）
- 紧急联系人 CRUD
- 预警记录查询
- 后台扫描任务调用入口（被定时任务调用）
"""
from __future__ import annotations

import logging
import os
import smtplib
import secrets
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
import re
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.core.security import get_current_user
from app.models.models import EmailLog, SystemConfig, SystemMessage, User

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


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$")


def _validate_email(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not _EMAIL_RE.match(v):
        raise ValueError("邮箱格式不正确")
    return v


class ContactCreateRequest(BaseModel):
    name: str = Field(..., max_length=50)
    email: str = Field(..., max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    relation: Optional[str] = Field(None, max_length=20)
    wechat_openid: Optional[str] = Field(None, max_length=100)

    @field_validator("email")
    @classmethod
    def _v_email(cls, v):
        return _validate_email(v)


class ContactUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    relation: Optional[str] = Field(None, max_length=20)
    wechat_openid: Optional[str] = Field(None, max_length=100)
    sort_order: Optional[int] = Field(None, ge=1, le=3)

    @field_validator("email")
    @classmethod
    def _v_email(cls, v):
        return _validate_email(v)


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
            " email VARCHAR(200) NOT NULL,"
            " phone VARCHAR(20) NULL,"
            " relation VARCHAR(20) NULL,"
            " wechat_openid VARCHAR(100) NULL,"
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
            " email VARCHAR(200) NOT NULL,"
            " phone VARCHAR(20) NULL,"
            " relation VARCHAR(20) NULL,"
            " wechat_openid VARCHAR(100) NULL,"
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
    """根据配置 + 最近签到，计算运行态。"""
    if now is None:
        now = datetime.utcnow()
    threshold_hours = int(cfg.get("threshold_hours") or 48)
    paused_until = cfg.get("paused_until")
    status = cfg.get("status") or "normal"

    if status == "paused":
        if paused_until is None or (isinstance(paused_until, datetime) and paused_until > now):
            return {
                "runtime_status": "paused",
                "next_checkin_at": None,
                "remaining_hours": None,
                "paused_until": paused_until.isoformat() if paused_until else None,
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
        if status == "alerting":
            runtime = "alerting"

    return {
        "runtime_status": runtime,
        "next_checkin_at": deadline.isoformat(),
        "remaining_hours": round(delta, 2),
        "paused_until": None,
    }


# ─────────────── Email & SMTP ───────────────


def _smtp_env_config() -> Optional[dict]:
    """从环境变量读取 SMTP 配置（兜底）。"""
    host = os.environ.get("SMTP_HOST") or os.environ.get("EMAIL_NOTIFY_SMTP_HOST")
    port = os.environ.get("SMTP_PORT") or os.environ.get("EMAIL_NOTIFY_SMTP_PORT")
    user = os.environ.get("SMTP_USER") or os.environ.get("EMAIL_NOTIFY_SMTP_USER")
    pwd = os.environ.get("SMTP_PASSWORD") or os.environ.get("EMAIL_NOTIFY_SMTP_PASSWORD")
    if host and port and user and pwd:
        try:
            return {"host": host, "port": int(port), "user": user, "password": pwd}
        except ValueError:
            return None
    return None


async def _load_smtp_config(db: AsyncSession) -> Optional[dict]:
    """优先从 SystemConfig 读取邮件 SMTP 配置；找不到则尝试环境变量。"""
    try:
        result = await db.execute(select(SystemConfig).where(
            SystemConfig.config_key.in_([
                "email_notify_enable",
                "email_notify_smtp_host",
                "email_notify_smtp_port",
                "email_notify_smtp_user",
                "email_notify_smtp_password",
            ])
        ))
        m = {c.config_key: c.config_value for c in result.scalars().all()}
        if (m.get("email_notify_enable", "").lower() == "true"
                and m.get("email_notify_smtp_host")
                and m.get("email_notify_smtp_port")
                and m.get("email_notify_smtp_user")
                and m.get("email_notify_smtp_password")):
            pwd = m["email_notify_smtp_password"]
            try:
                from app.services.sms_service import decrypt_secret_key
                pwd = decrypt_secret_key(pwd)
            except Exception:
                pass
            return {
                "host": m["email_notify_smtp_host"],
                "port": int(m["email_notify_smtp_port"]),
                "user": m["email_notify_smtp_user"],
                "password": pwd,
            }
    except Exception as exc:
        logger.warning("safety_rope: load smtp from SystemConfig failed: %s", exc)
    return _smtp_env_config()


def _send_email_sync(smtp_cfg: dict, to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_cfg["user"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        port = smtp_cfg["port"]
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_cfg["host"], port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_cfg["host"], port, timeout=15)
            server.starttls()
        server.login(smtp_cfg["user"], smtp_cfg["password"])
        server.sendmail(smtp_cfg["user"], [to_email], msg.as_string())
        server.quit()
        return True, ""
    except Exception as exc:
        return False, str(exc)[:500]


async def _send_email(db: AsyncSession, to_email: str, subject: str, html_body: str) -> bool:
    """统一邮件发送 + EmailLog 落盘。SMTP 未配置时仅记录 pending 日志返回 False。"""
    smtp_cfg = await _load_smtp_config(db)
    log = EmailLog(
        to_email=to_email,
        subject=subject,
        content=html_body,
        status="pending",
        is_test=False,
    )
    if not smtp_cfg:
        log.status = "skipped"
        log.error_message = "SMTP not configured"
        db.add(log)
        return False
    ok, err = _send_email_sync(smtp_cfg, to_email, subject, html_body)
    log.status = "success" if ok else "failed"
    if not ok:
        log.error_message = err
    db.add(log)
    return ok


async def _send_system_message(db: AsyncSession, recipient_user_id: int, title: str,
                                content: str, message_type: str = "safety_rope") -> None:
    db.add(SystemMessage(
        message_type=message_type,
        recipient_user_id=recipient_user_id,
        title=title,
        content=content,
    ))


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
        today_checked = last["checkin_at"].date() == datetime.utcnow().date()

    return {
        "config": {
            "threshold_hours": cfg["threshold_hours"],
            "status": cfg["status"],
            "paused_until": cfg["paused_until"].isoformat() if cfg.get("paused_until") else None,
        },
        "last_checkin": {
            "checkin_at": last["checkin_at"].isoformat() if last else None,
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
            new_paused_until = datetime.utcnow() + timedelta(days=body.paused_days)
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

    # 记录签到
    now = datetime.utcnow()
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

    # 若之前是预警中，自动解除并通知联系人
    was_alerting = cfg.get("status") == "alerting"
    if was_alerting:
        await db.execute(text(
            "UPDATE safety_rope_config SET status='normal', updated_at=CURRENT_TIMESTAMP WHERE user_id=:uid"
        ), {"uid": current_user.id})
        # 找最近一条未解除的预警，标记 resolved
        alert_row = (await db.execute(text(
            "SELECT id FROM safety_rope_alert WHERE user_id=:uid AND resolved_at IS NULL "
            "ORDER BY triggered_at DESC LIMIT 1"
        ), {"uid": current_user.id})).first()
        if alert_row:
            await db.execute(text(
                "UPDATE safety_rope_alert SET resolved_at=:t, resolved_location=:loc WHERE id=:aid"
            ), {"t": now, "loc": (body.location_address or "")[:255] if body.location_address else None,
                "aid": alert_row[0]})
        # 通知联系人解除
        contacts = (await db.execute(text(
            "SELECT name, email FROM safety_rope_contact WHERE user_id=:uid ORDER BY sort_order"
        ), {"uid": current_user.id})).fetchall()
        user_name = current_user.nickname or current_user.phone or f"用户{current_user.id}"
        loc_text = body.location_address or "（未提供位置）"
        for c in contacts:
            await _send_email(
                db, c[1],
                f"【数字安全绳·已平安解除】{user_name}",
                f"<p><b>{user_name}</b> 已于 {now.strftime('%Y-%m-%d %H:%M')}（UTC）在 App 中重新签到。</p>"
                f"<p>最新位置：{loc_text}</p>"
                f"<p>之前的预警已自动解除，TA 已平安。</p>"
                f"<p style='color:#888;font-size:12px'>—— bini-health 数字安全绳</p>"
            )

    await db.commit()
    return {"success": True, "checkin_at": now.isoformat(), "alert_resolved": was_alerting}


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
                "checkin_at": r[1].isoformat() if r[1] else None,
                "location_address": r[2],
            }
            for r in rows
        ],
        "total": len(rows),
    }


# ─────────────── API: Contacts ───────────────


@router.get("/contacts")
async def list_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _ensure_tables(db)
    rows = (await db.execute(text(
        "SELECT id, name, email, phone, relation, wechat_openid, sort_order "
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
    cnt = (await db.execute(text(
        "SELECT COUNT(1) FROM safety_rope_contact WHERE user_id=:uid"
    ), {"uid": current_user.id})).scalar() or 0
    if cnt >= 3:
        raise HTTPException(400, "紧急联系人最多 3 位")
    sort_order = int(cnt) + 1
    await db.execute(text(
        "INSERT INTO safety_rope_contact (user_id, name, email, phone, relation, wechat_openid, sort_order) "
        "VALUES (:uid, :name, :email, :phone, :rel, :openid, :so)"
    ), {
        "uid": current_user.id,
        "name": body.name,
        "email": body.email,
        "phone": body.phone,
        "rel": body.relation,
        "openid": body.wechat_openid,
        "so": sort_order,
    })
    await db.commit()

    # 给联系人发确认邮件
    user_name = current_user.nickname or current_user.phone or f"用户{current_user.id}"
    await _send_email(
        db, body.email,
        f"【数字安全绳】您被设为 {user_name} 的紧急联系人",
        f"<p>您好 <b>{body.name}</b>：</p>"
        f"<p>{user_name} 已将您设为「数字安全绳」紧急联系人。</p>"
        f"<p>当 TA 连续未签到超过设定时长时，您将收到预警邮件。届时请尽快联系 TA，确认其安全。</p>"
        f"<p style='color:#888;font-size:12px'>—— bini-health 数字安全绳</p>"
    )
    await db.commit()
    return {"success": True}


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
    updates = []
    params: dict[str, Any] = {"cid": contact_id, "uid": current_user.id}
    for fld in ("name", "email", "phone", "relation", "wechat_openid", "sort_order"):
        v = getattr(body, fld)
        if v is not None:
            updates.append(f"{fld}=:{fld}")
            params[fld] = v
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
            "triggered_at": r[1].isoformat() if r[1] else None,
            "last_checkin_at": r[2].isoformat() if r[2] else None,
            "last_location": r[3],
            "notified_contacts": contacts or [],
            "resolved_at": r[5].isoformat() if r[5] else None,
            "resolved_location": r[6],
        })
    return {"items": items, "total": len(items)}


# ─────────────── Scanner (called by scheduler) ───────────────


async def scan_and_notify() -> dict[str, int]:
    """扫描所有用户，对到期者触发预警/提前提醒。供 APScheduler 周期调用。"""
    import json
    stats = {"scanned": 0, "pre_warned": 0, "alerted": 0}
    async with async_session() as db:
        try:
            await _ensure_tables(db)
            cfg_rows = (await db.execute(text(
                "SELECT user_id, threshold_hours, status, paused_until, last_warning_pre_at "
                "FROM safety_rope_config"
            ))).fetchall()
            now = datetime.utcnow()
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
                        if user.email:
                            await _send_email(
                                db, user.email,
                                "【数字安全绳】该签到啦",
                                "<p>您今日尚未签到，请打开 App 点击「我今天平安」完成签到。</p>"
                                "<p style='color:#888;font-size:12px'>—— bini-health 数字安全绳</p>"
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
                        "SELECT id, name, email, phone FROM safety_rope_contact "
                        "WHERE user_id=:uid ORDER BY sort_order"
                    ), {"uid": uid})).fetchall()
                    notified = []
                    for c in contacts:
                        c_id, c_name, c_email, c_phone = c
                        body_html = (
                            f"<p><b>【数字安全绳预警】</b></p>"
                            f"<p>您是 <b>{user_name}</b> 的紧急联系人。</p>"
                            f"<p>TA 已经连续 {threshold_hours} 小时没有在 App 中签到了。</p>"
                            f"<p>📅 最后签到时间：{last_at.strftime('%Y-%m-%d %H:%M')}（UTC）</p>"
                            f"<p>📍 最后签到位置：{last.get('location_address') or '（未提供）'}</p>"
                            f"<p>📞 TA 的手机号：{(user.phone or '未提供')}</p>"
                            f"<p>建议：</p><ol>"
                            f"<li>立刻拨打电话联系 TA</li>"
                            f"<li>如联系不上，可前往最后签到位置查看</li>"
                            f"<li>必要时联系所在地社区/物业/警方</li></ol>"
                            f"<p style='color:#888;font-size:12px'>—— bini-health 数字安全绳</p>"
                        )
                        ok = await _send_email(
                            db, c_email,
                            f"【数字安全绳预警】{user_name} 超时未签到",
                            body_html,
                        )
                        notified.append({
                            "contact_id": c_id,
                            "name": c_name,
                            "email": c_email,
                            "email_status": "success" if ok else "failed",
                        })
                    # 给本人也发一条系统消息提示
                    await _send_system_message(
                        db, uid,
                        "您已超时未签到",
                        "您已超时未签到，系统已通知您的紧急联系人。请尽快重新签到。",
                        message_type="safety_rope_alert",
                    )
                    # 写预警记录 + 更新状态
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
    """管理员手工触发扫描（用于测试）。"""
    if current_user.role not in ("admin",):
        raise HTTPException(403, "仅管理员可触发")
    return await scan_and_notify()
