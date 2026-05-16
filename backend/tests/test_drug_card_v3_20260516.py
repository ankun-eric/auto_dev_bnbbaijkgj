"""[PRD-DRUG-CARD-V3 2026-05-16] AI 对话拍照识药 v3 单元测试。

覆盖：
- call_ai_model 默认不再自动多模态升级（修复 Bug #2 400 Bad Request 的根因）
- call_ai_model(enable_vision=True) 仍可主动升级
- medication_library_v3 工具函数：过敏冲突 / 慢病冲突 / 重复用药判定
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.services import ai_service
from app.api.medication_library_v3 import (
    CHRONIC_CONFLICT_MAP,
    _check_allergy,
    _check_chronic,
    _safe_list,
)


# ────────── Bug #2 回归 ──────────


def test_call_ai_model_default_no_multimodal_upgrade(monkeypatch):
    """call_ai_model 默认 enable_vision=False，messages 不应被升级为多模态结构。

    这是 Bug #2（400 Bad Request 根治）的关键回归点。
    """
    captured: Dict[str, Any] = {}

    class _FakeResp:
        def __init__(self):
            self._json = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        def json(self):
            return self._json

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["payload"] = json
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)

    async def _fake_get_active(db=None):
        return {
            "base_url": "https://x.example.com",
            "model": "deepseek-v3-2-251201",
            "api_key": "k",
            "max_tokens": 100,
            "temperature": 0.5,
        }

    monkeypatch.setattr(ai_service, "_get_active_model_config", _fake_get_active)

    import asyncio

    messages = [
        {
            "role": "user",
            "content": "https://cdn.x/a.png\n请识别这张药品",
        }
    ]
    result = asyncio.get_event_loop().run_until_complete(
        ai_service.call_ai_model(messages, "", db=None)
    )
    assert result == "ok"
    sent_messages = captured["payload"]["messages"]
    # 关键断言：默认调用下 content 必须仍是字符串，未被升级为 list
    user_msg = next(m for m in sent_messages if m["role"] == "user")
    assert isinstance(user_msg["content"], str), (
        "call_ai_model 默认 enable_vision=False 时不应把 content 升级为多模态 list 结构，"
        "否则纯文本模型 deepseek-v3-2-251201 会返回 400 Bad Request"
    )


def test_call_ai_model_enable_vision_does_upgrade(monkeypatch):
    """enable_vision=True 时应该把 user 消息中的图片 URL 升级为多模态结构。"""
    captured: Dict[str, Any] = {}

    class _FakeResp:
        def json(self):
            return {"choices": [{"message": {"content": "ok"}}], "usage": None}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["payload"] = json
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)

    async def _fake_get_active(db=None):
        return {
            "base_url": "https://x.example.com",
            "model": "doubao-vision-pro",
            "api_key": "k",
            "max_tokens": 100,
            "temperature": 0.5,
        }

    monkeypatch.setattr(ai_service, "_get_active_model_config", _fake_get_active)

    import asyncio

    messages = [
        {"role": "user", "content": "https://cdn.x/a.png\n请识别这张药品"}
    ]
    asyncio.get_event_loop().run_until_complete(
        ai_service.call_ai_model(messages, "", db=None, enable_vision=True)
    )
    sent_messages = captured["payload"]["messages"]
    user_msg = next(m for m in sent_messages if m["role"] == "user")
    assert isinstance(user_msg["content"], list), "enable_vision=True 时应升级 content 为 list"
    types = [p.get("type") for p in user_msg["content"]]
    assert "image_url" in types and "text" in types


# ────────── 冲突判定 ──────────


def test_safe_list_normalizes_inputs():
    assert _safe_list(None) == []
    assert _safe_list(["a", "b"]) == ["a", "b"]
    assert _safe_list("青霉素,头孢菌素") == ["青霉素", "头孢菌素"]
    assert _safe_list("青霉素; 磺胺") == ["青霉素", "磺胺"]


def test_allergy_conflict_from_library_field():
    """命中库时，contraindications 字段含过敏关键词 → 触发 high 级冲突。"""
    card = {
        "drug_name": "阿莫西林胶囊",
        "contraindications": "青霉素过敏者禁用",
        "category": "青霉素类抗生素",
    }
    conflicts = _check_allergy(card, ["青霉素"], source="library")
    assert len(conflicts) == 1
    assert conflicts[0].severity == "high"
    assert conflicts[0].block_add is True
    assert "青霉素" in conflicts[0].title


def test_allergy_conflict_fallback_when_library_missing():
    """未命中库降级：仅 drug_name/generic_name 字面含过敏词也要触发 high 级冲突。

    这是 PRD F4 / TC17 的关键合规口径：宁可误报不漏报。
    """
    card = {
        "drug_name": "阿莫西林胶囊",  # 字面含"莫西林"
        "generic_name": None,
        "category": None,
        "contraindications": None,  # 库未命中 → 权威字段为空
    }
    # 档案过敏关键词「莫西林」（演示模糊场景）应触发
    conflicts = _check_allergy(card, ["莫西林"], source="fallback")
    assert len(conflicts) == 1
    assert conflicts[0].severity == "high"
    assert conflicts[0].block_add is True
    assert conflicts[0].source == "fallback"


def test_allergy_no_match_no_conflict():
    card = {"drug_name": "二甲双胍", "category": "降糖药"}
    conflicts = _check_allergy(card, ["青霉素"], source="library")
    assert conflicts == []


def test_chronic_conflict_via_disease_tags():
    card = {"drug_name": "A", "disease_tags": ["高血压患者慎用"]}
    conflicts = _check_chronic(card, ["高血压"], source="library")
    assert len(conflicts) >= 1
    assert conflicts[0].type == "chronic_disease"
    assert conflicts[0].severity == "medium"
    assert conflicts[0].block_add is False


def test_chronic_conflict_via_keyword_map():
    card = {
        "drug_name": "复方伪麻黄碱片",
        "indications": "感冒",
    }
    conflicts = _check_chronic(card, ["高血压"], source="library")
    assert any("高血压" in c.title for c in conflicts)


def test_chronic_diabetes_via_keyword():
    card = {"drug_name": "止咳糖浆", "indications": "咳嗽"}
    conflicts = _check_chronic(card, ["糖尿病"], source="library")
    assert any("糖尿病" in c.title for c in conflicts)
