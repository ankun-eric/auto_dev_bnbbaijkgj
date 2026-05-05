"""[PRD-05 核销动作收口手机端 v1.0] 单元测试

覆盖范围
========
A. utils.client_source 客户端来源识别
   1. parse_client_type_from_header：标准化 Header / 大小写 / 兼容下划线
   2. parse_client_type_from_user_agent：UA 兜底（含微信、安卓、iPhone、PC）
   3. detect_client_type：Header 优先、UA 兜底
   4. is_mobile_verify_client：仅 h5-mobile / verify-miniprogram 通过

B. require_mobile_verify_client 依赖项
   1. h5-mobile / verify-miniprogram → 通过
   2. pc-web → 403
   3. unknown → 403
   4. UA 兜底命中 PC → 403
   5. UA 兜底命中 iPhone → 通过

C. 行为契约（PRD §2.4 / R-05-04）
   1. 错误时返回的 detail 与 PRD 一致
   2. 4 类来源穷举参数化
"""
from __future__ import annotations

import asyncio
from typing import Optional
from unittest.mock import MagicMock

import pytest

from app.utils.client_source import (
    CLIENT_H5_MOBILE,
    CLIENT_PC_WEB,
    CLIENT_UNKNOWN,
    CLIENT_VERIFY_MINIPROGRAM,
    MOBILE_VERIFY_CLIENTS,
    VERIFY_FORBIDDEN_DETAIL,
    detect_client_type,
    is_mobile_verify_client,
    parse_client_type_from_header,
    parse_client_type_from_user_agent,
    require_mobile_verify_client,
)
from fastapi import HTTPException


# ────────── 工具：构造伪 Request ──────────


def _make_request(headers: Optional[dict] = None):
    """构造一个最小可用的 Request mock，仅暴露 headers 字典。"""
    req = MagicMock()
    # FastAPI Request.headers 是一个类 dict，支持 .get(key)。
    h = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers = MagicMock()
    req.headers.get = lambda name, default=None: (
        headers.get(name)
        if headers and name in headers
        else h.get(name.lower(), default)
    )
    return req


# ────────── A. parse_client_type_from_header ──────────


class TestParseClientTypeFromHeader:
    def test_client_type_header_standard(self):
        req = _make_request({"Client-Type": "h5-mobile"})
        assert parse_client_type_from_header(req) == CLIENT_H5_MOBILE

    def test_x_client_type_header(self):
        req = _make_request({"X-Client-Type": "verify-miniprogram"})
        assert parse_client_type_from_header(req) == CLIENT_VERIFY_MINIPROGRAM

    def test_lowercase_header_name(self):
        req = _make_request({"client-type": "pc-web"})
        assert parse_client_type_from_header(req) == CLIENT_PC_WEB

    def test_uppercase_value_normalized(self):
        req = _make_request({"Client-Type": "H5-Mobile"})
        assert parse_client_type_from_header(req) == CLIENT_H5_MOBILE

    def test_underscore_value_tolerated(self):
        req = _make_request({"Client-Type": "h5_mobile"})
        assert parse_client_type_from_header(req) == CLIENT_H5_MOBILE

    def test_unknown_value(self):
        req = _make_request({"Client-Type": "macos-app"})
        # 不在 4 类合法值中 → 返回空字符串，留给 UA 兜底
        assert parse_client_type_from_header(req) == ""

    def test_no_header(self):
        req = _make_request({})
        assert parse_client_type_from_header(req) == ""

    def test_none_request(self):
        assert parse_client_type_from_header(None) == ""

    def test_empty_string_value(self):
        req = _make_request({"Client-Type": ""})
        assert parse_client_type_from_header(req) == ""


# ────────── B. parse_client_type_from_user_agent ──────────


class TestParseClientTypeFromUA:
    def test_ua_iphone_safari(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile/15E148"
        assert parse_client_type_from_user_agent(ua) == CLIENT_H5_MOBILE

    def test_ua_android_chrome(self):
        ua = "Mozilla/5.0 (Linux; Android 12; SM-S908B) AppleWebKit/537.36 Mobile"
        assert parse_client_type_from_user_agent(ua) == CLIENT_H5_MOBILE

    def test_ua_wechat_miniprogram(self):
        ua = (
            "Mozilla/5.0 (Linux; Android 12) MicroMessenger/8.0 NetType/WIFI Language/zh_CN MiniProgram"
        )
        assert parse_client_type_from_user_agent(ua) == CLIENT_VERIFY_MINIPROGRAM

    def test_ua_wechat_h5_in_browser(self):
        ua = "Mozilla/5.0 (Linux; Android 12) MicroMessenger/8.0 NetType/WIFI Language/zh_CN"
        # 微信内置 WebView H5 同样视作移动端可信来源
        assert parse_client_type_from_user_agent(ua) == CLIENT_H5_MOBILE

    def test_ua_windows_chrome(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        assert parse_client_type_from_user_agent(ua) == CLIENT_PC_WEB

    def test_ua_macos_chrome(self):
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0"
        assert parse_client_type_from_user_agent(ua) == CLIENT_PC_WEB

    def test_ua_linux_chrome(self):
        ua = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0"
        assert parse_client_type_from_user_agent(ua) == CLIENT_PC_WEB

    def test_ua_empty(self):
        assert parse_client_type_from_user_agent("") == CLIENT_UNKNOWN

    def test_ua_none(self):
        assert parse_client_type_from_user_agent(None) == CLIENT_UNKNOWN

    def test_ua_unrecognized(self):
        assert parse_client_type_from_user_agent("curl/8.0") == CLIENT_UNKNOWN


# ────────── C. detect_client_type 综合判定 ──────────


class TestDetectClientType:
    def test_header_overrides_ua(self):
        # Header 显式声明 h5-mobile，但 UA 是 PC：以 Header 为准
        req = _make_request({
            "Client-Type": "h5-mobile",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0)",
        })
        assert detect_client_type(req) == CLIENT_H5_MOBILE

    def test_no_header_falls_back_to_ua_pc(self):
        req = _make_request({"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"})
        assert detect_client_type(req) == CLIENT_PC_WEB

    def test_no_header_falls_back_to_ua_mobile(self):
        req = _make_request({"User-Agent": "Mozilla/5.0 (iPhone)"})
        assert detect_client_type(req) == CLIENT_H5_MOBILE

    def test_no_header_no_ua(self):
        req = _make_request({})
        assert detect_client_type(req) == CLIENT_UNKNOWN

    def test_none_request(self):
        assert detect_client_type(None) == CLIENT_UNKNOWN


# ────────── D. is_mobile_verify_client ──────────


class TestIsMobileVerifyClient:
    @pytest.mark.parametrize(
        "ct,expected",
        [
            (CLIENT_H5_MOBILE, True),
            (CLIENT_VERIFY_MINIPROGRAM, True),
            (CLIENT_PC_WEB, False),
            (CLIENT_UNKNOWN, False),
            ("", False),
            ("h5-mobile", True),
            ("H5-Mobile", True),  # 大小写宽容
            ("verify-miniprogram", True),
            ("pc-web", False),
            ("anything-else", False),
        ],
    )
    def test_only_two_clients_allowed(self, ct, expected):
        assert is_mobile_verify_client(ct) is expected

    def test_constant_set_is_correct(self):
        assert MOBILE_VERIFY_CLIENTS == frozenset(
            {CLIENT_H5_MOBILE, CLIENT_VERIFY_MINIPROGRAM}
        )


# ────────── E. require_mobile_verify_client 依赖项 ──────────


def _run_dep(req):
    """同步驱动 require_mobile_verify_client，返回值或抛 HTTPException。"""
    return asyncio.run(require_mobile_verify_client(req))


class TestRequireMobileVerifyClient:
    def test_h5_mobile_passes(self):
        req = _make_request({"Client-Type": "h5-mobile"})
        assert _run_dep(req) == CLIENT_H5_MOBILE

    def test_verify_miniprogram_passes(self):
        req = _make_request({"Client-Type": "verify-miniprogram"})
        assert _run_dep(req) == CLIENT_VERIFY_MINIPROGRAM

    def test_pc_web_blocked(self):
        req = _make_request({"Client-Type": "pc-web"})
        with pytest.raises(HTTPException) as exc:
            _run_dep(req)
        assert exc.value.status_code == 403
        assert exc.value.detail == VERIFY_FORBIDDEN_DETAIL

    def test_unknown_blocked(self):
        req = _make_request({})
        with pytest.raises(HTTPException) as exc:
            _run_dep(req)
        assert exc.value.status_code == 403

    def test_ua_pc_blocked(self):
        req = _make_request({"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"})
        with pytest.raises(HTTPException) as exc:
            _run_dep(req)
        assert exc.value.status_code == 403

    def test_ua_iphone_passes(self):
        req = _make_request({"User-Agent": "Mozilla/5.0 (iPhone)"})
        assert _run_dep(req) == CLIENT_H5_MOBILE

    def test_ua_wechat_miniprogram_passes(self):
        req = _make_request({"User-Agent": "MicroMessenger MiniProgram"})
        assert _run_dep(req) == CLIENT_VERIFY_MINIPROGRAM

    def test_header_overrides_pc_ua(self):
        # 即便 UA 是 Windows，只要 Header 显式声明 h5-mobile，依然通过
        req = _make_request({
            "Client-Type": "h5-mobile",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0)",
        })
        assert _run_dep(req) == CLIENT_H5_MOBILE

    def test_empty_header_falls_back_to_pc_ua(self):
        # Header 为空字符串 → 走 UA 兜底，UA 是 PC → 403
        req = _make_request({
            "Client-Type": "",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0)",
        })
        with pytest.raises(HTTPException):
            _run_dep(req)

    @pytest.mark.parametrize(
        "client_type,expect_pass",
        [
            ("h5-mobile", True),
            ("verify-miniprogram", True),
            ("pc-web", False),
            ("unknown", False),
            ("", False),
        ],
    )
    def test_4_categories_parametrized(self, client_type, expect_pass):
        req = _make_request({"Client-Type": client_type})
        if expect_pass:
            assert _run_dep(req) == client_type
        else:
            with pytest.raises(HTTPException):
                _run_dep(req)


# ────────── F. PRD §2.4 错误信息契约 ──────────


class TestForbiddenDetailContract:
    def test_detail_message_present(self):
        # PRD §2.4 / R-05-04：来源不可识别或为 PC → 403 Forbidden
        # detail 必须明确指引用户到手机端核销
        assert "手机端" in VERIFY_FORBIDDEN_DETAIL
        assert "核销" in VERIFY_FORBIDDEN_DETAIL

    def test_detail_is_consistent_across_calls(self):
        # 同一份常量在多次调用中保持一致，避免错误信息漂移
        req1 = _make_request({"Client-Type": "pc-web"})
        req2 = _make_request({"Client-Type": "unknown"})
        with pytest.raises(HTTPException) as e1:
            _run_dep(req1)
        with pytest.raises(HTTPException) as e2:
            _run_dep(req2)
        assert e1.value.detail == e2.value.detail == VERIFY_FORBIDDEN_DETAIL
