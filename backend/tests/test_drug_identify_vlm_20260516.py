"""[BUG_FIX_用药识别千图一答 2026-05-16] 视觉版用药识别回归测试。

本测试覆盖修复方案 §5 的关键验收点：

T-DRG-VLM-01：``extract_image_urls`` 能从混合文本中解析出图片 URL（不同顺序、不同后缀）
T-DRG-VLM-02：``upgrade_messages_to_multimodal`` 把裸 URL 升级为 OpenAI 多模态 content
T-DRG-VLM-03：``build_vision_message_content`` 无图时返回纯文本（向后兼容）
T-DRG-VLM-04：identify_drug_structured 在调用方不传图片 URL 时直接 retake 不调模型
T-DRG-VLM-05：identify_drug_structured 在 LLM 返回非法 JSON 时给出 retake 兜底
T-DRG-VLM-06：identify_drug_structured 在 LLM 正常返回结构化 JSON 时正常解析所有字段
T-DRG-VLM-07：identify_drug_structured 在 LLM 返回 ```json 包裹的代码块时也能解析
T-DRG-VLM-08：identify_drug_from_image 必须把图片 URL 真正放进 content 多模态结构里
T-DRG-VLM-09：不同图片 URL 对应不同的 prompt content（防"千图一答"在协议层重现）

所有测试都通过 monkeypatch 拦截 ``call_ai_model``，不依赖真实 LLM 网络。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from app.services import ai_service
from app.services.ai_service import (
    build_vision_message_content,
    extract_image_urls,
    identify_drug_from_image,
    identify_drug_structured,
    upgrade_messages_to_multimodal,
)


def test_extract_image_urls_picks_only_image_urls():
    """T-DRG-VLM-01：仅捕获带图片后缀的 http(s) URL，纯文本/中文不会误命中。"""
    text = (
        "[用户上传的图片 2 张]\n"
        "1. https://cdn.example.com/drugs/a.png\n"
        "2. http://x.y.z/b.JPG?token=abc\n"
        "\n"
        "我上传了一张药品图片，请帮我识别。https://example.com/not-an-image\n"
        "末尾再放一张 https://cdn.example.com/c.webp"
    )
    urls = extract_image_urls(text)
    assert "https://cdn.example.com/drugs/a.png" in urls
    assert any(u.startswith("http://x.y.z/b.JPG") for u in urls)
    assert "https://cdn.example.com/c.webp" in urls
    # 不应误把 not-an-image（无后缀）算进来
    assert all("not-an-image" not in u for u in urls)


def test_extract_image_urls_handles_empty_and_none():
    assert extract_image_urls("") == []
    assert extract_image_urls(None) == []  # type: ignore[arg-type]


def test_upgrade_messages_to_multimodal_converts_user_image_urls():
    """T-DRG-VLM-02：user 消息含图片 URL 时被升级为 [image_url..., text]。system / assistant 不动。"""
    messages = [
        {"role": "system", "content": "你是药品识别助手"},
        {"role": "user", "content": "https://cdn.x/a.png\n请识别"},
        {"role": "assistant", "content": "好的"},
        {"role": "user", "content": "纯文字，无图片"},
    ]
    upgraded = upgrade_messages_to_multimodal(messages)
    # system 原样
    assert upgraded[0]["content"] == "你是药品识别助手"
    # 第一条 user：被升级
    new_content = upgraded[1]["content"]
    assert isinstance(new_content, list)
    types = [part.get("type") for part in new_content]
    assert "image_url" in types
    assert "text" in types
    # 图片放前面，文本放后面
    assert types[0] == "image_url"
    assert new_content[0]["image_url"]["url"] == "https://cdn.x/a.png"
    # assistant 原样
    assert upgraded[2]["content"] == "好的"
    # 第二条 user：无图片 → content 仍是字符串
    assert upgraded[3]["content"] == "纯文字，无图片"


def test_build_vision_message_content_no_image_returns_plain_string():
    """T-DRG-VLM-03：无图片 URL 时 build_vision_message_content 必须返回纯字符串。"""
    result = build_vision_message_content("hello", [])
    assert result == "hello"
    assert isinstance(result, str)


def test_build_vision_message_content_with_images_returns_list():
    result = build_vision_message_content("识别这个药", ["https://x/a.png", "https://x/b.jpg"])
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["type"] == "image_url"
    assert result[1]["type"] == "image_url"
    assert result[2]["type"] == "text"
    assert result[2]["text"] == "识别这个药"


@pytest.mark.asyncio
async def test_identify_structured_no_image_returns_retake():
    """T-DRG-VLM-04：调用方没传任何图片 URL 时，必须直接 next_action=retake，不调 LLM。"""
    res = await identify_drug_structured(image_urls=[], ocr_text=None, db=None)
    assert res["recognized"] is False
    assert res["next_action"] == "retake"
    assert res["medicines"] == []


@pytest.mark.asyncio
async def test_identify_structured_bad_json_falls_back_to_retake(monkeypatch):
    """T-DRG-VLM-05：LLM 返回完全无法解析的脏内容时，应该给出 retake 兜底，不允许抛异常。"""
    captured_args: Dict[str, Any] = {}

    async def fake_call(messages, system_prompt, db):
        captured_args["messages"] = messages
        captured_args["system_prompt"] = system_prompt
        return "这根本不是 JSON，模型胡说八道"

    monkeypatch.setattr(ai_service, "call_ai_model", fake_call)

    res = await identify_drug_structured(
        image_urls=["https://cdn.x/a.png"],
        ocr_text="阿莫西林",
        db=None,
    )
    assert res["recognized"] is False
    assert res["next_action"] == "retake"
    assert "AI 识别失败" in res["summary_markdown"]
    # 必须把图片真的塞到 content 里（多模态结构），不是只把 URL 拼到字符串
    user_msg = captured_args["messages"][0]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert any(
        part.get("type") == "image_url" and part["image_url"]["url"] == "https://cdn.x/a.png"
        for part in user_msg["content"]
    )


@pytest.mark.asyncio
async def test_identify_structured_happy_path(monkeypatch):
    """T-DRG-VLM-06：LLM 返回标准 JSON 时，所有字段正确解析。"""
    good_json = {
        "recognized": True,
        "confidence": 0.92,
        "medicines": [
            {
                "name": "氯雷他定片",
                "brand": "开瑞坦",
                "spec": "10mg x 6 片",
                "manufacturer": "拜耳",
                "category": "非处方药",
                "ingredients": "氯雷他定",
                "usage": "成人一日一次，一次 10mg",
                "indications": "缓解过敏性鼻炎",
                "precautions": "服药期间避免饮酒",
                "contraindications": "对本品过敏者禁用",
            }
        ],
        "raw_ocr_text": "氯雷他定片 拜耳",
        "next_action": "show_card",
        "summary_markdown": "**氯雷他定片**（开瑞坦）...",
        "disclaimer": "AI 识别结果仅供参考",
    }

    async def fake_call(messages, system_prompt, db):
        return json.dumps(good_json, ensure_ascii=False)

    monkeypatch.setattr(ai_service, "call_ai_model", fake_call)
    res = await identify_drug_structured(
        image_urls=["https://cdn.x/a.png"],
        ocr_text="氯雷他定片 拜耳",
        db=None,
    )
    assert res["recognized"] is True
    assert res["confidence"] == 0.92
    assert res["next_action"] == "show_card"
    assert len(res["medicines"]) == 1
    assert res["medicines"][0]["name"] == "氯雷他定片"
    assert res["medicines"][0]["brand"] == "开瑞坦"


@pytest.mark.asyncio
async def test_identify_structured_unwraps_code_fence(monkeypatch):
    """T-DRG-VLM-07：LLM 返回 ```json ... ``` 时也能解析。"""
    payload = {
        "recognized": True,
        "confidence": 0.7,
        "medicines": [{"name": "布洛芬缓释胶囊"}],
        "next_action": "show_card",
        "summary_markdown": "...",
    }
    fenced = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    async def fake_call(messages, system_prompt, db):
        return fenced

    monkeypatch.setattr(ai_service, "call_ai_model", fake_call)
    res = await identify_drug_structured(
        image_urls=["https://cdn.x/a.png"],
        ocr_text=None,
        db=None,
    )
    assert res["recognized"] is True
    assert res["medicines"][0]["name"] == "布洛芬缓释胶囊"


@pytest.mark.asyncio
async def test_identify_from_image_passes_multimodal_content(monkeypatch):
    """T-DRG-VLM-08：identify_drug_from_image 必须以多模态结构把图片 URL 真正送进 user content。

    这是修复"千图一答"的最关键协议层验证：如果模型 user content 还是纯字符串，
    则 Bug 在协议层就回来了。
    """
    captured: Dict[str, Any] = {}

    async def fake_call(messages, system_prompt, db):
        captured["messages"] = messages
        captured["system_prompt"] = system_prompt
        return "（模拟模型返回的识别结果）"

    monkeypatch.setattr(ai_service, "call_ai_model", fake_call)

    result = await identify_drug_from_image(
        image_description="拍照识药",
        db=None,
        image_urls=["https://cdn.x/some-drug.png"],
        ocr_text="阿司匹林肠溶片",
    )
    assert "（模拟模型返回的识别结果）" in result

    user_msg = captured["messages"][0]
    assert user_msg["role"] == "user"
    # 必须是多模态 list 而不是纯文本
    assert isinstance(user_msg["content"], list), f"got: {user_msg['content']!r}"
    assert any(
        part.get("type") == "image_url" and "some-drug.png" in part["image_url"]["url"]
        for part in user_msg["content"]
    )
    # OCR 文字也要带进去
    assert any(
        part.get("type") == "text" and "阿司匹林肠溶片" in part.get("text", "")
        for part in user_msg["content"]
    )
    # system_prompt 不能再是旧版那套"凭描述瞎猜"的话术
    assert "无法识别" in captured["system_prompt"] or "重拍" in captured["system_prompt"]


@pytest.mark.asyncio
async def test_different_images_produce_different_prompts(monkeypatch):
    """T-DRG-VLM-09：不同图片 URL 必然落进不同的 user content，杜绝协议层"千图一答"。

    旧版 Bug 的根因是任何图都被映射成同一段 prompt（"用户上传了一张药品图片，文件名: x"），
    本测试断言：两张不同 URL 的图，发给 LLM 的 messages 一定不同。
    """
    seen_contents: List[Any] = []

    async def fake_call(messages, system_prompt, db):
        seen_contents.append(messages[0]["content"])
        # 返回一个最低限度合法的结构化结果，避免兜底路径
        return json.dumps({
            "recognized": True,
            "confidence": 0.5,
            "medicines": [{"name": "X"}],
            "next_action": "show_card",
            "summary_markdown": "x",
        })

    monkeypatch.setattr(ai_service, "call_ai_model", fake_call)
    await identify_drug_structured(image_urls=["https://cdn.x/img-A.png"], db=None)
    await identify_drug_structured(image_urls=["https://cdn.x/img-B.png"], db=None)

    assert len(seen_contents) == 2
    # 两次发给 LLM 的 user content 必须不同（最起码图片 URL 不同）
    assert seen_contents[0] != seen_contents[1]
    # 都应是多模态结构
    for c in seen_contents:
        assert isinstance(c, list)
    urls = []
    for c in seen_contents:
        for part in c:
            if part.get("type") == "image_url":
                urls.append(part["image_url"]["url"])
    assert "https://cdn.x/img-A.png" in urls
    assert "https://cdn.x/img-B.png" in urls


@pytest.mark.asyncio
async def test_call_ai_model_upgrades_chat_messages_with_urls(monkeypatch):
    """T-DRG-VLM-10：call_ai_model 在收到普通 chat messages（user content 含图片 URL）时，
    必须自动升级为多模态结构再发给 LLM——这是让 ai-home 拍照识药修复"零前端改动"也能生效的关键。
    """
    captured: Dict[str, Any] = {}

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):  # noqa: A002
            captured["payload"] = json
            return FakeResp({
                "choices": [{"message": {"content": "（fake answer）"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            })

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", FakeClient)

    async def fake_get_config(db=None):
        return {
            "base_url": "http://fake",
            "model": "fake-vlm",
            "api_key": "k",
            "max_tokens": 10,
            "temperature": 0.1,
        }

    monkeypatch.setattr(ai_service, "_get_active_model_config", fake_get_config)

    text = (
        "[用户上传的图片 1 张]\n"
        "1. https://cdn.x/pill.png\n"
        "\n"
        "我上传了一张药品图片，请帮我识别"
    )
    await ai_service.call_ai_model(
        messages=[{"role": "user", "content": text}],
        system_prompt="你是药品识别助手",
        db=None,
    )

    payload_messages = captured["payload"]["messages"]
    # system + user
    assert payload_messages[0]["role"] == "system"
    user_msg = payload_messages[-1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list), f"未升级为多模态：{user_msg['content']!r}"
    assert any(
        part.get("type") == "image_url" and part["image_url"]["url"] == "https://cdn.x/pill.png"
        for part in user_msg["content"]
    )


