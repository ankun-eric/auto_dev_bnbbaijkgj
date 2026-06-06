"""[BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
单元测试：后端统一按钮意图解析器 + 识药自动写入。

覆盖回归用例 RT-01 ~ RT-08（按文档 §7）。
"""

import pytest

from app.services.button_intent_resolver import (
    DRUG_IDENTIFY,
    REPORT_INTERPRET,
    resolve_button_intent,
)


# ------------------------------------------------------------------
# RT-01 ~ RT-08：覆盖文档 §5.2 的优先级表
# ------------------------------------------------------------------


class TestResolveButtonIntentReportInterpret:
    def test_RT01_new_image_capture_interpret_report(self):
        """RT-01：新体系 - 报告解读
        button_type=ai_function / ai_function_type=image_capture / capture_purpose=interpret_report
        → report_interpret"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="ai_function",
                ai_function_type="image_capture",
                capture_purpose="interpret_report",
            )
            == REPORT_INTERPRET
        )

    def test_RT02_legacy_top_report_interpret(self):
        """RT-02：老体系 - 报告解读
        button_type=report_interpret → report_interpret"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="report_interpret",
                ai_function_type=None,
                capture_purpose=None,
            )
            == REPORT_INTERPRET
        )

    def test_RT03_middle_compat_ai_fn_report_interpret(self):
        """RT-03：中间兼容 - 报告解读
        button_type=ai_function / ai_function_type=report_interpret → report_interpret"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="ai_function",
                ai_function_type="report_interpret",
                capture_purpose=None,
            )
            == REPORT_INTERPRET
        )


class TestResolveButtonIntentDrugIdentify:
    def test_RT04_new_image_capture_identify_medicine(self):
        """RT-04：新体系 - 识药 ⭐
        button_type=ai_function / ai_function_type=image_capture / capture_purpose=identify_medicine
        → drug_identify"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="ai_function",
                ai_function_type="image_capture",
                capture_purpose="identify_medicine",
            )
            == DRUG_IDENTIFY
        )

    def test_RT05_legacy_top_photo_recognize_drug(self):
        """RT-05：老体系 - 识药
        button_type=photo_recognize_drug → drug_identify"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="photo_recognize_drug",
                ai_function_type=None,
                capture_purpose=None,
            )
            == DRUG_IDENTIFY
        )

    def test_RT06_middle_compat_ai_fn_medicine_recognize(self):
        """RT-06：中间兼容 - 识药
        button_type=ai_function / ai_function_type=medicine_recognize → drug_identify"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="ai_function",
                ai_function_type="medicine_recognize",
                capture_purpose=None,
            )
            == DRUG_IDENTIFY
        )


class TestResolveButtonIntentFallthrough:
    def test_RT07_capture_purpose_upload_falls_to_llm(self):
        """RT-07：纯上传（不应进任何专用引擎）
        button_type=ai_function / ai_function_type=image_capture / capture_purpose=upload → None"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="ai_function",
                ai_function_type="image_capture",
                capture_purpose="upload",
            )
            is None
        )

    def test_RT08_questionnaire_falls_to_llm(self):
        """RT-08：其他乱配（兜底走通用 LLM）
        button_type=ai_function / ai_function_type=questionnaire → None"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="ai_function",
                ai_function_type="questionnaire",
                capture_purpose=None,
            )
            is None
        )

    def test_unknown_top_type_falls_to_llm(self):
        """完全未知的 button_type 兜底为 None。"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="external_link",
                ai_function_type=None,
                capture_purpose=None,
            )
            is None
        )


class TestResolveButtonIntentExplicitIntent:
    def test_P1_explicit_report_interpret_wins(self):
        """P1：显式 intent='report_interpret' 优先于其他所有字段。"""
        assert (
            resolve_button_intent(
                intent="report_interpret",
                button_type="external_link",
                ai_function_type="questionnaire",
                capture_purpose="upload",
            )
            == REPORT_INTERPRET
        )

    def test_P1_explicit_drug_identify_wins(self):
        """P1：显式 intent='drug_identify' 优先于其他所有字段。"""
        assert (
            resolve_button_intent(
                intent="drug_identify",
                button_type="ai_function",
                ai_function_type="image_capture",
                capture_purpose="interpret_report",  # 即便此处是 report，显式 drug 仍胜出
            )
            == DRUG_IDENTIFY
        )

    def test_P1_case_insensitive(self):
        """字段大小写应被归一化后比较。"""
        assert (
            resolve_button_intent(
                intent=None,
                button_type="AI_Function",
                ai_function_type="Image_Capture",
                capture_purpose="Identify_Medicine",
            )
            == DRUG_IDENTIFY
        )


# ------------------------------------------------------------------
# 识药自动写入：MedicalRecord(medication_record, ai_drug_identify)
# ------------------------------------------------------------------


@pytest.fixture
def patched_async_session(monkeypatch):
    """把 chat.py 内部的 async_session 临时替换为测试 sqlite session factory，
    让 _auto_sync_drug_record 写入测试内存数据库而非真实 MySQL。"""
    from tests.conftest import test_session

    monkeypatch.setattr("app.api.chat.async_session", test_session)
    return test_session


@pytest.mark.asyncio
async def test_auto_sync_drug_record_writes_medical_record(
    db_session, patched_async_session
):
    """_auto_sync_drug_record 应写入 MedicalRecord(medication_record, ai_drug_identify)
    + MedicalRecordFile（每图一条）。"""
    from datetime import datetime
    from sqlalchemy import select as sa_select

    from app.api.chat import _auto_sync_drug_record
    from app.core.security import get_password_hash
    from app.models.health_archive_v5 import MedicalRecord, MedicalRecordFile
    from app.models.models import (
        ChatSession,
        FamilyMember,
        SessionType,
        User,
        UserRole,
    )

    # 准备用户 + 家庭成员 + 会话
    user = User(
        phone="13900001111",
        password_hash=get_password_hash("Password123"),
        nickname="测试用户",
        role=UserRole.user,
    )
    db_session.add(user)
    await db_session.flush()

    fm = FamilyMember(
        user_id=user.id,
        nickname="本人",
        relationship_type="self",
        is_self=True,
    )
    db_session.add(fm)
    await db_session.flush()

    sess = ChatSession(
        user_id=user.id,
        family_member_id=fm.id,
        session_type=SessionType.health_qa,
        title="拍照识药",
    )
    db_session.add(sess)
    await db_session.commit()

    final_meta = {
        "card_type": "drug_identify",
        "message_type": "drug_identify_card",
        "medicines": [
            {"name": "布洛芬缓释胶囊", "usage": "一次1粒，一日2次，饭后口服"}
        ],
        "image_urls": [
            "https://example.com/drug-1.jpg",
            "https://example.com/drug-2.jpg",
        ],
        "family_member_id": fm.id,
    }

    await _auto_sync_drug_record(
        session_id=sess.id,
        user_id=user.id,
        family_member_id=fm.id,
        final_meta=final_meta,
        ai_text="这是布洛芬，用于解热镇痛...",
    )

    # 验证 MedicalRecord
    mr_q = await db_session.execute(
        sa_select(MedicalRecord).where(
            MedicalRecord.user_id == user.id,
            MedicalRecord.member_id == fm.id,
            MedicalRecord.category == "medication_record",
            MedicalRecord.source == "ai_drug_identify",
        )
    )
    mrs = mr_q.scalars().all()
    assert len(mrs) == 1
    mr = mrs[0]
    assert mr.title == "布洛芬缓释胶囊"
    assert mr.record_date == datetime.now().date()

    # 验证 MedicalRecordFile
    mrf_q = await db_session.execute(
        sa_select(MedicalRecordFile).where(MedicalRecordFile.record_id == mr.id)
    )
    files = mrf_q.scalars().all()
    assert len(files) == 2
    assert {f.file_url for f in files} == {
        "https://example.com/drug-1.jpg",
        "https://example.com/drug-2.jpg",
    }
    assert all(f.file_type == "image" for f in files)


@pytest.mark.asyncio
async def test_auto_sync_drug_record_dedup(db_session, patched_async_session):
    """同一 session_id 重复触发应去重，不重复写入 MedicalRecord。"""
    from sqlalchemy import select as sa_select

    from app.api.chat import _auto_sync_drug_record
    from app.core.security import get_password_hash
    from app.models.health_archive_v5 import MedicalRecord
    from app.models.models import (
        ChatSession,
        FamilyMember,
        SessionType,
        User,
        UserRole,
    )

    user = User(
        phone="13900002222",
        password_hash=get_password_hash("Password123"),
        nickname="测试用户2",
        role=UserRole.user,
    )
    db_session.add(user)
    await db_session.flush()
    fm = FamilyMember(
        user_id=user.id,
        nickname="本人",
        relationship_type="self",
        is_self=True,
    )
    db_session.add(fm)
    await db_session.flush()
    sess = ChatSession(
        user_id=user.id,
        family_member_id=fm.id,
        session_type=SessionType.health_qa,
    )
    db_session.add(sess)
    await db_session.commit()

    final_meta = {
        "card_type": "drug_identify",
        "medicines": [{"name": "感冒清热颗粒"}],
        "image_urls": ["https://example.com/a.jpg"],
        "family_member_id": fm.id,
    }

    # 连续触发两次
    await _auto_sync_drug_record(
        session_id=sess.id, user_id=user.id, family_member_id=fm.id,
        final_meta=final_meta, ai_text="...",
    )
    await _auto_sync_drug_record(
        session_id=sess.id, user_id=user.id, family_member_id=fm.id,
        final_meta=final_meta, ai_text="...",
    )

    mr_q = await db_session.execute(
        sa_select(MedicalRecord).where(
            MedicalRecord.user_id == user.id,
            MedicalRecord.source == "ai_drug_identify",
        )
    )
    mrs = mr_q.scalars().all()
    assert len(mrs) == 1, "去重失败，重复写入 MedicalRecord"


@pytest.mark.asyncio
async def test_auto_sync_drug_record_skip_without_family_member(
    db_session, patched_async_session
):
    """缺少 family_member_id 应跳过写入并记录 warning，不抛异常。"""
    from sqlalchemy import select as sa_select

    from app.api.chat import _auto_sync_drug_record
    from app.core.security import get_password_hash
    from app.models.health_archive_v5 import MedicalRecord
    from app.models.models import (
        ChatSession,
        SessionType,
        User,
        UserRole,
    )

    user = User(
        phone="13900003333",
        password_hash=get_password_hash("Password123"),
        nickname="测试用户3",
        role=UserRole.user,
    )
    db_session.add(user)
    await db_session.flush()
    sess = ChatSession(
        user_id=user.id,
        session_type=SessionType.health_qa,
    )
    db_session.add(sess)
    await db_session.commit()

    await _auto_sync_drug_record(
        session_id=sess.id, user_id=user.id, family_member_id=None,
        final_meta={"card_type": "drug_identify", "medicines": [{"name": "X"}]},
        ai_text="...",
    )

    mr_q = await db_session.execute(
        sa_select(MedicalRecord).where(
            MedicalRecord.user_id == user.id,
            MedicalRecord.source == "ai_drug_identify",
        )
    )
    assert mr_q.scalars().first() is None
