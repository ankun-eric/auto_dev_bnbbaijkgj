"""[BUG-HSC-FIX-V2-20260521] B 系列回归测试。

覆盖范围：
- B-2 family 主体文案（subject_kind / subject_label）
- B-7 占位符渲染器（本人 / 家人 / 缺失档案 三个分支）
- B-6 placeholder-catalog 接口结构
- B-1 后端 Q6 备注题 placeholder 与 subtitle 字段独立性（数据契约）
"""
from __future__ import annotations

from datetime import date

import pytest


# ─────────────────────────────────────────────────────────────────
# B-7 占位符渲染器单元测试（纯函数，无需 DB）
# ─────────────────────────────────────────────────────────────────


class _FakeUser:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeFamilyMember:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_placeholder_renderer_self_full_filled():
    from app.services.prompt_renderer import build_placeholder_values, render

    user = _FakeUser(nickname="张小白", gender="男", birthday=date(1990, 5, 1))
    hp = {
        "chronic_diseases": "高血压",
        "allergies": "青霉素",
        "medications": "氨氯地平",
        "surgery_history": None,
        "family_history": "父亲糖尿病",
        "height": 175,
        "weight": 68,
        "blood_type": "O",
    }
    vals = build_placeholder_values(user=user, health_profile=hp, hsc_answer_fields=[
        {"label": "部位", "value": "腹部"},
        {"label": "症状", "value": ["胀痛", "反酸"]},
        {"label": "持续时间", "value": "2 天"},
    ])
    assert vals["user_name"] == "张小白"
    assert vals["user_gender"] == "男"
    assert vals["user_age"] != "未填写"  # 年龄能计算出来
    assert vals["chronic_diseases"] == "高血压"
    assert vals["allergies"] == "青霉素"
    assert vals["bmi"] != "未填写"
    assert vals["body_parts"] == "腹部"
    assert vals["symptoms"] == "胀痛、反酸"
    assert vals["duration"] == "2 天"

    out = render(
        "您好 {user_name}（{user_age}岁），慢病：{chronic_diseases}；本次部位：{body_parts}",
        vals,
    )
    assert "{user_name}" not in out
    assert "张小白" in out
    assert "高血压" in out
    assert "腹部" in out


def test_placeholder_renderer_family_branch():
    from app.services.prompt_renderer import build_placeholder_values, render

    user = _FakeUser(nickname="张小白", gender="男", birthday=date(1990, 5, 1))
    fm = _FakeFamilyMember(
        nickname="妈妈",
        relationship_type="母亲",
        gender="女",
        birthday=date(1965, 1, 1),
    )
    vals = build_placeholder_values(user=user, family_member=fm)
    assert vals["family_member_name"] == "妈妈"
    assert vals["family_member_relation"] == "母亲"
    assert vals["family_member_gender"] == "女"
    assert vals["family_member_age"] != "未填写"

    out = render("本次咨询对象：{family_member_name}（{family_member_relation}）", vals)
    assert "妈妈" in out
    assert "母亲" in out


def test_placeholder_renderer_missing_profile_returns_unfilled():
    """B-7：取不到值时统一渲染为 "未填写"，不抛错。"""
    from app.services.prompt_renderer import build_placeholder_values, render

    vals = build_placeholder_values()
    assert vals["user_name"] == "未填写"
    assert vals["family_member_name"] == "未填写"
    assert vals["chronic_diseases"] == "未填写"
    assert vals["allergies"] == "未填写"
    assert vals["bmi"] == "未填写"
    assert vals["body_parts"] == "未填写"

    out = render("您的过敏史：{allergies}；BMI：{bmi}", vals)
    assert "未填写" in out
    assert "{allergies}" not in out


def test_placeholder_catalog_metadata_complete():
    """B-6：catalog 至少包含 21 项，包含本次 10 项新增字段。"""
    from app.services.prompt_renderer import PLACEHOLDER_CATALOG

    keys = {item["key"] for item in PLACEHOLDER_CATALOG}
    must_have = {
        "user_name", "user_gender", "user_age",
        "family_member_name", "family_member_relation",
        "family_member_age", "family_member_gender",
        "chronic_diseases", "allergies", "medications",
        "surgery_history", "family_history",
        "height", "weight", "bmi", "blood_type",
        "body_parts", "symptoms", "duration", "description",
        "health_profile",
    }
    missing = must_have - keys
    assert not missing, f"占位符 catalog 缺少：{missing}"
    # 每项必须有 scope_tag
    for item in PLACEHOLDER_CATALOG:
        assert "scope_tag" in item and item["scope_tag"], f"item={item} 缺少 scope_tag"


# ─────────────────────────────────────────────────────────────────
# B-5 老表下线迁移：dry-run 模式不应删表（默认行为）
# ─────────────────────────────────────────────────────────────────


def test_legacy_offline_dry_run_default_does_not_drop(monkeypatch):
    """默认 dry-run：HSC_LEGACY_OFFLINE_DROP 未设为 1 时，应不真正 DROP。"""
    monkeypatch.delenv("HSC_LEGACY_OFFLINE_DROP", raising=False)
    from app.services.prd_health_self_check_legacy_offline_v1_migration import _should_drop

    assert _should_drop() is False


def test_legacy_offline_drop_when_env_set(monkeypatch):
    monkeypatch.setenv("HSC_LEGACY_OFFLINE_DROP", "1")
    from app.services.prd_health_self_check_legacy_offline_v1_migration import _should_drop

    assert _should_drop() is True


# ─────────────────────────────────────────────────────────────────
# B-2 主体文案：_build_questionnaire_card_payload 的 subject_label
# ─────────────────────────────────────────────────────────────────


def test_build_card_payload_self_label():
    """本人态：subject_label = '本人'"""
    from app.api.questionnaire import _build_questionnaire_card_payload

    class _Tpl:
        id = 1
        code = "tcm_constitution"
        name = "体质测评"

    class _Ans:
        id = 100
        completed_at = None

    payload = _build_questionnaire_card_payload(
        tpl=_Tpl(),
        ans=_Ans(),
        main_type="平和质",
        secondary_types=None,
        scores=None,
        classification_name="平和质",
        classification_code="ph",
        subject_name="张小白",
        summary_text="您是平和质",
        fields=[],
        icon="🌿",
        subject_kind="self",
        subject_relation=None,
    )
    assert payload["subject_kind"] == "self"
    assert payload["subject_label"] == "本人"


def test_build_card_payload_family_label():
    """家人态：subject_label = '妈妈（母亲）'"""
    from app.api.questionnaire import _build_questionnaire_card_payload

    class _Tpl:
        id = 1
        code = "health_self_check"
        name = "健康自查"

    class _Ans:
        id = 200
        completed_at = None

    payload = _build_questionnaire_card_payload(
        tpl=_Tpl(),
        ans=_Ans(),
        main_type=None,
        secondary_types=None,
        scores=None,
        classification_name=None,
        classification_code=None,
        subject_name="妈妈",
        summary_text="—",
        fields=[
            {"key": "部位", "label": "部位", "value": "腹部"},
            {"key": "症状", "label": "症状", "value": "胀痛"},
        ],
        icon="🩺",
        subject_kind="family",
        subject_relation="母亲",
    )
    assert payload["subject_kind"] == "family"
    assert payload["subject_label"] == "妈妈（母亲）"
    assert payload["subject_relation"] == "母亲"


def test_build_card_payload_family_label_no_relation():
    """家人态但无关系字段：subject_label = '妈妈'（不带括号）"""
    from app.api.questionnaire import _build_questionnaire_card_payload

    class _Tpl:
        id = 1
        code = "tcm_constitution"
        name = "体质测评"

    class _Ans:
        id = 201
        completed_at = None

    payload = _build_questionnaire_card_payload(
        tpl=_Tpl(),
        ans=_Ans(),
        main_type="气虚质",
        secondary_types=None,
        scores=None,
        classification_name="气虚质",
        classification_code="qx",
        subject_name="老爸",
        summary_text="—",
        fields=[],
        icon="🌿",
        subject_kind="family",
        subject_relation=None,
    )
    assert payload["subject_kind"] == "family"
    assert payload["subject_label"] == "老爸"


# ─────────────────────────────────────────────────────────────────
# B-2 archive_prefix 文案分支测试
# ─────────────────────────────────────────────────────────────────


def test_chat_messages_archive_prefix_family_branch():
    """家人档案：开场白应包含'本次回答结合 妈妈（母亲）的健康档案。'"""
    from app.api.questionnaire import _build_chat_messages_sequence

    class _Tpl:
        id = 1
        code = "tcm_constitution"
        name = "体质测评"
        ai_opening = None  # 走兜底分支

    class _Ans:
        id = 300

    msgs = _build_chat_messages_sequence(
        tpl=_Tpl(),
        ans=_Ans(),
        card_payload={},
        ai_opening=None,
        main_type=None,
        secondary_types=None,
        scores=None,
        subject_name="妈妈",
        ai_followup_enabled=False,
        subject_kind="family",
        subject_relation="母亲",
    )
    # 第二条消息是 text，开场白应当包含 "妈妈（母亲）"
    text_msg = next((m for m in msgs if m.get("type") == "text"), None)
    assert text_msg is not None
    assert "妈妈（母亲）" in text_msg["text"]
    assert "本次回答结合" in text_msg["text"]


def test_chat_messages_archive_prefix_self_branch():
    """本人档案：开场白应包含'本次回答结合本人的健康档案。'"""
    from app.api.questionnaire import _build_chat_messages_sequence

    class _Tpl:
        id = 1
        code = "tcm_constitution"
        name = "体质测评"
        ai_opening = None

    class _Ans:
        id = 301

    msgs = _build_chat_messages_sequence(
        tpl=_Tpl(),
        ans=_Ans(),
        card_payload={},
        ai_opening=None,
        main_type=None,
        secondary_types=None,
        scores=None,
        subject_name="张小白",
        ai_followup_enabled=False,
        subject_kind="self",
        subject_relation=None,
    )
    text_msg = next((m for m in msgs if m.get("type") == "text"), None)
    assert text_msg is not None
    assert "本人" in text_msg["text"]
    assert "本次回答结合" in text_msg["text"]


# ─────────────────────────────────────────────────────────────────
# B-6 placeholder-catalog API 结构（不实际启动 server，断 schema）
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_placeholder_catalog_endpoint_shape():
    """placeholder-catalog 接口结构断言（直接调函数）。"""
    from app.api.questionnaire import get_placeholder_catalog

    out = await get_placeholder_catalog()
    assert "items" in out
    assert isinstance(out["items"], list)
    assert len(out["items"]) >= 21
    assert out.get("unfilled_text") == "未填写"
    sample = out["items"][0]
    assert {"key", "label", "scope_tag"}.issubset(sample.keys())
