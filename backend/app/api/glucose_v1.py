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

SCENE_FASTING = 1        # 空腹
SCENE_AFTER_MEAL_2H = 2  # 餐后 2h
SCENE_RANDOM = 3         # 随机
SCENE_BEDTIME = 4        # 睡前
# [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 新增 2 个测量类型
SCENE_AFTER_MEAL_1H = 5  # 餐后 1h
SCENE_DAWN = 6           # 凌晨

# 向后兼容旧别名
SCENE_AFTER_MEAL = SCENE_AFTER_MEAL_2H

SCENE_NAME = {
    SCENE_FASTING: "空腹",
    SCENE_AFTER_MEAL_2H: "餐后2h",
    SCENE_RANDOM: "随机",
    SCENE_BEDTIME: "睡前",
    SCENE_AFTER_MEAL_1H: "餐后1h",
    SCENE_DAWN: "凌晨",
}

# 字符串 key -> 编码（用于 H5 端传 string）
SCENE_KEY_TO_CODE = {
    "fasting": SCENE_FASTING,
    "after_meal_2h": SCENE_AFTER_MEAL_2H,
    "after_meal": SCENE_AFTER_MEAL_2H,  # 兼容旧值
    "random": SCENE_RANDOM,
    "before_sleep": SCENE_BEDTIME,
    "bedtime": SCENE_BEDTIME,
    "after_meal_1h": SCENE_AFTER_MEAL_1H,
    "dawn": SCENE_DAWN,
}

SCENE_CODE_TO_KEY = {
    SCENE_FASTING: "fasting",
    SCENE_AFTER_MEAL_2H: "after_meal_2h",
    SCENE_RANDOM: "random",
    SCENE_BEDTIME: "before_sleep",
    SCENE_AFTER_MEAL_1H: "after_meal_1h",
    SCENE_DAWN: "dawn",
}

# 档位编码（PRD §3.1，五档制）— 用词更新：「严重」→「重度」，去除「危象」字眼
LEVEL_VERY_LOW = 1   # 重度偏低
LEVEL_LOW = 2        # 偏低
LEVEL_NORMAL = 3     # 正常
LEVEL_HIGH = 4       # 偏高
LEVEL_VERY_HIGH = 5  # 重度偏高

LEVEL_LABEL = {
    LEVEL_VERY_LOW: "重度偏低",
    LEVEL_LOW: "偏低",
    LEVEL_NORMAL: "正常",
    LEVEL_HIGH: "偏高",
    LEVEL_VERY_HIGH: "重度偏高",
}

# 后端返回给前端的 level key（语义化字符串，便于前端切换文案与色板）
LEVEL_KEY = {
    LEVEL_VERY_LOW: "low_critical",
    LEVEL_LOW: "low",
    LEVEL_NORMAL: "normal",
    LEVEL_HIGH: "high",
    LEVEL_VERY_HIGH: "high_critical",
}

LEVEL_COLOR = {
    LEVEL_VERY_LOW: "#DC2626",   # 红色 - 重度偏低
    LEVEL_LOW: "#F59E0B",        # 黄色 - 偏低
    LEVEL_NORMAL: "#10B981",     # 绿色 - 正常
    LEVEL_HIGH: "#FF8C00",       # 橙色 - 偏高
    LEVEL_VERY_HIGH: "#DC2626",  # 红色 - 重度偏高
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


# [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30 §3.2] 六类型五档阈值表（mmol/L）
# 区间：前闭后开 [low, high)；任何类型 <2.8 一律重度偏低
# scene_code -> (low_max(2->3), normal_max(3->4), high_max(4->5))
# 重度偏低区间：< 2.8
# 偏低区间：[2.8, low_max)
# 正常区间：[low_max, normal_max)
# 偏高区间：[normal_max, high_max)
# 重度偏高区间：>= high_max
SCENE_THRESHOLDS = {
    SCENE_FASTING:        (3.9, 6.1, 7.0),    # 空腹
    SCENE_AFTER_MEAL_1H:  (3.9, 9.0, 11.1),   # 餐后 1h
    SCENE_AFTER_MEAL_2H:  (3.9, 7.8, 11.1),   # 餐后 2h
    SCENE_BEDTIME:        (4.4, 6.7, 10.0),   # 睡前
    SCENE_DAWN:           (3.9, 5.6, 7.0),    # 凌晨
    SCENE_RANDOM:         (3.9, 11.1, 16.7),  # 随机
}


def judge_level(value: float, scene: int) -> int:
    """[PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 根据 6 种测量类型套用五档阈值。

    阈值表见 PRD §3.2。
    """
    # 任何类型 <2.8 一律判为重度偏低
    if value < CRISIS_LOW_THRESHOLD:
        return LEVEL_VERY_LOW

    th = SCENE_THRESHOLDS.get(scene) or SCENE_THRESHOLDS[SCENE_RANDOM]
    low_max, normal_max, high_max = th

    if value < low_max:
        return LEVEL_LOW
    if value < normal_max:
        return LEVEL_NORMAL
    if value < high_max:
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
    """[PRD-GLUCOSE-CARD-OPTIMIZE-V2] 去除"危象"字眼，改为更友好的提示文案。"""
    if crisis == CRISIS_HIGH:
        return (
            f"⚠️ 血糖严重偏高 {value} mmol/L（{SCENE_NAME.get(scene, '随机')}）。"
            "建议立即就医，避免剧烈运动，多喝水。"
        )
    if crisis == CRISIS_LOW:
        return (
            f"⚠️ 血糖严重偏低 {value} mmol/L（{SCENE_NAME.get(scene, '随机')}）。"
            "建议立即补充含糖食物（糖水、糖果、果汁），并尽快联系家人或就医。"
        )
    return ""


# ─── Pydantic Schemas ────────────────────────────────────────────────

class GlucoseRecordCreate(BaseModel):
    value: float = Field(..., description="血糖值 mmol/L，0.5~35.0")
    # [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 同时支持 int (1~6) 与 string key
    scene: Any = Field(..., description="1=空腹 2=餐后2h 3=随机 4=睡前 5=餐后1h 6=凌晨；或字符串 key")
    measure_time: Optional[str] = Field(None, description="测量时间 ISO 字符串，默认当前时间")
    note: Optional[str] = Field(None, max_length=200, description="备注")


def _normalize_scene(value: Any) -> int:
    """[PRD-GLUCOSE-CARD-OPTIMIZE-V2] 将 int / string / None 统一为 int 编码。
    无效或缺失时抛出 HTTPException 400。
    """
    if value is None or value == "":
        raise HTTPException(status_code=400, detail="测量类型必填（period/scene 不能为空）")
    if isinstance(value, bool):  # 避免 True/False 被识别为 int
        raise HTTPException(status_code=400, detail="scene 类型非法")
    if isinstance(value, int):
        if value in SCENE_NAME:
            return value
        raise HTTPException(status_code=400, detail="scene 取值非法（1~6）")
    if isinstance(value, str):
        key = value.strip().lower()
        if key in SCENE_KEY_TO_CODE:
            return SCENE_KEY_TO_CODE[key]
        # 兼容数字字符串
        if key.isdigit() and int(key) in SCENE_NAME:
            return int(key)
        raise HTTPException(status_code=400, detail=f"测量类型非法：{value}")
    raise HTTPException(status_code=400, detail="测量类型类型非法")


class GlucoseRecordOut(BaseModel):
    id: int
    user_id: int
    value: float
    scene: int
    scene_label: str
    # [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 同时返回字符串 key，便于前端使用
    scene_key: str = "random"
    period: str = "random"  # 别名兼容 PRD §5.1.1 接口
    period_label: str = ""
    level: int
    level_key: str = "normal"
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
        return datetime.now()
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
            return datetime.now()


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
    sc = int(scene)
    lv = int(level)
    sk = SCENE_CODE_TO_KEY.get(sc, "random")
    return GlucoseRecordOut(
        id=int(rid),
        user_id=int(uid),
        value=float(value),
        scene=sc,
        scene_label=SCENE_NAME.get(sc, "随机"),
        scene_key=sk,
        period=sk,
        period_label=SCENE_NAME.get(sc, "随机"),
        level=lv,
        level_key=LEVEL_KEY.get(lv, "normal"),
        level_label=LEVEL_LABEL.get(lv, "正常"),
        level_color=LEVEL_COLOR.get(lv, "#10B981"),
        is_crisis=int(is_crisis or 0),
        # [PRD-GLUCOSE-CARD-OPTIMIZE-V2] 去除"危象"字眼
        crisis_label=("严重偏高" if int(is_crisis or 0) == CRISIS_HIGH
                      else "严重偏低" if int(is_crisis or 0) == CRISIS_LOW else ""),
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
                "ct": datetime.now(),
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
    # 字段合法性 — [PRD-GLUCOSE-CARD-OPTIMIZE-V2] 测量类型强制必填，支持 6 种类型
    scene = _normalize_scene(body.scene)
    if body.value is None or body.value < VALUE_MIN or body.value > VALUE_MAX:
        raise HTTPException(status_code=400, detail=f"数值不在合理范围（{VALUE_MIN}~{VALUE_MAX}）")

    value = round(float(body.value), 1)
    measure_time = _parse_measure_time(body.measure_time)
    note = (body.note or "").strip()[:200] or None

    level = judge_level(value, scene)
    is_crisis = judge_crisis(value)

    now = datetime.now()
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

    sk = SCENE_CODE_TO_KEY.get(scene, "random")
    record_out = GlucoseRecordOut(
        id=new_id,
        user_id=current_user.id,
        value=value,
        scene=scene,
        scene_label=SCENE_NAME[scene],
        scene_key=sk,
        period=sk,
        period_label=SCENE_NAME[scene],
        level=level,
        level_key=LEVEL_KEY.get(level, "normal"),
        level_label=LEVEL_LABEL[level],
        level_color=LEVEL_COLOR[level],
        is_crisis=is_crisis,
        crisis_label=("严重偏高" if is_crisis == CRISIS_HIGH
                      else "严重偏低" if is_crisis == CRISIS_LOW else ""),
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
            "alert_label": "严重偏高" if is_crisis == CRISIS_HIGH else "严重偏低",
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
    start = datetime.now() - timedelta(days=days)
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
    start = datetime.now() - timedelta(days=days)
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
    start = datetime.now() - timedelta(days=days)
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
        CRISIS_HIGH: "严重偏高",
        CRISIS_LOW: "严重偏低",
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
    start = datetime.now() - timedelta(days=days)
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
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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


# ─── 路由：当前用户最新血糖（PRD-GLUCOSE-CARD-OPTIMIZE-V1 §卡片对齐血压） ─

@router.get("/latest", response_model=Optional[GlucoseRecordOut])
async def get_latest_record(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GLUCOSE-CARD-OPTIMIZE-V1 2026-05-30] 返回最新一条血糖记录。

    用于健康档案首页【血糖卡片】展示主数值/胶囊/时间·来源。
    若无记录返回 None（HTTP 200 + null body）。
    """
    row = (await db.execute(
        text(
            "SELECT id, user_id, value, scene, level, is_crisis, measure_time, note, create_time "
            "FROM health_glucose_record WHERE user_id=:uid "
            "ORDER BY measure_time DESC, id DESC LIMIT 1"
        ),
        {"uid": current_user.id},
    )).fetchone()
    if not row:
        return None
    return _row_to_record_out(row)


@router.patch("/records/{record_id}/scene", response_model=GlucoseRecordOut)
async def update_record_scene(
    record_id: int,
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §4.6] 修改历史记录测量类型，并重新计算 level / is_crisis。

    Request body: {"scene": 1|2|3|4}
    """
    new_scene = _normalize_scene(payload.get("scene") if "scene" in payload else payload.get("period"))
    row = (await db.execute(
        text(
            "SELECT user_id, value FROM health_glucose_record WHERE id=:rid"
        ),
        {"rid": record_id},
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if int(row[0]) != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该记录")
    value = float(row[1])
    new_level = judge_level(value, new_scene)
    new_crisis = judge_crisis(value)
    await db.execute(
        text(
            "UPDATE health_glucose_record SET scene=:scene, level=:level, is_crisis=:crisis "
            "WHERE id=:rid"
        ),
        {"scene": new_scene, "level": new_level, "crisis": new_crisis, "rid": record_id},
    )
    await db.commit()
    out_row = (await db.execute(
        text(
            "SELECT id, user_id, value, scene, level, is_crisis, measure_time, note, create_time "
            "FROM health_glucose_record WHERE id=:rid"
        ),
        {"rid": record_id},
    )).fetchone()
    return _row_to_record_out(out_row)


# ─── 路由：管理员清空历史血糖数据（PRD §5 物理删除） ────────────────

@router.post("/admin/purge-all")
async def admin_purge_all_glucose_data(
    confirm_token: str = Query(..., description="必填确认令牌：PURGE_ALL_GLUCOSE_2026_05_30"),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GLUCOSE-CARD-OPTIMIZE-V1 2026-05-30 §五] 一次性清空所有用户的历史血糖数据。

    ⚠️ 不可逆。运维操作前需自行做库快照备份。
    出于安全考虑，仅通过 confirm_token 校验防止误调。
    """
    EXPECTED_TOKEN = "PURGE_ALL_GLUCOSE_2026_05_30"
    if confirm_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=403, detail="confirm_token 不匹配")

    # 同步清空：record / alert / 也清掉 health_metric_record 中 metric_type=blood_glucose
    deleted = {"records": 0, "alerts": 0, "metric_records": 0}
    try:
        res = await db.execute(text("DELETE FROM health_glucose_alert"))
        try:
            deleted["alerts"] = int(getattr(res, "rowcount", 0) or 0)
        except Exception:
            pass

        res2 = await db.execute(text("DELETE FROM health_glucose_record"))
        try:
            deleted["records"] = int(getattr(res2, "rowcount", 0) or 0)
        except Exception:
            pass

        # 兼容 v3 metric 表（统一 metric 录入用的 health_metric_record）
        try:
            res3 = await db.execute(
                text("DELETE FROM health_metric_record WHERE metric_type='blood_glucose'")
            )
            try:
                deleted["metric_records"] = int(getattr(res3, "rowcount", 0) or 0)
            except Exception:
                pass
        except Exception as exc:
            logger.warning("[GLUCOSE-V1] purge_metric_records_failed: %s", exc)

        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("[GLUCOSE-V1] purge_failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"清空失败: {exc}")

    logger.warning(
        "[GLUCOSE-V1] ⚠️ admin_purge_all_glucose_data executed: %s", deleted
    )
    return {"purged": True, "counts": deleted, "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


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
        "ut": datetime.now(),
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


# ────────────────────────────────────────────────────────────────────
# [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 完整修改/AI 解读接口
# ────────────────────────────────────────────────────────────────────

class GlucoseRecordUpdate(BaseModel):
    """PRD §5.1.1 修改血糖记录请求体。"""
    value: Optional[float] = None
    scene: Optional[Any] = None    # 兼容 int 或 string key
    period: Optional[Any] = None   # PRD §5.1.1 用 period 字段名
    measure_time: Optional[str] = None
    measured_at: Optional[str] = None  # 别名
    note: Optional[str] = None
    remark: Optional[str] = None       # 别名


@router.put("/records/{record_id}", response_model=GlucoseRecordOut)
async def update_record(
    record_id: int,
    body: GlucoseRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §5.1.1] 完整修改血糖记录（不再以"新增一条"绕过）。

    支持修改 value / scene / measure_time / note，level/is_crisis 自动重算。
    """
    row = (await db.execute(
        text("SELECT user_id, value, scene, measure_time, note "
             "FROM health_glucose_record WHERE id=:rid"),
        {"rid": record_id},
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if int(row[0]) != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该记录")

    # 取新值，未传则保留原值
    new_value = round(float(body.value), 1) if body.value is not None else float(row[1])
    if new_value < VALUE_MIN or new_value > VALUE_MAX:
        raise HTTPException(status_code=400, detail=f"数值不在合理范围（{VALUE_MIN}~{VALUE_MAX}）")

    scene_input = body.scene if body.scene is not None else body.period
    if scene_input is not None:
        new_scene = _normalize_scene(scene_input)
    else:
        new_scene = int(row[2])

    mt_str = body.measure_time or body.measured_at
    new_mt = _parse_measure_time(mt_str) if mt_str else row[3]

    note_val = body.note if body.note is not None else body.remark
    new_note = (note_val.strip()[:200] if note_val else (row[4] if note_val is None else None)) or None

    new_level = judge_level(new_value, new_scene)
    new_crisis = judge_crisis(new_value)

    await db.execute(
        text(
            "UPDATE health_glucose_record SET value=:v, scene=:s, level=:l, "
            "is_crisis=:c, measure_time=:mt, note=:n WHERE id=:rid"
        ),
        {
            "v": new_value, "s": new_scene, "l": new_level, "c": new_crisis,
            "mt": new_mt, "n": new_note, "rid": record_id,
        },
    )
    await db.commit()

    out_row = (await db.execute(
        text("SELECT id, user_id, value, scene, level, is_crisis, measure_time, note, create_time "
             "FROM health_glucose_record WHERE id=:rid"),
        {"rid": record_id},
    )).fetchone()
    return _row_to_record_out(out_row)


# ────────────────────────────────────────────────────────────────────
# [PRD §6] AI 解读 - 单次 / 趋势
# ────────────────────────────────────────────────────────────────────

class AiExplainSingleRequest(BaseModel):
    record_id: int
    profile_id: Optional[int] = None


class AiExplainTrendRequest(BaseModel):
    range: str = Field("7d", description="7d / 14d / 30d")
    profile_id: Optional[int] = None


def _range_to_days(rng: str) -> int:
    rng = (rng or "7d").lower().strip()
    if rng in ("today", "1d"):
        return 1
    if rng in ("7d", "week"):
        return 7
    if rng in ("14d", "two_weeks"):
        return 14
    if rng in ("30d", "month"):
        return 30
    try:
        return max(1, min(90, int(rng.rstrip("d"))))
    except Exception:
        return 7


def _fallback_single_explain(value: float, scene: int, level: int) -> str:
    """[PRD §7.2] 大模型不可用时的规则文案降级。"""
    cn = SCENE_NAME.get(scene, "随机")
    label = LEVEL_LABEL.get(level, "正常")
    base = f"本次血糖 {value} mmol/L，属于{cn}「{label}」。"
    if level == LEVEL_NORMAL:
        return base + "属于正常范围。建议：保持规律饮食与适量运动，继续按当前节奏监测。"
    if level == LEVEL_LOW:
        return base + "数值略低于推荐范围。建议：立即少量补充含糖食物（糖水/果汁），15 分钟后复测。"
    if level == LEVEL_HIGH:
        return base + "数值略高于推荐范围。建议：减少精制主食与含糖饮料，餐后 30 分钟散步 20 分钟，2 小时后复测。"
    if level == LEVEL_VERY_LOW:
        return base + "数值明显偏低，需要立即处理。建议：立即补糖，必要时联系家人或拨打 120。"
    return base + "数值明显偏高，建议尽快就医评估。可多饮温水，避免剧烈运动。"


def _fallback_trend_explain(days: int, rows: List[Any]) -> Dict[str, str]:
    if not rows:
        return {
            "summary": f"近 {days} 天暂无血糖记录。",
            "trend": "数据不足，无法分析趋势。",
            "advice": "建议每周至少记录 3 次空腹与餐后血糖，便于评估。",
        }
    vals = [float(r[0]) for r in rows]
    levels = [int(r[2]) for r in rows]
    avg = round(sum(vals) / len(vals), 2)
    mn = round(min(vals), 1)
    mx = round(max(vals), 1)
    target_n = sum(1 for lv in levels if lv == LEVEL_NORMAL)
    rate = round(target_n * 100 / len(rows), 1)
    high_scene_count: Dict[int, int] = {}
    for r in rows:
        if int(r[2]) in (LEVEL_HIGH, LEVEL_VERY_HIGH):
            sc = int(r[1])
            high_scene_count[sc] = high_scene_count.get(sc, 0) + 1
    top_scene = ""
    if high_scene_count:
        sc, _n = max(high_scene_count.items(), key=lambda kv: kv[1])
        top_scene = SCENE_NAME.get(sc, "")
    summary = (
        f"近 {days} 天共记录 {len(rows)} 次，平均 {avg} mmol/L，"
        f"波动范围 {mn}~{mx} mmol/L，达标率约 {rate}%。"
    )
    trend = (
        f"整体呈相对稳定状态。" if rate >= 80
        else f"波动偏大，偏高时段最常出现于「{top_scene or '餐后'}」。"
    )
    advice = (
        "建议：1) 三餐定时定量；2) 减少精制主食与含糖饮料；"
        "3) 每天散步 30 分钟；4) 每周至少 3 次空腹+餐后监测；"
        "5) 如近期持续偏高请尽快就诊。"
    )
    return {"summary": summary, "trend": trend, "advice": advice}


async def _load_glucose_prompt(db: AsyncSession, prompt_key: str) -> Optional[str]:
    """[PRD §8.4] 从 ai_prompt_config 表读取已发布的提示词。

    若表不存在或未配置则返回 None，由调用方走降级。
    """
    try:
        row = (await db.execute(
            text(
                "SELECT content FROM ai_prompt_config "
                "WHERE prompt_key=:k AND status=1 ORDER BY version DESC LIMIT 1"
            ),
            {"k": prompt_key},
        )).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception as exc:
        logger.debug("[GLUCOSE-AI] load_prompt_failed key=%s err=%s", prompt_key, exc)
    return None


async def _call_ai_with_timeout(prompt_text: str, timeout_s: float = 3.0) -> Optional[str]:
    """[PRD §7.2] 调用大模型，3s 超时即降级。

    复用 app.services.ai_service.call_ai_model 的标准签名：
        messages: List[Dict[str, str]], system_prompt: str = "", ...
    """
    import asyncio
    try:
        from app.services.ai_service import call_ai_model  # type: ignore
    except Exception:
        return None
    try:
        messages = [{"role": "user", "content": prompt_text}]
        result = await asyncio.wait_for(
            call_ai_model(messages=messages, system_prompt=""),
            timeout=timeout_s,
        )
        if isinstance(result, str):
            txt = result
        elif isinstance(result, dict):
            txt = result.get("content") or result.get("text") or ""
        else:
            txt = str(result) if result else ""
        if not txt or "未配置" in txt or "未配置AI" in txt:
            return None
        return txt
    except asyncio.TimeoutError:
        logger.warning("[GLUCOSE-AI] call timeout, fallback to rules")
        return None
    except Exception as exc:
        logger.warning("[GLUCOSE-AI] call_failed: %s", exc)
        return None


# 简单进程内缓存（生产环境可替换为 Redis）
_ai_cache: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str, ttl_s: int) -> Optional[Dict[str, Any]]:
    item = _ai_cache.get(key)
    if not item:
        return None
    if ttl_s > 0 and (datetime.now().timestamp() - item.get("_ts", 0)) > ttl_s:
        _ai_cache.pop(key, None)
        return None
    return item


def _cache_set(key: str, data: Dict[str, Any]) -> None:
    data["_ts"] = datetime.now().timestamp()
    _ai_cache[key] = data


PROMPT_VERSION = "v3"


@router.post("/ai-explain-single")
async def ai_explain_single(
    body: AiExplainSingleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §5.1.3] AI 解读单次血糖。

    Response 字段：from_cache / model / prompt_version / content / generated_at
    """
    # 1) 读记录
    row = (await db.execute(
        text("SELECT id, user_id, value, scene, level, is_crisis, measure_time, note, create_time "
             "FROM health_glucose_record WHERE id=:rid"),
        {"rid": body.record_id},
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if int(row[1]) != current_user.id:
        raise HTTPException(status_code=403, detail="无权解读该记录")

    rec = _row_to_record_out(row)

    cache_key = f"glucose:ai:single:{rec.id}:{PROMPT_VERSION}"
    cached = _cache_get(cache_key, ttl_s=0)  # 永久缓存
    if cached:
        return {"code": 0, "data": {
            "from_cache": True, "model": cached.get("model", "rules"),
            "prompt_version": PROMPT_VERSION,
            "content": cached["content"],
            "generated_at": cached.get("generated_at"),
        }}

    # 2) 装填提示词
    prompt_tpl = await _load_glucose_prompt(db, "glucose_single_explain")
    if not prompt_tpl:
        prompt_tpl = DEFAULT_SINGLE_PROMPT

    # 用户信息（性别/年龄/糖尿病史） — 尽力而为
    gender = getattr(current_user, "gender", None) or "未填"
    age = getattr(current_user, "age", None) or "未填"
    has_diabetes = "未知"

    prompt_text = (
        prompt_tpl
        .replace("{gender}", str(gender))
        .replace("{age}", str(age))
        .replace("{has_diabetes}", str(has_diabetes))
        .replace("{value}", str(rec.value))
        .replace("{period_label}", rec.period_label)
        .replace("{measured_at}", rec.measure_time)
        .replace("{level_label}", rec.level_label)
    )

    # 3) 调用大模型（3s 超时）
    ai_text = await _call_ai_with_timeout(prompt_text)

    used_model = "qwen-max"
    if not ai_text:
        ai_text = _fallback_single_explain(rec.value, rec.scene, rec.level)
        used_model = "rules-fallback"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "from_cache": False,
        "model": used_model,
        "prompt_version": PROMPT_VERSION,
        "content": ai_text,
        "generated_at": now_str,
    }
    _cache_set(cache_key, {"content": ai_text, "model": used_model, "generated_at": now_str})
    return {"code": 0, "data": payload}


@router.post("/ai-explain-trend")
async def ai_explain_trend(
    body: AiExplainTrendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §5.1.4] AI 解读血糖趋势。"""
    days = _range_to_days(body.range)
    start = datetime.now() - timedelta(days=days)

    rows = (await db.execute(
        text(
            "SELECT value, scene, level, measure_time FROM health_glucose_record "
            "WHERE user_id=:uid AND measure_time>=:start "
            "ORDER BY measure_time DESC LIMIT 200"
        ),
        {"uid": current_user.id, "start": start},
    )).fetchall()

    cache_key = f"glucose:ai:trend:{current_user.id}:{days}:{PROMPT_VERSION}"
    cached = _cache_get(cache_key, ttl_s=300)  # 5 min 缓存
    if cached:
        return {"code": 0, "data": {
            "from_cache": True,
            "model": cached.get("model", "rules"),
            "prompt_version": PROMPT_VERSION,
            "summary": cached["summary"],
            "trend": cached["trend"],
            "advice": cached["advice"],
            "generated_at": cached.get("generated_at"),
        }}

    prompt_tpl = await _load_glucose_prompt(db, "glucose_trend_explain")
    if not prompt_tpl:
        prompt_tpl = DEFAULT_TREND_PROMPT

    gender = getattr(current_user, "gender", None) or "未填"
    age = getattr(current_user, "age", None) or "未填"
    records_text = "\n".join([
        f"- {_fmt_dt(r[3])} {SCENE_NAME.get(int(r[1]), '随机')} {float(r[0])} mmol/L ({LEVEL_LABEL.get(int(r[2]), '正常')})"
        for r in rows[:60]
    ]) or "（无记录）"

    prompt_text = (
        prompt_tpl
        .replace("{range}", f"{days}天")
        .replace("{gender}", str(gender))
        .replace("{age}", str(age))
        .replace("{has_diabetes}", "未知")
        .replace("{records_json}", records_text)
    )

    ai_text = await _call_ai_with_timeout(prompt_text)
    used_model = "qwen-max"
    summary = trend = advice = ""
    if ai_text:
        # 尝试 JSON 解析
        try:
            import json as _json
            # 容错：去除 ```json 包裹
            s = ai_text.strip()
            if s.startswith("```"):
                s = s.strip("`")
                if s.startswith("json"):
                    s = s[4:]
            data = _json.loads(s)
            summary = str(data.get("summary", ""))[:500]
            trend = str(data.get("trend", ""))[:500]
            advice = str(data.get("advice", ""))[:1000]
        except Exception:
            summary = ai_text[:500]
            trend = ""
            advice = ""

    if not summary:
        # 降级
        rule = _fallback_trend_explain(days, rows)
        summary, trend, advice = rule["summary"], rule["trend"], rule["advice"]
        used_model = "rules-fallback"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _cache_set(cache_key, {
        "summary": summary, "trend": trend, "advice": advice,
        "model": used_model, "generated_at": now_str,
    })
    return {"code": 0, "data": {
        "from_cache": False,
        "model": used_model,
        "prompt_version": PROMPT_VERSION,
        "summary": summary,
        "trend": trend,
        "advice": advice,
        "generated_at": now_str,
    }}


# [PRD §6.1/6.2] 默认提示词（同时作为 ai_prompt_config 初始化数据）
DEFAULT_SINGLE_PROMPT = """你是一名资深内分泌科医生兼健康管理师，请根据以下用户的本次血糖测量结果，给出一段 80–150 字的通俗易懂的解读，
要求：
1. 用中文，老人也能看懂；
2. 第一句先复述本次结果（数值 + 测量类型 + 状态档位）；
3. 第二句解释为什么是这个档位，结合医学常识；
4. 第三句给出 1–2 条具体可执行的建议（饮食/运动/复测/就医）；
5. 不要使用"危象"等吓人字眼；
6. 不要给出诊断结论，只能给出建议。

【用户基本信息】
- 性别：{gender}
- 年龄：{age}
- 是否糖尿病史：{has_diabetes}

【本次血糖】
- 数值：{value} mmol/L
- 测量类型：{period_label}
- 测量时间：{measured_at}
- 状态档位：{level_label}

请直接输出解读文本，不要任何前缀。"""


DEFAULT_TREND_PROMPT = """你是一名资深内分泌科医生兼健康管理师，请根据以下用户最近 {range} 的血糖记录，输出三段文本：

【summary】（2–3 句）：总体情况概括，包括平均值、波动范围、达标率。
【trend】（2–3 句）：趋势分析，是稳定/上升/下降/波动大，并指出最常出现偏高的测量类型。
【advice】（3–5 条）：针对性建议，每条 1 句，覆盖饮食、运动、监测频率、就医建议。

要求：
1. 中文，通俗易懂；
2. 不要使用"危象"等吓人字眼；
3. 不要给出诊断结论。

【用户基本信息】
- 性别：{gender}
- 年龄：{age}
- 是否糖尿病史：{has_diabetes}

【最近 {range} 血糖记录】
{records_json}

请按以下 JSON 格式严格输出（不要 markdown 代码块包裹）：
{"summary": "...", "trend": "...", "advice": "..."}"""


# ────────────────────────────────────────────────────────────────────
# [PRD §8] AI 提示词配置（管理后台 CRUD + 版本）
# ────────────────────────────────────────────────────────────────────

GLUCOSE_PROMPT_KEYS = ("glucose_single_explain", "glucose_trend_explain")
GLUCOSE_PROMPT_NAMES = {
    "glucose_single_explain": "血糖_单次解读",
    "glucose_trend_explain": "血糖_趋势解读",
}


async def _ensure_glucose_prompts(db: AsyncSession) -> None:
    """[PRD §8.5] 部署时自动 insert 两条记录，幂等。"""
    defaults = {
        "glucose_single_explain": DEFAULT_SINGLE_PROMPT,
        "glucose_trend_explain": DEFAULT_TREND_PROMPT,
    }
    try:
        for key, content in defaults.items():
            row = (await db.execute(
                text("SELECT id FROM ai_prompt_config WHERE prompt_key=:k"),
                {"k": key},
            )).fetchone()
            if row:
                continue
            await db.execute(
                text(
                    "INSERT INTO ai_prompt_config "
                    "(prompt_key, name, content, version, status, model_key, "
                    " updated_by, updated_at, created_at) "
                    "VALUES (:k, :n, :c, 1, 1, NULL, 'system', :ct, :ct)"
                ),
                {
                    "k": key, "n": GLUCOSE_PROMPT_NAMES[key],
                    "c": content, "ct": datetime.now(),
                },
            )
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        logger.warning("[GLUCOSE-AI] ensure_prompts_failed: %s", exc)


@router.get("/admin/ai-prompts")
async def admin_list_prompts(
    db: AsyncSession = Depends(get_db),
):
    """[PRD §8.2] 列表页（仅返回血糖两条）。"""
    await _ensure_glucose_prompts(db)
    rows = (await db.execute(
        text(
            "SELECT id, prompt_key, name, content, version, status, "
            "       model_key, updated_by, updated_at "
            "FROM ai_prompt_config WHERE prompt_key IN "
            "('glucose_single_explain','glucose_trend_explain')"
        ),
    )).fetchall()
    items = [{
        "id": int(r[0]), "prompt_key": r[1], "name": r[2], "content": r[3],
        "version": int(r[4] or 1), "status": int(r[5] or 1),
        "model_key": r[6], "updated_by": r[7],
        "updated_at": _fmt_dt(r[8]),
    } for r in rows]
    return {"code": 0, "data": {"items": items}}


class PromptUpdateRequest(BaseModel):
    content: str
    name: Optional[str] = None
    updated_by: Optional[str] = None


@router.put("/admin/ai-prompts/{prompt_key}")
async def admin_update_prompt(
    prompt_key: str,
    body: PromptUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """[PRD §8.3] 编辑/发布新版本。"""
    if prompt_key not in GLUCOSE_PROMPT_KEYS:
        raise HTTPException(status_code=400, detail="prompt_key 非法")
    await _ensure_glucose_prompts(db)
    cur = (await db.execute(
        text("SELECT id, version FROM ai_prompt_config WHERE prompt_key=:k"),
        {"k": prompt_key},
    )).fetchone()
    if not cur:
        raise HTTPException(status_code=404, detail="提示词不存在")
    new_ver = int(cur[1] or 1) + 1
    # 历史快照
    try:
        old_content = (await db.execute(
            text("SELECT content FROM ai_prompt_config WHERE id=:i"),
            {"i": int(cur[0])},
        )).scalar() or ""
        await db.execute(
            text(
                "INSERT INTO ai_prompt_config_history "
                "(prompt_key, version, content, updated_by, updated_at) "
                "VALUES (:k, :v, :c, :u, :t)"
            ),
            {
                "k": prompt_key, "v": int(cur[1] or 1),
                "c": old_content,
                "u": body.updated_by or "admin",
                "t": datetime.now(),
            },
        )
    except Exception as exc:
        logger.debug("[GLUCOSE-AI] history snapshot failed: %s", exc)

    await db.execute(
        text(
            "UPDATE ai_prompt_config SET content=:c, name=COALESCE(:n, name), "
            "version=:v, status=1, updated_by=:u, updated_at=:t WHERE prompt_key=:k"
        ),
        {
            "c": body.content, "n": body.name, "v": new_ver,
            "u": body.updated_by or "admin", "t": datetime.now(),
            "k": prompt_key,
        },
    )
    await db.commit()
    # 清掉缓存
    keys_to_del = [k for k in list(_ai_cache.keys())
                   if k.startswith(f"glucose:ai:{'single' if prompt_key == 'glucose_single_explain' else 'trend'}:")]
    for k in keys_to_del:
        _ai_cache.pop(k, None)
    return {"code": 0, "data": {"prompt_key": prompt_key, "version": new_ver}}


class PromptTestRequest(BaseModel):
    content: str
    test_value: Optional[float] = 8.0
    test_scene: Optional[str] = "after_meal_2h"


@router.post("/admin/ai-prompts/{prompt_key}/test")
async def admin_test_prompt(
    prompt_key: str,
    body: PromptTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """[PRD §8.3] 测试调用：用给定提示词内容渲染样例数据并调用大模型。"""
    if prompt_key not in GLUCOSE_PROMPT_KEYS:
        raise HTTPException(status_code=400, detail="prompt_key 非法")

    if prompt_key == "glucose_single_explain":
        scene = _normalize_scene(body.test_scene or "after_meal_2h")
        value = float(body.test_value or 8.0)
        level = judge_level(value, scene)
        prompt_text = (
            body.content
            .replace("{gender}", "男")
            .replace("{age}", "62")
            .replace("{has_diabetes}", "是")
            .replace("{value}", str(value))
            .replace("{period_label}", SCENE_NAME.get(scene, "随机"))
            .replace("{measured_at}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            .replace("{level_label}", LEVEL_LABEL.get(level, "正常"))
        )
        ai_text = await _call_ai_with_timeout(prompt_text, timeout_s=6.0)
        if not ai_text:
            ai_text = _fallback_single_explain(value, scene, level) + "\n（注：当前为规则降级，未调用大模型）"
        return {"code": 0, "data": {"output": ai_text, "rendered_prompt": prompt_text}}

    # trend
    sample_records = "\n".join([
        "- 2026-05-29 07:30 空腹 6.4 mmol/L (偏高)",
        "- 2026-05-29 09:30 餐后1h 9.8 mmol/L (偏高)",
        "- 2026-05-28 21:00 睡前 5.8 mmol/L (正常)",
    ])
    prompt_text = (
        body.content
        .replace("{range}", "7天")
        .replace("{gender}", "男")
        .replace("{age}", "62")
        .replace("{has_diabetes}", "是")
        .replace("{records_json}", sample_records)
    )
    ai_text = await _call_ai_with_timeout(prompt_text, timeout_s=6.0)
    if not ai_text:
        ai_text = (
            '{"summary":"测试样例 - 近 7 天平均 7.3，达标率 33%",'
            '"trend":"波动偏大，偏高集中在餐后1h",'
            '"advice":"减少精制主食；散步 30 分钟；3 次/周监测"}'
            "\n（注：当前为规则降级，未调用大模型）"
        )
    return {"code": 0, "data": {"output": ai_text, "rendered_prompt": prompt_text}}
