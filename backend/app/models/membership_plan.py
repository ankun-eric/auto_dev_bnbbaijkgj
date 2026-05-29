"""[会员中心 PRD v1.0 对齐 - 2026-05-26] 付费会员套餐与用户订阅模型

本次结构性变更（严格对齐 PRD v1.0）：
- MembershipPlan：删除 plan_code/ai_call_quota/ai_alert_quota/ai_remind_quota/max_guardians/
  benefits_desc/point_multiplier/price_monthly/price_yearly；新增 is_recommended/
  max_managed_by/ai_outbound_call_count/price_month/price_year；保留 discount_rate
  （仅后台可配，用户端不展示）
- FreeMemberQuota：删除老字段（ai_call_quota/ai_alert_quota/ai_remind_quota/
  max_guardians/benefits_desc）；新增 max_managed_by/ai_outbound_call_count

迁移由 backend/app/services/schema_sync._sync_membership_v1_aligned 执行物理 ALTER。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import mapped_column, relationship

from app.core.database import Base


class MembershipPlan(Base):
    """付费会员套餐配置（PRD v1.0 终稿对齐）"""

    __tablename__ = "membership_plans"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(50), nullable=False, comment="套餐名称")
    description = mapped_column(String(255), nullable=True, comment="套餐说明")
    price_month = mapped_column(Numeric(10, 2), nullable=True, comment="月价（30天），NULL=不支持月购")
    price_year = mapped_column(Numeric(10, 2), nullable=True, comment="年价（365天），NULL=不支持年购")
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径变更：
    # 语义：可管理家庭守护成员总人数（**含主账号本人在内**）。前端零加工原样展示。-1=不限。
    # 注：内部 _get_max_guardians 会自动 -1 转换为「不含本人上限」供配额比较使用。
    max_managed = mapped_column(Integer, nullable=False, default=4,
                                comment="家庭守护成员总人数（含本人，用户端原样展示），-1=不限")
    ai_outbound_call_count = mapped_column(Integer, nullable=False, default=0,
                                           comment="AI 外呼提醒（次/月），-1=不限")
    emergency_ai_call_count = mapped_column(Integer, nullable=False, default=0,
                                            comment="紧急 AI 呼叫（次/月），-1=不限")
    max_managed_by = mapped_column(Integer, nullable=False, default=3,
                                   comment="被管理人数上限，-1=不限")
    discount_rate = mapped_column(Float, nullable=True, default=None,
                                  comment="商城折扣率（0.0~1.0，NULL=无折扣，仅后台可配）")
    is_active = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    is_recommended = mapped_column(Boolean, nullable=False, default=False,
                                   comment="是否推荐套餐（开启后用户端展示金色描边+推荐角标）")
    sort_order = mapped_column(Integer, nullable=False, default=0, comment="排序，越小越靠前")
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserMembershipSub(Base):
    """用户付费会员订阅记录"""

    __tablename__ = "user_membership_subs"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = mapped_column(Integer, ForeignKey("membership_plans.id"), nullable=False, index=True)
    billing_cycle = mapped_column(String(20), nullable=False, default="monthly", comment="monthly/yearly")
    start_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expire_at = mapped_column(DateTime, nullable=False, comment="到期时间；过期后自动降级为免费会员")
    status = mapped_column(String(20), nullable=False, default="active",
                           comment="active/expired/cancelled")
    paid_amount = mapped_column(Numeric(10, 2), nullable=True, comment="本次订阅实付金额")
    auto_renew = mapped_column(Boolean, nullable=False, default=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    plan = relationship("MembershipPlan", lazy="joined")


class FreeMemberQuota(Base):
    """免费会员额度配置（PRD v1.0 终稿对齐，系统级单行配置，id=1）"""

    __tablename__ = "free_member_quota"

    id = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径变更：
    # 语义：免费会员家庭守护成员总人数（**含主账号本人在内**）。前端零加工原样展示。
    # 注：内部 _get_max_guardians 会自动 -1 转换为「不含本人上限」供配额比较使用。
    max_managed = mapped_column(Integer, nullable=False, default=4,
                                comment="免费会员家庭守护成员总人数（含本人，用户端原样展示）")
    ai_outbound_call_count = mapped_column(Integer, nullable=False, default=5,
                                           comment="AI 外呼提醒（次/月）")
    emergency_ai_call_count = mapped_column(Integer, nullable=False, default=3,
                                            comment="紧急 AI 呼叫（次/月）")
    max_managed_by = mapped_column(Integer, nullable=False, default=3,
                                   comment="被管理人数上限")
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
