# [PRD-FAMILY-V3-STATUS-INPLACE-UPGRADE 2026-06-03] V3 状态字段原地升级常量
#
# ──────────────────────────────────────────────────────────────────
# 治本背景：
#   原 status 字段值为 active / removed / deleted（语义模糊、与 V3 主+子状态
#   不对齐）。本次原地升级把 status 列内的值替换成 V3 主状态新枚举：
#
#       active   →  bound           （子状态 bound）
#       removed  →  deleted         （子状态 self_deleted）
#       deleted  →  deleted         （子状态 admin_deleted）
#       已解绑回扫 → unbound         （子状态 unbinded）
#
#   同时新增 sub_status 列存放子状态（8 种）。列名 status 保留不动，
#   保证 SQLAlchemy ORM 字段名、所有 JOIN 写法、所有索引都不需要重命名。
# ──────────────────────────────────────────────────────────────────

from typing import Tuple

# ============ V3 新枚举:主状态 ============
MAIN_STATUS_BOUND = "bound"          # 守护关系生效中
MAIN_STATUS_UNBOUND = "unbound"      # 未绑定/已解绑
MAIN_STATUS_DELETED = "deleted"      # 卡片已软删除

# ============ V3 新枚举:子状态 ============
SUB_STATUS_BOUND = "bound"
SUB_STATUS_NOT_APPLIED = "not_applied"
SUB_STATUS_APPLYING = "applying"
SUB_STATUS_REJECTED = "rejected"
SUB_STATUS_UNBINDED = "unbinded"
SUB_STATUS_INVITED_EXPIRED = "invited_expired"
SUB_STATUS_SELF_DELETED = "self_deleted"
SUB_STATUS_ADMIN_DELETED = "admin_deleted"

# ============ 过滤口径:已删除/已隐藏 ============
# "已删除"统一收口到 deleted 主状态(治本后唯一软删除标记)
DELETED_STATUSES: Tuple[str, ...] = (MAIN_STATUS_DELETED,)

# "已隐藏"包含 deleted + unbound(已解绑也视为 Tab 隐藏)
HIDDEN_STATUSES: Tuple[str, ...] = (MAIN_STATUS_DELETED, MAIN_STATUS_UNBOUND)

# ============ 兼容期常量(已摘掉 removed) ============
# V3 升级后 FamilyMember.status 已不再写入 removed，统一使用 deleted/unbound。
# FamilyManagement 表的 removed 状态是独立状态体系，不在本常量管理范围内。
DELETED_OR_REMOVED_STATUSES: Tuple[str, ...] = (
    MAIN_STATUS_DELETED,
    MAIN_STATUS_UNBOUND,  # 已解绑视为 Tab 隐藏
)

# ============ "守护中"的判定 ============
# 替代原 status == 'active' 的所有过滤
ACTIVE_STATUSES: Tuple[str, ...] = (MAIN_STATUS_BOUND,)

# 兼容期"守护中"过滤口径(灰度期同时认 bound + 老的 active)
ACTIVE_STATUSES_COMPAT: Tuple[str, ...] = (MAIN_STATUS_BOUND, "active")

__all__ = [
    # 新枚举
    "MAIN_STATUS_BOUND", "MAIN_STATUS_UNBOUND", "MAIN_STATUS_DELETED",
    "SUB_STATUS_BOUND", "SUB_STATUS_NOT_APPLIED", "SUB_STATUS_APPLYING",
    "SUB_STATUS_REJECTED", "SUB_STATUS_UNBINDED", "SUB_STATUS_INVITED_EXPIRED",
    "SUB_STATUS_SELF_DELETED", "SUB_STATUS_ADMIN_DELETED",
    # 过滤口径
    "DELETED_STATUSES", "HIDDEN_STATUSES",
    "DELETED_OR_REMOVED_STATUSES",
    "ACTIVE_STATUSES", "ACTIVE_STATUSES_COMPAT",
]
