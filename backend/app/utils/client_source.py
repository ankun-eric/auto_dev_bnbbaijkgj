"""[PRD-05 核销动作收口手机端 v1.0] 客户端来源识别与校验。

设计目标：把"发起核销"动作严格收口到手机端，PC 端任何位置不允许发起核销。
核心机制：
- 解析 HTTP Header `Client-Type` / `X-Client-Type`，并兜底解析 `User-Agent`
- 来源 ∈ ("h5-mobile", "verify-miniprogram") -> 通过
- 来源 == "pc-web" 或不可识别 -> 403 Forbidden

四类来源：
- h5-mobile          ：H5 移动版（商家端 /merchant/m/* 页面）
- verify-miniprogram ：核销小程序
- pc-web             ：PC 端浏览器（商家后台 / Admin 平台）
- unknown            ：无法识别（测试环境通常会落在这里）

PRD 5.4 业务规则：
- R-05-01 核销动作仅限手机端（H5 移动版 + 核销小程序）
- R-05-02 PC 端任何位置禁止发起核销
- R-05-04 后端核销接口仅允许移动端来源调用，其他来源返回 403
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException, Request

# ────────── 客户端来源常量 ──────────

CLIENT_H5_MOBILE = "h5-mobile"
CLIENT_VERIFY_MINIPROGRAM = "verify-miniprogram"
CLIENT_PC_WEB = "pc-web"
CLIENT_UNKNOWN = "unknown"

# [客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 客户端家族（顾客侧）
# - h5-user            ：H5 用户端（bangvip.com 顾客域 / 路径）
# - miniprogram-user   ：顾客微信小程序（不含核销小程序）
# - app-user           ：顾客 APP（Flutter Android / iOS）
CLIENT_H5_USER = "h5-user"
CLIENT_MINIPROGRAM_USER = "miniprogram-user"
CLIENT_APP_USER = "app-user"

# [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0] 顾客端入口标识（X-Client-Source）
# 由各客户端入口在请求 Header 中显式声明本次操作"以顾客身份发起"。
# 该标识与 Client-Type 互为补充，专门解决「同一手机号既是商家又是顾客」时
# 顾客端入口被误判/被卡次数等问题。
CUSTOMER_SOURCE_H5 = "h5-customer"
CUSTOMER_SOURCE_MINIPROGRAM = "miniprogram-customer"
CUSTOMER_SOURCE_FLUTTER = "flutter-customer"
CUSTOMER_SOURCES = frozenset({
    CUSTOMER_SOURCE_H5,
    CUSTOMER_SOURCE_MINIPROGRAM,
    CUSTOMER_SOURCE_FLUTTER,
})

CLIENT_SOURCE_HEADERS = ("X-Client-Source", "x-client-source", "Client-Source", "client-source")

# 允许发起核销动作的来源
MOBILE_VERIFY_CLIENTS = frozenset({CLIENT_H5_MOBILE, CLIENT_VERIFY_MINIPROGRAM})

# [客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 允许调用「客户端顾客专属接口」的来源
# 商家端（h5-mobile / verify-miniprogram / pc-web）和 unknown 均不在白名单内
CUSTOMER_CLIENTS = frozenset({
    CLIENT_H5_USER,
    CLIENT_MINIPROGRAM_USER,
    CLIENT_APP_USER,
})

# Header 名称（兼容大小写、X- 前缀）
CLIENT_TYPE_HEADERS = ("Client-Type", "X-Client-Type", "client-type", "x-client-type")

# 移动端 UA 关键词（小写匹配）
_MOBILE_UA_KEYWORDS = (
    "android",
    "iphone",
    "ipod",
    "ipad",
    "mobile",
    "harmonyos",
    "windows phone",
    "blackberry",
)
# 微信小程序 UA 关键词
_WECHAT_MP_UA_KEYWORDS = ("miniprogram", "micromessenger")
# PC 桌面端 UA 关键词（仅在没有移动端关键词命中时才视为 PC）
_PC_UA_KEYWORDS = ("windows nt", "macintosh", "x11; linux", "cros")


def _normalize(value: Optional[str]) -> str:
    """标准化客户端类型字符串，去除空白并转小写。"""
    if not value:
        return ""
    return str(value).strip().lower()


def parse_client_type_from_header(request: Request) -> str:
    """从请求 Header 中解析 Client-Type / X-Client-Type，返回标准化值。

    若 Header 不存在或值不在 4 类合法值中，返回空字符串。
    """
    if request is None:
        return ""
    headers = request.headers
    for name in CLIENT_TYPE_HEADERS:
        v = headers.get(name)
        if v:
            nv = _normalize(v)
            if nv in (
                CLIENT_H5_MOBILE,
                CLIENT_VERIFY_MINIPROGRAM,
                CLIENT_PC_WEB,
                CLIENT_UNKNOWN,
                # [客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 新增三类客户端顾客来源
                CLIENT_H5_USER,
                CLIENT_MINIPROGRAM_USER,
                CLIENT_APP_USER,
            ):
                return nv
            # 容错处理：写错连字符 / 下划线
            normalized_dash = nv.replace("_", "-")
            if normalized_dash in (
                CLIENT_H5_MOBILE,
                CLIENT_VERIFY_MINIPROGRAM,
                CLIENT_PC_WEB,
                CLIENT_H5_USER,
                CLIENT_MINIPROGRAM_USER,
                CLIENT_APP_USER,
            ):
                return normalized_dash
    return ""


def parse_client_type_from_user_agent(user_agent: Optional[str]) -> str:
    """从 User-Agent 兜底推断客户端类型。

    判定优先级（防止误判）：
    1. 微信小程序关键词 -> 优先识别为 verify-miniprogram（注意：本项目两个小程序共用 MicroMessenger UA，
       接口侧无法精确区分，因此 UA 兜底只能保守地把"含小程序关键词的请求"统一视作可信的移动端来源；
       后续仍依赖前端显式传 Client-Type 做精确区分）
    2. 移动端 UA 关键词 -> h5-mobile
    3. PC UA 关键词     -> pc-web
    4. 其它             -> unknown
    """
    if not user_agent:
        return CLIENT_UNKNOWN
    ua = user_agent.lower()

    if any(k in ua for k in _WECHAT_MP_UA_KEYWORDS):
        # 微信内置 WebView / 小程序：UA 同时含 micromessenger，
        # 本项目顾客端小程序与核销小程序均会命中此分支，因此保守降级为 verify-miniprogram，
        # 业务侧实际上同样会通过显式 Client-Type Header 精确区分
        if "miniprogram" in ua:
            return CLIENT_VERIFY_MINIPROGRAM
        # 仅微信浏览器（H5 in WeChat），不当成核销小程序，按移动端处理
        return CLIENT_H5_MOBILE

    if any(k in ua for k in _MOBILE_UA_KEYWORDS):
        return CLIENT_H5_MOBILE

    if any(k in ua for k in _PC_UA_KEYWORDS):
        return CLIENT_PC_WEB

    return CLIENT_UNKNOWN


def detect_client_type(request: Request) -> str:
    """综合判定请求来源。Header 优先，UA 兜底。"""
    if request is None:
        return CLIENT_UNKNOWN
    header_value = parse_client_type_from_header(request)
    if header_value:
        return header_value
    ua = request.headers.get("user-agent") or request.headers.get("User-Agent") or ""
    return parse_client_type_from_user_agent(ua)


def is_mobile_verify_client(client_type: str) -> bool:
    """判断给定的客户端类型是否被允许发起核销动作。"""
    return _normalize(client_type) in MOBILE_VERIFY_CLIENTS


def is_customer_client(client_type: str) -> bool:
    """[客户端订单顾客操作鉴权误判 Bug 修复 v1.0]
    判断给定的客户端类型是否属于「客户端顾客侧」家族。
    仅 h5-user / miniprogram-user / app-user 通过；商家端与 unknown 均拒绝。
    """
    return _normalize(client_type) in CUSTOMER_CLIENTS


# ────────── FastAPI 依赖：来源拦截 ──────────


VERIFY_FORBIDDEN_DETAIL = "核销动作仅限手机端发起，请到手机端 H5 / 核销小程序操作"

# [客户端订单顾客操作鉴权误判 Bug 修复 v1.0]
# 订单顾客专属操作被商家端/PC/不可识别来源调用时的统一文案
CUSTOMER_FORBIDDEN_DETAIL = "该操作仅限客户端使用,请切换到顾客 APP / H5 用户端登录后再试"


async def require_mobile_verify_client(request: Request) -> str:
    """[PRD-05 R-05-04] 依赖项：仅允许移动端来源发起核销。

    用法：
    ```python
    @router.post("/verify")
    async def verify_xxx(
        request: Request,
        client_type: str = Depends(require_mobile_verify_client),
        ...
    ):
        ...
    ```

    返回值：通过校验时，返回标准化后的 client_type 字符串
    抛出：客户端不在允许集合时，抛 HTTPException(403, VERIFY_FORBIDDEN_DETAIL)
    """
    client_type = detect_client_type(request)
    if not is_mobile_verify_client(client_type):
        raise HTTPException(status_code=403, detail=VERIFY_FORBIDDEN_DETAIL)
    return client_type


def parse_client_source_from_header(request: Request) -> str:
    """[双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0] 从 Header 解析 X-Client-Source。

    返回标准化后的来源字符串，命中 CUSTOMER_SOURCES 时返回对应值；
    其他情况返回空字符串。

    也兼容部分客户端把 client_source 放到 body 中的情况（可由调用方读取请求体）。
    """
    if request is None:
        return ""
    headers = request.headers
    for name in CLIENT_SOURCE_HEADERS:
        v = headers.get(name)
        if v:
            nv = _normalize(v).replace("_", "-")
            if nv in CUSTOMER_SOURCES:
                return nv
    return ""


def is_customer_entry(request: Request) -> bool:
    """[双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0
    + BUG-FIX-RESCHEDULE-V2 2026-05-07 UA 兜底强化]
    判断本次请求是否从「顾客端入口」发起。

    判定来源（按优先级，满足任一条件即认定为顾客端入口）：
    1. X-Client-Source Header ∈ {h5-customer, miniprogram-customer, flutter-customer}（最强信号）
    2. Client-Type Header ∈ {h5-user, miniprogram-user, app-user}（向下兼容旧版前端）
    3. UA 兜底：当上述两个 Header 都缺失，且 path 不在商家管家域（/merchant/* PC 后台）下，
       UA 命中"移动端 / 微信小程序 / Flutter / Dart" 等关键词时，按顾客侧入口放行
       （旧版本 App 或漏改的入口不至于硬性 403）

    用于 reschedule 等"商家兼顾客"场景敏感的接口：
    - 顾客端入口 → 跳过商家身份校验、按顾客身份处理
    - 商家管家 PC 后台入口 → 维持原有规则
    """
    if request is None:
        return False
    if parse_client_source_from_header(request):
        return True
    if is_customer_client(detect_client_type(request)):
        return True
    # [BUG-FIX-RESCHEDULE-V2] UA 兜底：仅在 Header 全部缺失时才走 UA 推断
    try:
        ua = (request.headers.get("user-agent") or request.headers.get("User-Agent") or "").lower()
        path = (getattr(getattr(request, "url", None), "path", None) or "").lower()
        # 排除商家 PC 端入口（/merchant/* 但不含 /merchant/m/）
        is_merchant_pc_path = (
            "/merchant/" in path and "/merchant/m/" not in path
        )
        if is_merchant_pc_path:
            return False
        if not ua:
            return False
        # 命中以下关键词之一即视为顾客侧入口
        ua_hints = (
            "miniprogram",  # 微信小程序
            "micromessenger",  # 微信内嵌浏览器（顾客 H5 场景）
            "dart",  # Flutter HTTP 默认 UA 携带 Dart 关键字
            "flutter",
            "okhttp",  # Android Dio/OkHttp 客户端
            "iphone",
            "ipad",
            "android",
            "mobile",
        )
        if any(k in ua for k in ua_hints):
            return True
    except Exception:  # noqa: BLE001
        # UA 兜底任何异常都不阻塞主流程
        return False
    return False


async def get_optional_client_type(request: Request) -> str:
    """[双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
    宽松版客户端来源识别依赖，不抛 403。

    与 require_customer_client_session 的区别：本依赖**仅返回**识别结果，
    不做拦截。供"按入口区分"的接口使用，由业务层自己决定如何处理。
    """
    return detect_client_type(request)


async def require_customer_client_session(request: Request) -> str:
    """[客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 客户端会话强校验。

    与 `require_mobile_verify_client`（核销动作收口）互为对偶机制：
    - 后者把「核销动作」收口到商家端手机来源（h5-mobile + verify-miniprogram）
    - 本依赖把「顾客专属订单动作」收口到客户端家族（h5-user + miniprogram-user + app-user）

    放行条件：
    1. `Client-Type` Header ∈ {h5-user, miniprogram-user, app-user}
    2. 订单归属在各业务接口里单独校验（WHERE user_id = current_user.id）

    其他来源（商家端 H5 移动版、核销小程序、PC 后台、不可识别 unknown）→ 抛 403。

    判定依据从「全局 users.role 字段」切换为「本次请求的客户端会话来源」，
    解决「商家兼顾客」用户在客户端做顾客操作被一刀切的问题。

    用法：
    ```python
    @router.post("/{order_id}/appointment")
    async def set_order_appointment(
        order_id: int,
        client_type: str = Depends(require_customer_client_session),
        ...
    ):
        ...
    ```
    """
    client_type = detect_client_type(request)
    if not is_customer_client(client_type):
        raise HTTPException(
            status_code=403,
            detail=CUSTOMER_FORBIDDEN_DETAIL,
        )
    return client_type


__all__ = [
    "CLIENT_H5_MOBILE",
    "CLIENT_VERIFY_MINIPROGRAM",
    "CLIENT_PC_WEB",
    "CLIENT_UNKNOWN",
    "CLIENT_H5_USER",
    "CLIENT_MINIPROGRAM_USER",
    "CLIENT_APP_USER",
    "CUSTOMER_SOURCE_H5",
    "CUSTOMER_SOURCE_MINIPROGRAM",
    "CUSTOMER_SOURCE_FLUTTER",
    "CUSTOMER_SOURCES",
    "MOBILE_VERIFY_CLIENTS",
    "CUSTOMER_CLIENTS",
    "VERIFY_FORBIDDEN_DETAIL",
    "CUSTOMER_FORBIDDEN_DETAIL",
    "parse_client_type_from_header",
    "parse_client_type_from_user_agent",
    "parse_client_source_from_header",
    "is_customer_entry",
    "detect_client_type",
    "is_mobile_verify_client",
    "is_customer_client",
    "get_optional_client_type",
    "require_mobile_verify_client",
    "require_customer_client_session",
]
