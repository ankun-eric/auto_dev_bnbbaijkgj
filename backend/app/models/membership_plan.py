"""[付费会员体系 PRD v1.1] 付费会员套餐与用户订阅模型

新增模型：
- MembershipPlan：付费会员套餐配置（守护版/家庭版/年度版等）
- UserMembershipSub：用户订阅记录（active/expired/cancelled）。
  ⚠️ 表名与历史 UserMembership(user_memberships) 冲突，因此采用新表名 user_membership_subs。
- FreeMemberQuota：免费会员额度配置（单行配置表，id=1）

注：旧有 MemberLevel（积分会员等级）与 UserMembership（AI 外呼额度统计）保持表结构不变，
但新「付费会员订阅」业务以 UserMembershipSub 为主。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import mapped_column, relationship

from app.core.database import Base


class MembershipPlan(Base):
    """付费会员套餐配置（守护版/家庭版等）"""

    __tablename__ = "membership_plans"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_code = mapped_column(String(50), nullable=False, unique=True, comment="套餐唯一标识，如 guardian/family/annual")
    name = mapped_column(String(100), nullable=False, comment="套餐名称，如『守护版』")
    price_monthly = mapped_column(Numeric(10, 2), nullable=False, default=0, comment="月度价格（元）")
    price_yearly = mapped_column(Numeric(10, 2), nullable=True, comment="年度价格（元），可空")
    ai_call_quota = mapped_column(Integer, nullable=False, default=0, comment="AI 电话告警额度（次/月）")
    ai_alert_quota = mapped_column(Integer, nullable=False, default=0, comment="AI 异常告警额度（次/月）")
    ai_remind_quota = mapped_column(Integer, nullable=False, default=0, comment="AI 外呼提醒额度（次/月）")
    max_guardians = mapped_column(Integer, nullable=False, default=1, comment="守护人数量上限")
    discount_rate = mapped_column(Float, nullable=False, default=1.0, comment="商城折扣率，如 0.9 表示 9 折")
    benefits_desc = mapped_column(Text, nullable=True, comment="套餐权益描述（富文本/纯文本）")
    is_active = mapped_column(Boolean, nullable=False, default=True, comment="是否启用（用户端可见可购买）")
    sort_order = mapped_column(Integer, nullable=False, default=0, comment="列表排序，越小越靠前")
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserMembershipSub(Base):
    """用户付费会员订阅记录（PRD v1.1）

    注：表名采用 user_membership_subs，避免与既有 user_memberships（PRD-HEALTH-OPT-V1 AI 外呼配额表）冲突。
    """

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
    """免费会员额度配置（系统级单行配置，id 固定为 1）"""

    __tablename__ = "free_member_quota"

    id = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    ai_call_quota = mapped_column(Integer, nullable=False, default=0, comment="免费 AI 电话告警额度（次/月）")
    ai_alert_quota = mapped_column(Integer, nullable=False, default=3, comment="免费异常告警额度（次/月）")
    ai_remind_quota = mapped_column(Integer, nullable=False, default=0, comment="免费 AI 外呼提醒额度（次/月）")
    max_guardians = mapped_column(Integer, nullable=False, default=1, comment="免费用户守护人数量上限")
    benefits_desc = mapped_column(Text, nullable=True, comment="免费会员权益说明")
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
