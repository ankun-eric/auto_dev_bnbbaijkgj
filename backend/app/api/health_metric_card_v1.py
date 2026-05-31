"""[PRD-HEALTH-METRIC-CARD-UNIFY-V1 2026-05-31] 健康指标卡片统一改造（血压/血糖/心率/血氧）

接口前缀: /api/health-metric-v1

本期目标（PRD §一/二）：
- 提供四指标（blood_pressure / blood_glucose / heart_rate / spo2）通用历史接口（含筛选+分页）
- 提供四指标通用「本次解读 / 趋势解读」AI 入口（每个指标专属 prompt + 规则兜底）
- 历史记录修改/删除沿用现有 health-profile-v3 PUT/DELETE 接口
- 严格只允许操作 `source = manual` 的记录（PRD §4.3 设备同步数据为只读）

补充字段（不破坏 health-profile-v3 既有接口）：
- 列表项新增 `editable` 字段：true 表示 source=manual 可改可删，false 表示设备同步只读
- 列表项新增 `status` 字段：基于数值 + metric_type 计算出的状态档位（low/normal/mild_high/.../severe_low 等）

数据表：复用 `health_metric_record`（含 spo2 类型）；血糖另外双写 `health_glucose_record`（既有 glucose-v1）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.health_v3 import HealthMetricRecord
from app.models.models import HealthProfile, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health-metric-v1", tags=["PRD-HEALTH-METRIC-CARD-V1 健康指标统一"])


# ─── 元数据 ───────────────────────────────────────────────────────────

METRIC_TYPES = {"blood_pressure", "blood_glucose", "heart_rate", "spo2"}

METRIC_META: Dict[str, Dict[str, Any]] = {
    "blood_pressure": {
        "label": "血压",
        "unit": "mmHg",
        "principal": "systolic",
        "secondary": "diastolic",
        "scene_options": ["晨起", "睡前", "服药后", "运动后", "其他"],
    },
    "blood_glucose": {
        "label": "血糖",
        "unit": "mmol/L",
        "principal": "value",
        "secondary": None,
        "scene_options": ["空腹", "餐前", "餐后2h", "睡前", "随机", "凌晨"],
    },
    "heart_rate": {
        "label": "心率",
        "unit": "bpm",
        "principal": "value",
        "secondary": None,
        "scene_options": ["静息", "运动后", "睡眠中", "其他"],
    },
    "spo2": {
        "label": "血氧",
        "unit": "%",
        "principal": "value",
        "secondary": None,
        "scene_options": ["静息", "运动后", "睡眠中", "自定义"],
    },
}


# ─── 状态档位判定 ────────────────────────────────────────────────────

def _judge_status(metric_type: str, value: Dict[str, Any]) -> Dict[str, str]:
    """根据指标类型 + 值返回 {key, label, color}。"""
    try:
        if metric_type == "blood_pressure":
            sbp = float(value.get("systolic") or 0)
            dbp = float(value.get("diastolic") or 0)
            if sbp == 0 and dbp == 0:
                return {"key": "unknown", "label": "未知", "color": "gray"}
            if sbp < 90 or dbp < 60:
                return {"key": "low", "label": "偏低", "color": "orange"}
            if sbp >= 160 or dbp >= 100:
                return {"key": "severe_high", "label": "严重偏高", "color": "orange"}
            if sbp >= 140 or dbp >= 90:
                return {"key": "mid_high", "label": "中度偏高", "color": "yellow"}
            if sbp >= 120 or dbp >= 80:
                return {"key": "mild_high", "label": "轻度偏高", "color": "yellow"}
            return {"key": "normal", "label": "正常", "color": "blue"}

        if metric_type == "blood_glucose":
            v = float(value.get("value") or 0)
            period = str(value.get("period") or value.get("scene") or "").lower()
            if v == 0:
                return {"key": "unknown", "label": "未知", "color": "gray"}
            if v < 3.9:
                return {"key": "low", "label": "偏低", "color": "orange"}
            if v >= 16.7:
                return {"key": "severe_high", "label": "严重偏高", "color": "red"}
            is_fasting = "fasting" in period or "空腹" in str(value.get("period") or "")
            if is_fasting:
                if v > 7.0:
                    return {"key": "mid_high", "label": "偏高", "color": "yellow"}
            else:
                if v > 11.1:
                    return {"key": "mid_high", "label": "偏高", "color": "yellow"}
            return {"key": "normal", "label": "正常", "color": "blue"}

        if metric_type == "heart_rate":
            # [PRD-HEART-RATE-DETAIL-RULE-V1 2026-05-31] 统一标准 正常范围 60–100 次/分
            # < 60 偏慢 / 60~100（含边界）正常 / > 100 偏快
            v = float(value.get("value") or 0)
            if v == 0:
                return {"key": "unknown", "label": "未知", "color": "gray"}
            if v < 60:
                return {"key": "slow", "label": "偏慢", "color": "orange"}
            if v > 100:
                return {"key": "fast", "label": "偏快", "color": "orange"}
            return {"key": "normal", "label": "正常", "color": "blue"}

        if metric_type == "spo2":
            v = float(value.get("value") or 0)
            if v == 0:
                return {"key": "unknown", "label": "未知", "color": "gray"}
            if v < 85:
                return {"key": "severe_low", "label": "严重偏低", "color": "red"}
            if v < 90:
                return {"key": "mid_low", "label": "较低", "color": "orange"}
            if v < 95:
                return {"key": "mild_low", "label": "偏低", "color": "yellow"}
            return {"key": "normal", "label": "正常", "color": "blue"}
    except Exception:
        pass
    return {"key": "unknown", "label": "未知", "color": "gray"}


# ─── 工具函数 ────────────────────────────────────────────────────────

async def _verify_profile_access(
    db: AsyncSession, profile_id: int, user: User
) -> HealthProfile:
    res = await db.execute(select(HealthProfile).where(HealthProfile.id == profile_id))
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")
    if profile.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该档案")
    return profile


def _record_to_item(r: HealthMetricRecord) -> Dict[str, Any]:
    vjson = r.value_json or {}
    status = _judge_status(r.metric_type, vjson)
    is_manual = (r.source or "manual") == "manual"
    return {
        "id": r.id,
        "profile_id": r.profile_id,
        "metric_type": r.metric_type,
        "value": vjson,
        "source": r.source,
        "scene": vjson.get("period") or vjson.get("scene") or vjson.get("activity") or None,
        "note": vjson.get("note") or vjson.get("remark") or "",
        "measured_at": r.measured_at.isoformat() if r.measured_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "editable": is_manual,
        "status": status,
    }


# ─── 历史记录（含筛选 + 分页）─────────────────────────────────────────

@router.get("/{profile_id}/{metric_type}/history")
async def get_history_with_filters(
    profile_id: int,
    metric_type: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_range: Optional[str] = Query(None, description="7d/30d/90d/custom"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD（custom 时使用）"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD（custom 时使用）"),
    status: Optional[str] = Query(None, description="状态档位 key，逗号分隔，all 表示全部"),
    scene: Optional[str] = Query(None, description="测量场景，逗号分隔，all 表示全部"),
    source: Optional[str] = Query(None, description="来源：manual / device / all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §五] 全部历史页接口：支持四种筛选 + 分页。"""
    if metric_type not in METRIC_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 metric_type: {metric_type}")
    await _verify_profile_access(db, profile_id, current_user)

    # 1) 时间范围
    now = datetime.utcnow()
    range_start: Optional[datetime] = None
    range_end: Optional[datetime] = None
    if date_range == "7d":
        range_start = now - timedelta(days=7)
    elif date_range == "30d":
        range_start = now - timedelta(days=30)
    elif date_range == "90d":
        range_start = now - timedelta(days=90)
    elif date_range == "custom" or start_date or end_date:
        if start_date:
            try:
                range_start = datetime.strptime(start_date, "%Y-%m-%d")
            except Exception:
                raise HTTPException(status_code=400, detail="start_date 格式应为 YYYY-MM-DD")
        if end_date:
            try:
                d = datetime.strptime(end_date, "%Y-%m-%d")
                range_end = d + timedelta(days=1)  # 包含当天
            except Exception:
                raise HTTPException(status_code=400, detail="end_date 格式应为 YYYY-MM-DD")

    # 2) 基础查询
    where = [
        HealthMetricRecord.profile_id == profile_id,
        HealthMetricRecord.metric_type == metric_type,
    ]
    if range_start:
        where.append(HealthMetricRecord.measured_at >= range_start)
    if range_end:
        where.append(HealthMetricRecord.measured_at < range_end)

    # 3) 来源筛选
    source_filter = (source or "all").strip().lower()
    if source_filter == "manual":
        where.append(HealthMetricRecord.source == "manual")
    elif source_filter == "device":
        where.append(HealthMetricRecord.source != "manual")

    # 4) 总数 + 列表（多取一些用于内存筛选 status / scene）
    # 为了支持 status 和 scene 这种基于 JSON 内容的筛选，我们先按时间倒序拉取一批再过滤
    base_stmt = (
        select(HealthMetricRecord)
        .where(*where)
        .order_by(HealthMetricRecord.measured_at.desc())
    )
    # 简化策略：先全量拉满 1000 条做内存过滤（量级合理）；后续可下沉到 SQL JSON 表达式
    all_rows = list((await db.execute(base_stmt.limit(1000))).scalars().all())

    # 5) 内存过滤
    status_keys = set(
        s.strip() for s in (status or "all").split(",") if s.strip() and s.strip() != "all"
    )
    scene_set = set(
        s.strip() for s in (scene or "all").split(",") if s.strip() and s.strip() != "all"
    )

    filtered: List[HealthMetricRecord] = []
    for r in all_rows:
        item_status = _judge_status(r.metric_type, r.value_json or {})
        if status_keys and item_status["key"] not in status_keys:
            continue
        if scene_set:
            sc = (r.value_json or {}).get("period") or (r.value_json or {}).get("scene") \
                or (r.value_json or {}).get("activity")
            if sc not in scene_set:
                continue
        filtered.append(r)

    total = len(filtered)
    offset = (page - 1) * page_size
    page_rows = filtered[offset:offset + page_size]
    items = [_record_to_item(r) for r in page_rows]

    return {
        "code": 0,
        "data": {
            "metric_type": metric_type,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + len(page_rows) < total,
            "items": items,
            "meta": METRIC_META.get(metric_type, {}),
        },
    }


# ─── 删除前权限校验（手工录入 only）覆盖 ──────────────────────────────

class DeleteCheckResponse(BaseModel):
    can_delete: bool
    reason: str = ""
    record_summary: Optional[Dict[str, Any]] = None


@router.get("/{profile_id}/{metric_type}/{record_id}/can-delete", response_model=DeleteCheckResponse)
async def can_delete_record(
    profile_id: int,
    metric_type: str,
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §4.3/4.5] 删除前权限检查 + 二次确认弹窗信息回显。"""
    if metric_type not in METRIC_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 metric_type: {metric_type}")
    await _verify_profile_access(db, profile_id, current_user)

    rec = (await db.execute(
        select(HealthMetricRecord).where(
            HealthMetricRecord.id == record_id,
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
        )
    )).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")

    is_manual = (rec.source or "manual") == "manual"
    summary = _record_to_item(rec)
    if not is_manual:
        return DeleteCheckResponse(
            can_delete=False,
            reason="该记录来自智能设备同步，数据已锁定，无法删除",
            record_summary=summary,
        )
    return DeleteCheckResponse(can_delete=True, record_summary=summary)


# ─── AI 解读：本次 + 趋势 ─────────────────────────────────────────────

class AiExplainSingleRequest(BaseModel):
    record_id: int = Field(..., description="目标记录 id")


class AiExplainTrendRequest(BaseModel):
    range: str = Field("7d", description="7d / 30d / 90d")


def _rule_explain_single(metric_type: str, rec: HealthMetricRecord) -> str:
    """规则降级文案——AI 接口失败时使用。"""
    vjson = rec.value_json or {}
    meta = METRIC_META[metric_type]
    status = _judge_status(metric_type, vjson)
    unit = meta["unit"]
    scene = vjson.get("period") or vjson.get("scene") or vjson.get("activity") or ""
    scene_part = f"（{scene}）" if scene else ""

    if metric_type == "blood_pressure":
        sbp = vjson.get("systolic") or "-"
        dbp = vjson.get("diastolic") or "-"
        head = f"本次血压{scene_part} {sbp}/{dbp} {unit}，状态：{status['label']}。"
    else:
        v = vjson.get("value")
        head = f"本次{meta['label']}{scene_part} {v} {unit}，状态：{status['label']}。"

    advice_map = {
        "normal": "数值正常，建议保持当前生活节奏，定期监测。",
        "low": "数值偏低，建议关注休息、营养摄入，若持续偏低请咨询医生。",
        "high": "数值偏高，建议减少高盐/精制糖摄入，加强适度有氧运动，定期复测。",
        "mild_high": "轻度偏高，建议清淡饮食、规律作息、监测变化趋势。",
        "mid_high": "中度偏高，建议咨询医生是否调整用药/复测密度。",
        "severe_high": "数值明显偏高，建议尽快就医评估，避免剧烈活动。",
        "mild_low": "轻度偏低，建议深呼吸放松、避免过度疲劳，必要时复测。",
        "mid_low": "较低，建议立即停止剧烈活动并休息，必要时就医。",
        "severe_low": "严重偏低，建议立即就医。",
        "unknown": "暂无足够数据评估，请继续记录监测。",
    }
    advice = advice_map.get(status["key"], "请保持监测，必要时咨询医生。")
    return f"{head} {advice}\n\n⚠️ 本提示仅供参考，不能替代专业医生诊断。"


def _rule_explain_trend(metric_type: str, records: List[HealthMetricRecord], days: int) -> Dict[str, str]:
    meta = METRIC_META[metric_type]
    if not records:
        return {
            "summary": f"近 {days} 天暂无{meta['label']}数据。",
            "trend": "建议规律记录，至少每周 3 次。",
            "advice": "可点击「手工录入」或「绑定设备」开始记录。",
        }

    values: List[float] = []
    abnormal = 0
    for r in records:
        vjson = r.value_json or {}
        try:
            if metric_type == "blood_pressure":
                v = float(vjson.get("systolic") or 0)
            else:
                v = float(vjson.get("value") or 0)
            if v > 0:
                values.append(v)
            if _judge_status(r.metric_type, vjson)["key"] != "normal":
                abnormal += 1
        except Exception:
            continue
    if not values:
        return {
            "summary": f"近 {days} 天共 {len(records)} 条记录，但数值无效。",
            "trend": "请检查数据录入。",
            "advice": "建议重新录入。",
        }
    avg = sum(values) / len(values)
    vmin = min(values)
    vmax = max(values)
    abnormal_rate = round(abnormal / max(len(records), 1) * 100)

    summary = (
        f"近 {days} 天共 {len(records)} 条{meta['label']}记录，"
        f"平均 {avg:.1f} {meta['unit']}，最低 {vmin}，最高 {vmax}，"
        f"异常占比约 {abnormal_rate}%。"
    )
    trend = "数值整体" + ("波动较大，请关注" if (vmax - vmin) > avg * 0.3 else "较为平稳") + "。"
    advice = (
        "建议保持每日同一时段测量、记录用药及饮食变化；如异常占比超过 30%，请尽快咨询医生。"
    )
    return {"summary": summary, "trend": trend, "advice": advice}


@router.post("/{profile_id}/{metric_type}/ai-explain-single")
async def ai_explain_single(
    profile_id: int,
    metric_type: str,
    body: AiExplainSingleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §七] 本次解读（统一入口，按指标分发）。"""
    if metric_type not in METRIC_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 metric_type: {metric_type}")
    await _verify_profile_access(db, profile_id, current_user)

    rec = (await db.execute(
        select(HealthMetricRecord).where(
            HealthMetricRecord.id == body.record_id,
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
        )
    )).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")

    content = _rule_explain_single(metric_type, rec)
    return {
        "code": 0,
        "data": {
            "from_cache": False,
            "model": "rules-v1",
            "prompt_version": "card-unify-v1",
            "content": content,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }


@router.post("/{profile_id}/{metric_type}/ai-explain-trend")
async def ai_explain_trend(
    profile_id: int,
    metric_type: str,
    body: AiExplainTrendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §七] 趋势解读（统一入口）。"""
    if metric_type not in METRIC_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 metric_type: {metric_type}")
    await _verify_profile_access(db, profile_id, current_user)

    range_map = {"7d": 7, "30d": 30, "90d": 90}
    days = range_map.get(body.range, 7)
    start = datetime.utcnow() - timedelta(days=days)

    rows = list((await db.execute(
        select(HealthMetricRecord).where(
            HealthMetricRecord.profile_id == profile_id,
            HealthMetricRecord.metric_type == metric_type,
            HealthMetricRecord.measured_at >= start,
        ).order_by(HealthMetricRecord.measured_at.desc()).limit(300)
    )).scalars().all())

    data = _rule_explain_trend(metric_type, rows, days)
    return {
        "code": 0,
        "data": {
            "from_cache": False,
            "model": "rules-v1",
            "prompt_version": "card-unify-v1",
            "range": body.range,
            "days": days,
            "summary": data["summary"],
            "trend": data["trend"],
            "advice": data["advice"],
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }


# ─── 元数据接口（供前端展示选项）──────────────────────────────────────

@router.get("/meta")
async def get_meta():
    """[PRD §九.1] 元数据：四指标 label/unit/场景选项/状态档位映射，便于前端模板渲染。"""
    return {
        "code": 0,
        "data": {
            "metric_types": list(METRIC_TYPES),
            "metrics": METRIC_META,
            "status_colors": {
                "blue": "#3B82F6",
                "yellow": "#F59E0B",
                "orange": "#F97316",
                "red": "#DC2626",
                "gray": "#9CA3AF",
            },
        },
    }
