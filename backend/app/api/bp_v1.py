"""[PRD-BP-AI-EXPLAIN-V1 2026-05-31] 血压 AI 解读接口。

接口前缀: /api/bp-v1

提供两个端点（与血糖 AI 解读完全对齐，仅数据源换为 health_metric_record 中
metric_type='blood_pressure' 的记录）：
- POST /api/bp-v1/ai-explain-single  入参: { record_id, profile_id }
- POST /api/bp-v1/ai-explain-trend   入参: { range: '7d'|'30d', profile_id }

设计：
- 鉴权：复用 get_current_user
- 越权：从 health_metric_record 取记录后，校验记录的 profile_id 归属当前用户
  （通过 health_profiles.user_id 校验）
- 大模型：复用 app.services.ai_service.call_ai_model（3 秒超时）
- 提示词：从 ai_prompt_config 表读取 bp_single_explain / bp_trend_explain，
  读不到则使用本文件内置 DEFAULT_*_PROMPT
- 缓存：内存缓存（与血糖共用接口风格，但用独立 key 命名空间 `bp:ai:*`）
- 兜底：模型超时/失败/未配置 → 走规则文案（基于血压档位判定），绝不抛 500
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bp-v1", tags=["PRD-BP-AI-EXPLAIN-V1 血压 AI 解读"])


PROMPT_VERSION = "v1"


# ─── 档位判定（与 H5 端 judgeBp 同口径） ──────────────────────────────

def judge_bp(sbp: Optional[float], dbp: Optional[float]) -> Tuple[str, str]:
    """返回 (level_key, label)。值缺失返回 ('unknown', '未知')。"""
    if sbp is None or dbp is None:
        return ("unknown", "未知")
    if sbp >= 160 or dbp >= 100:
        return ("severe_high", "严重偏高")
    if sbp < 90 or dbp < 60:
        return ("low", "偏低")
    if sbp >= 140 or dbp >= 90:
        return ("mid_high", "中度偏高")
    if sbp >= 120 or dbp >= 80:
        return ("mild_high", "轻度偏高")
    return ("normal", "正常")


# ─── Pydantic ─────────────────────────────────────────────────────────

class BpAiSingleReq(BaseModel):
    record_id: int = Field(..., description="health_metric_record.id")
    profile_id: int = Field(..., description="health_profiles.id")


class BpAiTrendReq(BaseModel):
    range: str = Field("7d", description="7d | 30d")
    profile_id: int = Field(..., description="health_profiles.id")


# ─── 提示词读取与默认模板 ─────────────────────────────────────────────

DEFAULT_SINGLE_PROMPT = """你是一名资深心内科医生兼健康管理师，请根据以下用户的本次血压测量结果，给出一段 80–150 字的通俗易懂的解读，
要求：
1. 用中文，老人也能看懂；
2. 第一句先复述本次结果（收缩压/舒张压数值 + 状态档位）；
3. 第二句解释为什么是这个档位（结合医学常识，参考《中国高血压防治指南》）；
4. 第三句给出 1–2 条具体可执行的建议（饮食/运动/复测/就医）；
5. 不要使用"危象"等吓人字眼；
6. 不要给出诊断结论，只能给出建议。

【本次结果】
- 收缩压：{systolic} mmHg
- 舒张压：{diastolic} mmHg
- 状态档位：{level_label}
- 测量时间：{measured_at}
- 用户信息：性别 {gender}，年龄 {age}
"""


DEFAULT_TREND_PROMPT = """你是一名资深心内科医生兼健康管理师，请根据以下用户近 {range} 的血压记录，给出趋势解读，并以 JSON 格式返回：
{{
  "summary": "近期数据总览（80 字以内）",
  "trend": "趋势特点（80 字以内）",
  "advice": "具体可执行建议（150 字以内，分条列出）"
}}

【用户信息】性别 {gender}，年龄 {age}

【近期记录】
{records_text}
"""


async def _load_bp_prompt(db: AsyncSession, prompt_key: str) -> Optional[str]:
    """从 ai_prompt_config 表读取已发布的提示词。表不存在或未配置返回 None。"""
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
        logger.debug("[BP-AI] load_prompt_failed key=%s err=%s", prompt_key, exc)
    return None


async def _call_ai_with_timeout(prompt_text: str, timeout_s: float = 3.0) -> Optional[str]:
    """调用大模型，3s 超时即降级。复用 app.services.ai_service.call_ai_model。"""
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
        if not txt or "未配置" in txt:
            return None
        return txt
    except asyncio.TimeoutError:
        logger.warning("[BP-AI] call timeout, fallback to rules")
        return None
    except Exception as exc:
        logger.warning("[BP-AI] call_failed: %s", exc)
        return None


# ─── 缓存 ─────────────────────────────────────────────────────────────

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


# ─── 规则兜底文案 ─────────────────────────────────────────────────────

def _fallback_single_explain(sbp: Optional[float], dbp: Optional[float]) -> str:
    level, label = judge_bp(sbp, dbp)
    s = sbp if sbp is not None else "-"
    d = dbp if dbp is not None else "-"
    if level == "normal":
        return f"本次血压 {s}/{d} mmHg，属于正常范围。建议保持规律作息、清淡饮食与适量运动，继续按当前节奏监测。"
    if level == "mild_high":
        return (
            f"本次血压 {s}/{d} mmHg，属于轻度偏高（正常高值）。"
            "建议减少高盐高脂饮食、控制体重，每天散步 30 分钟，1 周后复测；若持续偏高请就医评估。"
        )
    if level == "mid_high":
        return (
            f"本次血压 {s}/{d} mmHg，属于中度偏高（1 级高血压）。"
            "建议低盐低脂饮食、戒烟限酒、规律运动，并尽快到心内科或全科门诊就诊评估是否需要药物治疗。"
        )
    if level == "severe_high":
        return (
            f"本次血压 {s}/{d} mmHg，属于严重偏高。"
            "建议立即静坐休息 15 分钟后复测，若仍持续偏高请尽快前往医院急诊或心内科就诊。"
        )
    if level == "low":
        return (
            f"本次血压 {s}/{d} mmHg，偏低。"
            "建议适量饮水、慢起慢站，避免空腹时间过长；若伴有头晕乏力请及时就医。"
        )
    return f"本次血压 {s}/{d} mmHg。建议保持规律监测，如有不适请及时就医。"


def _fallback_trend_explain(days: int, rows: List[Any]) -> Dict[str, str]:
    if not rows:
        return {
            "summary": f"近 {days} 天暂无血压记录。",
            "trend": "无法判断趋势。",
            "advice": "建议每天固定时段（晨起 / 睡前）测量血压并记录，便于后续分析。",
        }
    sbp_vals: List[float] = []
    dbp_vals: List[float] = []
    high_count = 0
    low_count = 0
    for r in rows:
        v = r[0] if not isinstance(r, dict) else r.get("value_json")
        if isinstance(v, str):
            import json as _json
            try:
                v = _json.loads(v)
            except Exception:
                v = {}
        if not isinstance(v, dict):
            continue
        try:
            s = float(v.get("systolic")) if v.get("systolic") is not None else None
            d = float(v.get("diastolic")) if v.get("diastolic") is not None else None
        except (TypeError, ValueError):
            s = d = None
        if s is not None:
            sbp_vals.append(s)
        if d is not None:
            dbp_vals.append(d)
        level, _ = judge_bp(s, d)
        if level in ("mild_high", "mid_high", "severe_high"):
            high_count += 1
        elif level == "low":
            low_count += 1
    sbp_avg = round(sum(sbp_vals) / len(sbp_vals), 1) if sbp_vals else 0
    dbp_avg = round(sum(dbp_vals) / len(dbp_vals), 1) if dbp_vals else 0
    sbp_max = round(max(sbp_vals), 1) if sbp_vals else 0
    dbp_max = round(max(dbp_vals), 1) if dbp_vals else 0
    summary = (
        f"近 {days} 天共记录 {len(rows)} 次，"
        f"平均 {sbp_avg}/{dbp_avg} mmHg，"
        f"最高 {sbp_max}/{dbp_max} mmHg。"
    )
    if high_count > len(rows) * 0.5:
        trend = f"过半时段偏高（{high_count}/{len(rows)} 次），整体偏高趋势明显。"
    elif high_count > 0:
        trend = f"偶有偏高（{high_count}/{len(rows)} 次），整体相对平稳但需关注。"
    elif low_count > 0:
        trend = f"偶有偏低（{low_count}/{len(rows)} 次），整体平稳但需关注体位性低血压。"
    else:
        trend = "整体保持在正常范围，趋势平稳。"
    advice = (
        "建议：1) 每天固定时段（晨起 / 睡前）测量并记录；"
        "2) 低盐低脂饮食，每天食盐 <5g；"
        "3) 戒烟限酒、规律作息；"
        "4) 每周至少 150 分钟有氧运动；"
        "5) 若收缩压持续 ≥140 或舒张压持续 ≥90，请尽快就医评估。"
    )
    return {"summary": summary, "trend": trend, "advice": advice}


# ─── 工具函数：取血压记录 + 越权校验 ───────────────────────────────────

async def _fetch_bp_record(
    db: AsyncSession, record_id: int, current_user_id: int
) -> Tuple[Optional[float], Optional[float], datetime, int]:
    """读取一条血压记录并校验归属。

    返回 (systolic, diastolic, measured_at, profile_id)
    """
    row = (await db.execute(
        text(
            "SELECT r.value_json, r.measured_at, r.profile_id, p.user_id "
            "FROM health_metric_record r "
            "LEFT JOIN health_profiles p ON p.id = r.profile_id "
            "WHERE r.id=:rid AND r.metric_type='blood_pressure'"
        ),
        {"rid": record_id},
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="血压记录不存在")
    if row[3] is not None and int(row[3]) != int(current_user_id):
        raise HTTPException(status_code=403, detail="无权解读该记录")
    v = row[0]
    if isinstance(v, str):
        import json as _json
        try:
            v = _json.loads(v)
        except Exception:
            v = {}
    if not isinstance(v, dict):
        v = {}
    try:
        sbp = float(v.get("systolic")) if v.get("systolic") is not None else None
    except (TypeError, ValueError):
        sbp = None
    try:
        dbp = float(v.get("diastolic")) if v.get("diastolic") is not None else None
    except (TypeError, ValueError):
        dbp = None
    return (sbp, dbp, row[1], int(row[2]) if row[2] is not None else 0)


def _range_to_days(rng: str) -> int:
    rng = (rng or "7d").lower()
    if rng in ("30d", "month", "30"):
        return 30
    return 7


# ─── 端点 ─────────────────────────────────────────────────────────────

@router.post("/ai-explain-single")
async def ai_explain_single(
    body: BpAiSingleReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-BP-AI-EXPLAIN-V1] AI 解读单次血压。

    Response: { code: 0, data: { content, model, prompt_version, from_cache, generated_at } }
    """
    sbp, dbp, measured_at, _profile_id = await _fetch_bp_record(db, body.record_id, current_user.id)

    cache_key = f"bp:ai:single:{body.record_id}:{PROMPT_VERSION}"
    cached = _cache_get(cache_key, ttl_s=0)
    if cached:
        return {"code": 0, "data": {
            "from_cache": True,
            "model": cached.get("model", "rules"),
            "prompt_version": PROMPT_VERSION,
            "content": cached["content"],
            "generated_at": cached.get("generated_at"),
        }}

    _level, label = judge_bp(sbp, dbp)
    prompt_tpl = await _load_bp_prompt(db, "bp_single_explain")
    if not prompt_tpl:
        prompt_tpl = DEFAULT_SINGLE_PROMPT

    gender = getattr(current_user, "gender", None) or "未填"
    age = getattr(current_user, "age", None) or "未填"
    measured_at_str = (
        measured_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(measured_at, datetime) else str(measured_at)
    )

    prompt_text = (
        prompt_tpl
        .replace("{systolic}", str(sbp if sbp is not None else "-"))
        .replace("{diastolic}", str(dbp if dbp is not None else "-"))
        .replace("{level_label}", label)
        .replace("{measured_at}", measured_at_str)
        .replace("{gender}", str(gender))
        .replace("{age}", str(age))
    )

    ai_text = await _call_ai_with_timeout(prompt_text)
    used_model = "qwen-max"
    if not ai_text:
        ai_text = _fallback_single_explain(sbp, dbp)
        used_model = "rules-fallback"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _cache_set(cache_key, {"content": ai_text, "model": used_model, "generated_at": now_str})
    return {"code": 0, "data": {
        "from_cache": False,
        "model": used_model,
        "prompt_version": PROMPT_VERSION,
        "content": ai_text,
        "generated_at": now_str,
    }}


@router.post("/ai-explain-trend")
async def ai_explain_trend(
    body: BpAiTrendReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-BP-AI-EXPLAIN-V1] AI 解读血压趋势。

    Response: { code: 0, data: { summary, trend, advice, model, prompt_version, from_cache, generated_at } }
    """
    days = _range_to_days(body.range)

    # 校验 profile 归属（防越权）— 必须传 profile_id
    try:
        prof_row = (await db.execute(
            text("SELECT user_id FROM health_profiles WHERE id=:pid"),
            {"pid": body.profile_id},
        )).fetchone()
    except Exception:
        prof_row = None
    if prof_row is None:
        raise HTTPException(status_code=404, detail="健康档案不存在")
    if int(prof_row[0]) != int(current_user.id):
        raise HTTPException(status_code=403, detail="无权访问该档案")

    cache_key = f"bp:ai:trend:{body.profile_id}:{days}:{PROMPT_VERSION}"
    cached = _cache_get(cache_key, ttl_s=300)
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

    start = datetime.now() - timedelta(days=days)
    rows = (await db.execute(
        text(
            "SELECT value_json, measured_at FROM health_metric_record "
            "WHERE profile_id=:pid AND metric_type='blood_pressure' AND measured_at>=:start "
            "ORDER BY measured_at DESC LIMIT 200"
        ),
        {"pid": body.profile_id, "start": start},
    )).fetchall()

    prompt_tpl = await _load_bp_prompt(db, "bp_trend_explain")
    if not prompt_tpl:
        prompt_tpl = DEFAULT_TREND_PROMPT

    gender = getattr(current_user, "gender", None) or "未填"
    age = getattr(current_user, "age", None) or "未填"

    records_text_lines: List[str] = []
    import json as _json
    for r in rows[:60]:
        v = r[0]
        if isinstance(v, str):
            try:
                v = _json.loads(v)
            except Exception:
                v = {}
        if not isinstance(v, dict):
            v = {}
        s = v.get("systolic", "-")
        d = v.get("diastolic", "-")
        t = r[1].strftime("%Y-%m-%d %H:%M") if isinstance(r[1], datetime) else str(r[1])
        records_text_lines.append(f"- {t} {s}/{d} mmHg")
    records_text = "\n".join(records_text_lines) or "（无记录）"

    prompt_text = (
        prompt_tpl
        .replace("{range}", f"{days} 天")
        .replace("{gender}", str(gender))
        .replace("{age}", str(age))
        .replace("{records_text}", records_text)
    )

    ai_text = await _call_ai_with_timeout(prompt_text)
    used_model = "qwen-max"
    summary = trend = advice = ""
    if ai_text:
        try:
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
