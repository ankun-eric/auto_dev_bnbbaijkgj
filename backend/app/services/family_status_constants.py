# [PRD-FAMILY-V3-EMERGENCY-FIX 2026-06-03] V3 状态过滤统一常量
# 用途：所有家庭成员/家庭档案查询接口必须使用同一套"软删除/解绑"过滤口径，
# 杜绝 6399 账号反馈的"家人 Tab 看不到苏俊林、家庭档案能看到"现象。
#
# 真值口径：
#   - "已删除"语义统一覆盖 deleted（家庭成员状态机软删）+ removed（旧 DELETE 接口写入）
#   - 即两个软删除标记都视为"已隐藏",无论是从顶部 Tab 还是健康档案视图,都必须排除。
#
# V3 治本上线后,family_members 会改用 main_status='deleted' 字段,届时本常量将被
# upgrade 为新口径,但同一兼容期 30 天内,旧 status 字段仍是真值来源。

from typing import Tuple

# 旧版 status 字段中表示"已删除/已隐藏"的所有取值
DELETED_OR_REMOVED_STATUSES: Tuple[str, ...] = ("deleted", "removed")

__all__ = ["DELETED_OR_REMOVED_STATUSES"]
