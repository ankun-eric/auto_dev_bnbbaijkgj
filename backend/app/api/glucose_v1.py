"""[PRD-GLUCOSE-V1 2026-05-30] 血糖模块完整闭环 API。

接口前缀: /api/glucose-v1

核心能力：
- 录入血糖（POST /records）
- 五档自动判定 + 高/低糖危象判定（≥16.7 / <2.8）
- 历史列表 + 趋势统计（7/30/90 天）
- 预警事件列表 + 标记已确认
- AI 趋势诊断建议（占位 - 调用现有 AI 接口或返回规则建议）
- PDF 报告链接（占位 - 基于 HTML 渲染说明）

数据表：
- health_glucose_record
- health_glucose_alert

幂等建表通过 main.py lifespan 中 `_migrate_glucose_v1` 完成。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/glucose-v1", tags=["PRD-GLUCOSE-V1 血糖管理"])


# ─── 五档阈值与判定 ───────────────────────────────────────────────────

SCENE_FASTING = 1     # 空腹
SCENE_AFTER_MEAL = 2  # 餐后 2h
SCENE_RANDOM = 3      # 随机
SCENE_BEDTIME = 4     # 睡前

SCENE_NAME = {
    SCENE_FASTING: "空腹",
    SCENE_AFTER_MEAL: "餐后2h",
    SCENE_RANDOM: "随机",
    SCENE_BEDTIME: "睡前",
}

# 档位编码（PRD §3.1）
LEVEL_VERY_LOW = 1   # 严重偏低
LEVEL_LOW = 2        # 偏低
LEVEL_NORMAL = 3     # 正常
LEVEL_HIGH = 4       # 偏高
LEVEL_VERY_HIGH = 5  # 严重偏高

LEVEL_LABEL = {
    LEVEL_VERY_LOW: "严重偏低",
    LEVEL_LOW: "偏低",
    LEVEL_NORMAL: "正常",
    LEVEL_HIGH: "偏高",
    LEVEL_VERY_HIGH: "严重偏高",
}

LEVEL_COLOR = {
    LEVEL_VERY_LOW: "deep_red",
    LEVEL_LOW: "orange",
    LEVEL_NORMAL: "green",
    LEVEL_HIGH: "orange",
    LEVEL_VERY_HIGH: "red",
}

# 危象编码（PRD §3.2 + §10.2）
CRISIS_NONE = 0
CRISIS_HIGH = 1   # 高糖危象 ≥ 16.7
CRISIS_LOW = 2    # 低糖危象 < 2.8

# 录入合理范围（PRD §八）
VALUE_MIN = 0.5
VALUE_MAX = 35.0

# 危象阈值
CRISIS_HIGH_THRESHOLD = 16.7
CRISIS_LOW_THRESHOLD = 2.8


def judge_level(value: float, scene: int) -> int:
    """根据场景套用五档阈值（PRD §3.1）。

    规则（mmol/L）：
    - 空腹：<2.8 严重偏低 | 2.8~3.9 偏低 | 3.9~6.1 正常 | 6.1~7.0 偏高 | >=7.0 严重偏高
    - 餐后2h/随机/睡前：<2.8 严重偏低 | 2.8~3.9 偏低 | 3.9~7.8 正常 | 7.8~11.1 偏高 | >=11.1 严重偏高
      （随机/睡前 简化为同餐后2h 阈值，见 PRD 说明）
    """
    if value < CRISIS_LOW_THRESHOLD:  # < 2.8
        return LEVEL_VERY_LOW
    if value < 3.9:
        return LEVEL_LOW

    if scene == SCENE_FASTING:
        if value < 6.1:
            return LEVEL_NORMAL
        if value < 7.0:
            return LEVEL_HIGH
        return LEVEL_VERY_HIGH
    # 餐后/随机/睡前
    if value < 7.8:
        return LEVEL_NORMAL
    if value < 11.1:
        return LEVEL_HIGH
    return LEVEL_VERY_HIGH


def judge_crisis(value: float) -> int:
    """高/低糖危象判定（PRD §3.2，跨场景）。"""
    if value >= CRISIS_HIGH_THRESHOLD:
        return CRISIS_HIGH
    if value < CRISIS_LOW_THRESHOLD:
        return CRISIS_LOW
    return CRISIS_NONE


def build_alert_message(value: float, scene: int, crisis: int) -> str:
    """为危象事件生成给守护人 / 弹窗使用的建议文案。"""
    if crisis == CRISIS_HIGH:
        return (
            f"⚠️ 检测到高糖危象 {value} mmol/L（{SCENE_NAME.get(scene, '随机')}）。"
            "建议立即就医，避免剧烈运动，多喝水。"
        )
    if crisis == CRISIS_LOW:
        return (
            f"⚠️ 检测到低糖危象 {value} mmol/L（{SCENE_NAME.get(scene, '随机')}）。"
            "建议立即补充含糖食物（糖水、糖果、果汁），并尽快联系家人或就医。"
        )
    return ""


# ─── Pydantic Schemas ────────────────────────────────────────────────

class GlucoseRecordCreate(BaseModel):
    value: float = Field(..., description="血糖值 mmol/L，0.5~35.0")
    scene: int = Field(..., description="1=空腹 2=餐后2h 3=随机 4=睡前")
    measure_time: Optional[str] = Field(None, description="测量时间 ISO 字符串，默认当前时间")
    note: Optional[str] = Field(None, max_length=200, description="备注")


class GlucoseRecordOut(BaseModel):
    id: int
    user_id: int
    value: float
    scene: int
    scene_label: str
    level: int
    level_label: str
    level_color: str
    is_crisis: int
    crisis_label: str
    measure_time: str
    note: Optional[str] = None
    create_time: str


class GlucoseSaveResponse(BaseModel):
    record: GlucoseRecordOut
    alert: Optional[Dict[str, Any]] = None  # 若触发危象/严重档则附带弹窗与推送信息


class GlucoseStatsResponse(BaseModel):
    range_days: int
    scene: Optional[int] = None
    count: int
    avg: Optional[float] = None
    max: Optional[float] = None
    min: Optional[float] = None
    abnormal_count: int = 0
    target_rate: Optional[float] = None
    trend: List[Dict[str, Any]] = []  # [{date, avg, count}]
    distribution: Dict[str, int] = {}  # 五档分布


class GlucoseAlertOut(BaseModel):
    id: int
    record_id: int
    user_id: int
    alert_type: int
    alert_label: str
    push_status: int
    guardian_confirmed: int
    measure_time: str
    value: float
    scene: int
    create_time: str


class AiAdviceResponse(BaseModel):
    period_days: int
    summary_lines: List[str]
    trend_lines: List[str]
    advice_lines: List[str]
    disclaimer: str


# ─── 内部辅助 ────────────────────────────────────────────────────────

def _parse_measure_time(s: Optional[str]) -> datetime:
    if not s:
        return datetime.utcnow()
    try:
        # 支持 'YYYY-MM-DDTHH:MM:SS' / 'YYYY-MM-DD HH:MM:SS'
        s2 = s.replace("T", " ").replace("Z", "").split("+")[0].strip()
        if "." in s2:
            s2 = s2.split(".")[0]
        return datetime.strptime(s2[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            return datetime.utcnow()


def _fmt_dt(v: Any) -> str:
    """统一兼容 datetime 对象与字符串（SQLite 返回字符串）。"""
    if not v:
        return ""
    if isinstance(v, str):
        # 去除微秒部分并裁剪到 19 位
        s = v.replace("T", " ")
        if "." in s:
            s = s.split(".")[0]
        return s[:19]
    try:
        return v.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)[:19]


def _row_to_record_out(row: Any) -> GlucoseRecordOut:
    rid, uid, value, scene, level, is_crisis, measure_time, note, create_time = row
    return GlucoseRecordOut(
        id=int(rid),
        user_id=int(uid),
        value=float(value),
        scene=int(scene),
        scene_label=SCENE_NAME.get(int(scene), "随机"),
        level=int(level),
        level_label=LEVEL_LABEL.get(int(level), "正常"),
        level_color=LEVEL_COLOR.get(int(level), "green"),
        is_crisis=int(is_crisis or 0),
        crisis_label=("高糖危象" if int(is_crisis or 0) == CRISIS_HIGH
                      else "低糖危象" if int(is_crisis or 0) == CRISIS_LOW else ""),
        measure_time=_fmt_dt(measure_time),
        note=note,
        create_time=_fmt_dt(create_time),
    )


async def _list_guardians_of(db: AsyncSession, user_id: int) -> List[int]:
    """读取该被守护人的所有守护人 user_id（尽力而为，多源兼容）。

    bini-health 中守护人关系散落在多张表，本接口选择最稳健的兜底：
    仅尝试读取 `family_member_relation`（如存在），失败则返回空列表，
    推送降级为站内信占位。
    """
    try:
        sql = text(
            "SELECT guardian_user_id FROM family_member_relation "
            "WHERE managed_user_id=:uid AND status='active'"
        )
        res = await db.execute(sql, {"uid": user_id})
        return [int(r[0]) for r in res.fetchall() if r and r[0]]
    except Exception:
        return []


async def _push_alert(
    db: AsyncSession, *, user_id: int, record_id: int, alert_type: int,
    value: float, scene: int, message: str,
) -> int:
    """[PRD §3.3-§3.4] 写预警事件 + 占位推送。

    返回 alert_id。具体推送通道（站内信 / APP Push / 订阅消息）由后续接入的
    推送服务消费 health_glucose_alert 表完成。本期仅写表 + 写站内信 log。
    """
    guardians = await _list_guardians_of(db, user_id)
    try:
        res = await db.execute(
            text(
                "INSERT INTO health_glucose_alert "
                "(record_id, user_id, alert_type, push_status, guardian_confirmed, "
                " message, guardian_ids, create_time) "
                "VALUES (:rid, :uid, :atype, 1, 0, :msg, :gids, :ct)"
            ),
            {
                "rid": record_id,
                "uid": user_id,
                "atype": int(alert_type),
                "msg": message[:512],
                "gids": ",".join(str(g) for g in guardians) if guardians else "",
                "ct": datetime.utcnow(),
            },
        )
        await db.commit()
        # 兼容不同方言取 lastrowid
        alert_id = 0
        try:
            alert_id = int(res.lastrowid or 0)  # type: ignore[attr-defined]
        except Exception:
            pass
        logger.info(
            "[GLUCOSE-V1] alert_pushed id=%s record=%s user=%s type=%s value=%s guardians=%s",
            alert_id, record_id, user_id, alert_type, value, guardians,
        )
        return alert_id
    except Exception as exc:
        logger.exception("[GLUCOSE-V1] push_alert_failed: %s", exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return 0


# ─── 路由：录入 ──────────────────────────────────────────────────────

@router.post("/records", response_model=GlucoseSaveResponse)
async def create_record(
    body: GlucoseRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 字段合法性
    if body.scene not in SCENE_NAME:
        raise HTTPException(status_code=400, detail="scene 取值非法（1/2/3/4）")
    if body.value is None or body.value < VALUE_MIN or body.value > VALUE_MAX:
        raise HTTPException(status_code=400, detail=f"数值不在合理范围（{VALUE_MIN}~{VALUE_MAX}）")

    value = round(float(body.value), 1)
    scene = int(body.scene)
    measure_time = _parse_measure_time(body.measure_time)
    note = (body.note or "").strip()[:200] or None

    level = judge_level(value, scene)
    is_crisis = judge_crisis(value)

    now = datetime.utcnow()
    insert_sql = text(
        "INSERT INTO health_glucose_record "
        "(user_id, value, scene, level, is_crisis, measure_time, note, create_time) "
        "VALUES (:uid, :val, :scene, :level, :crisis, :mt, :note, :ct)"
    )
    res = await db.execute(
        insert_sql,
        {
            "uid": current_user.id,
            "val": value,
            "scene": scene,
            "level": level,
            "crisis": is_crisis,
            "mt": measure_time,
            "note": note,
            "ct": now,
        },
    )
    await db.commit()

    new_id = 0
    try:
        new_id = int(res.lastrowid or 0)  # type: ignore[attr-defined]
    except Exception:
        pass
    if not new_id:
        # 兜底
        row = (await db.execute(
            text(
                "SELECT id FROM health_glucose_record "
                "WHERE user_id=:uid ORDER BY id DESC LIMIT 1"
            ),
            {"uid": current_user.id},
        )).fetchone()
        if row:
            new_id = int(row[0])

    record_out = GlucoseRecordOut(
        id=new_id,
        user_id=current_user.id,
        value=value,
        scene=scene,
        scene_label=SCENE_NAME[scene],
        level=level,
        level_label=LEVEL_LABEL[level],
        level_color=LEVEL_COLOR[level],
        is_crisis=is_crisis,
        crisis_label=("高糖危象" if is_crisis == CRISIS_HIGH
                      else "低糖危象" if is_crisis == CRISIS_LOW else ""),
        measure_time=measure_time.strftime("%Y-%m-%d %H:%M:%S"),
        note=note,
        create_time=now.strftime("%Y-%m-%d %H:%M:%S"),
    )

    alert_payload: Optional[Dict[str, Any]] = None

    # 危象或严重档触发预警事件
    if is_crisis != CRISIS_NONE:
        msg = build_alert_message(value, scene, is_crisis)
        alert_id = await _push_alert(
            db, user_id=current_user.id, record_id=new_id,
            alert_type=is_crisis, value=value, scene=scene, message=msg,
        )
        alert_payload = {
            "must_popup": True,
            "alert_id": alert_id,
            "alert_type": is_crisis,
            "alert_label": "高糖危象" if is_crisis == CRISIS_HIGH else "低糖危象",
            "title": "⚠️ 检测到血糖严重异常",
            "message": msg,
            "guardian_notified": True,
        }
    elif level == LEVEL_VERY_HIGH:
        # 严重偏高（非危象）：仅推送，不强弹窗
        msg = f"⚠️ 血糖严重偏高 {value} mmol/L（{SCENE_NAME[scene]}），请注意控制饮食并复测。"
        alert_id = await _push_alert(
            db, user_id=current_user.id, record_id=new_id,
            alert_type=3, value=value, scene=scene, message=msg,
        )
        alert_payload = {
            "must_popup": False,
            "alert_id": alert_id,
            "alert_type": 3,
            "alert_label": "严重偏高",
            "title": "血糖严重偏高",
            "message": msg,
            "guardian_notified": True,
        }
    elif level == LEVEL_HIGH or level == LEVEL_LOW:
        alert_payload = {
            "must_popup": False,
            "alert_id": 0,
            "alert_type": 0,
            "alert_label": LEVEL_LABEL[level],
            "title": LEVEL_LABEL[level],
            "message": "血糖偏高，注意饮食" if level == LEVEL_HIGH else "血糖偏低，注意补充",
            "guardian_notified": False,
        }

    return GlucoseSaveResponse(record=record_out, alert=alert_payload)


# ─── 路由：列表 / 详情 / 删除 ────────────────────────────────────────

@router.get("/records", response_model=Dict[str, Any])
async def list_records(
    scene: Optional[int] = Query(None, description="筛选场景"),
    level: Optional[int] = Query(None, description="筛选档位"),
    days: int = Query(90, ge=1, le=365, description="最近 N 天"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.utcnow() - timedelta(days=days)
    where = ["user_id=:uid", "measure_time>=:start"]
    params: Dict[str, Any] = {"uid": current_user.id, "start": start}
    if scene is not None:
        where.append("scene=:scene")
        params["scene"] = int(scene)
    if level is not None:
        where.append("level=:level")
        params["level"] = int(level)

    where_clause = " AND ".join(where)

    total_row = (await db.execute(
        text(f"SELECT COUNT(*) FROM health_glucose_record WHERE {where_clause}"), params
    )).fetchone()
    total = int(total_row[0]) if total_row else 0

    offset = (page - 1) * size
    list_params = {**params, "limit": size, "offset": offset}
    rows = (await db.execute(
        text(
            f"SELECT id, user_id, value, scene, level, is_crisis, measure_time, note, create_time "
            f"FROM health_glucose_record WHERE {where_clause} "
            f"ORDER BY measure_time DESC, id DESC LIMIT :limit OFFSET :offset"
        ),
        list_params,
    )).fetchall()

    items = [_row_to_record_out(r).model_dump() for r in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT user_id FROM health_glucose_record WHERE id=:rid"),
        {"rid": record_id},
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if int(row[0]) != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除该记录")
    await db.execute(
        text("DELETE FROM health_glucose_record WHERE id=:rid"), {"rid": record_id}
    )
    await db.execute(
        text("DELETE FROM health_glucose_alert WHERE record_id=:rid"), {"rid": record_id}
    )
    await db.commit()
    return {"deleted": True, "id": record_id}


# ─── 路由：统计 / 趋势 ───────────────────────────────────────────────

@router.get("/stats", response_model=GlucoseStatsResponse)
async def get_stats(
    days: int = Query(7, ge=1, le=365),
    scene: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.utcnow() - timedelta(days=days)
    where = ["user_id=:uid", "measure_time>=:start"]
    params: Dict[str, Any] = {"uid": current_user.id, "start": start}
    if scene is not None:
        where.append("scene=:scene")
        params["scene"] = int(scene)
    where_clause = " AND ".join(where)

    rows = (await db.execute(
        text(
            f"SELECT value, scene, level, measure_time "
            f"FROM health_glucose_record WHERE {where_clause}"
        ),
        params,
    )).fetchall()

    values = [float(r[0]) for r in rows]
    levels = [int(r[2]) for r in rows]
    count = len(values)
    avg_v = round(sum(values) / count, 2) if count else None
    max_v = max(values) if count else None
    min_v = min(values) if count else None
    abnormal_count = sum(1 for lv in levels
                         if lv in (LEVEL_VERY_LOW, LEVEL_LOW, LEVEL_HIGH, LEVEL_VERY_HIGH))
    target_count = sum(1 for lv in levels if lv == LEVEL_NORMAL)
    target_rate = round(target_count / count, 3) if count else None

    # 按日趋势
    day_map: Dict[str, List[float]] = {}
    for r in rows:
        d_key = _fmt_dt(r[3])[:10] if r[3] else ""
        if not d_key:
            continue
        day_map.setdefault(d_key, []).append(float(r[0]))
    today = date.today()
    trend: List[Dict[str, Any]] = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        ds = d.strftime("%Y-%m-%d")
        vals = day_map.get(ds, [])
        trend.append({
            "date": ds,
            "avg": round(sum(vals) / len(vals), 2) if vals else None,
            "count": len(vals),
        })

    # 分档分布
    distribution = {LEVEL_LABEL[lv]: 0 for lv in (
        LEVEL_VERY_LOW, LEVEL_LOW, LEVEL_NORMAL, LEVEL_HIGH, LEVEL_VERY_HIGH)}
    for lv in levels:
        distribution[LEVEL_LABEL.get(lv, "正常")] = distribution.get(LEVEL_LABEL.get(lv, "正常"), 0) + 1

    return GlucoseStatsResponse(
        range_days=days,
        scene=scene,
        count=count,
        avg=avg_v,
        max=max_v,
        min=min_v,
        abnormal_count=abnormal_count,
        target_rate=target_rate,
        trend=trend,
        distribution=distribution,
    )


# ─── 路由：预警事件 ─────────────────────────────────────────────────

@router.get("/alerts", response_model=Dict[str, Any])
async def list_alerts(
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.utcnow() - timedelta(days=days)
    total_row = (await db.execute(
        text(
            "SELECT COUNT(*) FROM health_glucose_alert "
            "WHERE user_id=:uid AND create_time>=:start"
        ),
        {"uid": current_user.id, "start": start},
    )).fetchone()
    total = int(total_row[0]) if total_row else 0

    rows = (await db.execute(
        text(
            "SELECT a.id, a.record_id, a.user_id, a.alert_type, a.push_status, "
            "       a.guardian_confirmed, a.create_time, "
            "       r.value, r.scene, r.measure_time "
            "FROM health_glucose_alert a "
            "LEFT JOIN health_glucose_record r ON r.id=a.record_id "
            "WHERE a.user_id=:uid AND a.create_time>=:start "
            "ORDER BY a.create_time DESC, a.id DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {
            "uid": current_user.id, "start": start,
            "limit": size, "offset": (page - 1) * size,
        },
    )).fetchall()

    label_map = {
        CRISIS_HIGH: "高糖危象",
        CRISIS_LOW: "低糖危象",
        3: "严重偏高",
        4: "严重偏低",
    }
    items: List[Dict[str, Any]] = []
    for r in rows:
        items.append({
            "id": int(r[0]),
            "record_id": int(r[1]),
            "user_id": int(r[2]),
            "alert_type": int(r[3]),
            "alert_label": label_map.get(int(r[3]), "异常"),
            "push_status": int(r[4] or 0),
            "guardian_confirmed": int(r[5] or 0),
            "create_time": _fmt_dt(r[6]),
            "value": float(r[7]) if r[7] is not None else None,
            "scene": int(r[8]) if r[8] is not None else None,
            "scene_label": SCENE_NAME.get(int(r[8]), "") if r[8] is not None else "",
            "measure_time": _fmt_dt(r[9]),
        })
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("/alerts/{alert_id}/confirm")
async def confirm_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT user_id FROM health_glucose_alert WHERE id=:aid"), {"aid": alert_id}
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="预警事件不存在")
    if int(row[0]) != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该预警")
    await db.execute(
        text("UPDATE health_glucose_alert SET guardian_confirmed=1 WHERE id=:aid"),
        {"aid": alert_id},
    )
    await db.commit()
    return {"confirmed": True, "id": alert_id}


# ─── 路由：AI 建议（占位但有意义） ────────────────────────────────

@router.get("/ai-advice", response_model=AiAdviceResponse)
async def get_ai_advice(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """基于近 N 天数据用规则引擎生成个性化建议（PRD §六）。

    本期不调用 LLM，避免外部依赖；前端可在此接口基础上自行扩展为流式 AI。
    返回结构稳定，包含必要的"仅供参考"免责声明。
    """
    start = datetime.utcnow() - timedelta(days=days)
    rows = (await db.execute(
        text(
            "SELECT value, scene, level, measure_time FROM health_glucose_record "
            "WHERE user_id=:uid AND measure_time>=:start"
        ),
        {"uid": current_user.id, "start": start},
    )).fetchall()

    fasting = [float(r[0]) for r in rows if int(r[1]) == SCENE_FASTING]
    after_meal = [float(r[0]) for r in rows if int(r[1]) == SCENE_AFTER_MEAL]
    levels = [int(r[2]) for r in rows]

    def _avg(arr: List[float]) -> Optional[float]:
        return round(sum(arr) / len(arr), 2) if arr else None

    avg_fasting = _avg(fasting)
    avg_after = _avg(after_meal)
    abnormal_n = sum(1 for lv in levels
                     if lv in (LEVEL_VERY_LOW, LEVEL_LOW, LEVEL_HIGH, LEVEL_VERY_HIGH))
    crisis_n = sum(1 for r in rows
                   if (float(r[0]) >= CRISIS_HIGH_THRESHOLD
                       or float(r[0]) < CRISIS_LOW_THRESHOLD))

    summary: List[str] = []
    if avg_fasting is not None:
        tag = "正常" if 3.9 <= avg_fasting < 6.1 else ("偏高" if avg_fasting >= 6.1 else "偏低")
        summary.append(f"近 {days} 天平均空腹血糖 {avg_fasting} mmol/L（{tag}）")
    if avg_after is not None:
        tag = "正常" if 3.9 <= avg_after < 7.8 else ("偏高" if avg_after >= 7.8 else "偏低")
        summary.append(f"近 {days} 天平均餐后2h血糖 {avg_after} mmol/L（{tag}）")
    summary.append(f"异常事件 {abnormal_n} 次（其中危象 {crisis_n} 次）")

    trend: List[str] = []
    if avg_after is not None and avg_after >= 7.8:
        trend.append("餐后血糖偏高，提示主食量或升糖速度需调整")
    if avg_fasting is not None and avg_fasting >= 7.0:
        trend.append("空腹血糖严重偏高，建议尽快复诊评估")
    if crisis_n > 0:
        trend.append(f"近期发生 {crisis_n} 次危象事件，强烈建议线下就医评估")
    if not trend:
        trend.append("近期血糖整体处于可接受范围，继续保持")

    advice: List[str] = []
    if avg_after is not None and avg_after >= 7.8:
        advice.append("控制晚餐主食分量，建议 50–75g")
        advice.append("餐后 30 分钟轻度散步 20 分钟")
    if avg_fasting is not None and avg_fasting >= 6.1:
        advice.append("睡前避免甜食与高升糖食物")
    if crisis_n > 0:
        advice.append("近期如有持续偏高或偏低，建议尽快复诊")
    if not advice:
        advice = [
            "保持规律饮食与适量运动",
            "建议每周记录 3 次以上空腹与餐后血糖",
            "如出现头晕、心慌、出冷汗等异常，立即测量并联系守护人",
        ]

    return AiAdviceResponse(
        period_days=days,
        summary_lines=summary,
        trend_lines=trend,
        advice_lines=advice,
        disclaimer="此建议仅供参考，不能替代医生诊断。",
    )


# ─── 路由：PDF 报告（占位 - 返回 HTML 渲染页 URL） ────────────────

@router.get("/report", response_model=Dict[str, Any])
async def get_report_meta(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §F10] 报告导出元数据。

    本期返回报告结构体 + 临时分享链接（占位），前端可基于此渲染 HTML/PDF。
    生成真实 PDF 二进制可在后续接入 wkhtmltopdf / weasyprint。
    """
    stats = await get_stats(days=days, scene=None, current_user=current_user, db=db)
    advice = await get_ai_advice(days=days, current_user=current_user, db=db)

    return {
        "user_id": current_user.id,
        "period_days": days,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats.model_dump(),
        "ai_advice": advice.model_dump(),
        "share_url": f"/glucose/report?days={days}&token=preview",
        "share_valid_days": 7,
    }


# ─── 路由：餐后 2 小时提醒设置（v1 仅落库，提醒由本地定时器触发） ─

class GlucoseReminderConfig(BaseModel):
    breakfast: Optional[str] = Field(None, description="HH:MM，留空则关闭")
    lunch: Optional[str] = Field(None, description="HH:MM")
    dinner: Optional[str] = Field(None, description="HH:MM")
    enabled: bool = True


@router.get("/reminder", response_model=GlucoseReminderConfig)
async def get_reminder(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text(
            "SELECT breakfast, lunch, dinner, enabled "
            "FROM health_glucose_reminder WHERE user_id=:uid"
        ),
        {"uid": current_user.id},
    )).fetchone()
    if not row:
        return GlucoseReminderConfig(
            breakfast="07:00", lunch="12:00", dinner="18:30", enabled=False,
        )
    return GlucoseReminderConfig(
        breakfast=row[0], lunch=row[1], dinner=row[2], enabled=bool(row[3]),
    )


@router.put("/reminder", response_model=GlucoseReminderConfig)
async def set_reminder(
    body: GlucoseReminderConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exists = (await db.execute(
        text("SELECT id FROM health_glucose_reminder WHERE user_id=:uid"),
        {"uid": current_user.id},
    )).fetchone()
    params = {
        "uid": current_user.id,
        "b": body.breakfast, "l": body.lunch, "d": body.dinner,
        "e": 1 if body.enabled else 0,
        "ut": datetime.utcnow(),
    }
    if exists:
        await db.execute(
            text(
                "UPDATE health_glucose_reminder SET breakfast=:b, lunch=:l, dinner=:d, "
                "enabled=:e, updated_at=:ut WHERE user_id=:uid"
            ),
            params,
        )
    else:
        await db.execute(
            text(
                "INSERT INTO health_glucose_reminder "
                "(user_id, breakfast, lunch, dinner, enabled, created_at, updated_at) "
                "VALUES (:uid, :b, :l, :d, :e, :ut, :ut)"
            ),
            params,
        )
    await db.commit()
    return body
