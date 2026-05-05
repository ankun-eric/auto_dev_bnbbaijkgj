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

# 允许发起核销动作的来源
MOBILE_VERIFY_CLIENTS = frozenset({CLIENT_H5_MOBILE, CLIENT_VERIFY_MINIPROGRAM})

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
            ):
                return nv
            # 容错处理：写错连字符 / 下划线
            if nv.replace("_", "-") in (CLIENT_H5_MOBILE, CLIENT_VERIFY_MINIPROGRAM, CLIENT_PC_WEB):
                return nv.replace("_", "-")
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


# ────────── FastAPI 依赖：来源拦截 ──────────


VERIFY_FORBIDDEN_DETAIL = "核销动作仅限手机端发起，请到手机端 H5 / 核销小程序操作"


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


__all__ = [
    "CLIENT_H5_MOBILE",
    "CLIENT_VERIFY_MINIPROGRAM",
    "CLIENT_PC_WEB",
    "CLIENT_UNKNOWN",
    "MOBILE_VERIFY_CLIENTS",
    "VERIFY_FORBIDDEN_DETAIL",
    "parse_client_type_from_header",
    "parse_client_type_from_user_agent",
    "detect_client_type",
    "is_mobile_verify_client",
    "require_mobile_verify_client",
]
