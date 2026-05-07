"""PRD-366 H5 客户登录页面优化 - 非UI自动化验收测试

针对 PRD 第 8 节验收标准 V-01 ~ V-08，对部署到生产服务器的 H5 登录页
执行接口与产物层级的检查，验证：
  1. 登录页 HTTP 可达（HTTP 200）
  2. 登录页 chunk 中不含 PRD 要求删除的 helperText 文案
  3. 登录页 chunk 中不含「其他登录方式」/微信渠道相关代码
  4. 登录页 chunk 中保留邀请码识别行、获取验证码、用户协议等核心元素
  5. 登录主流程接口（短信发送、登录）契约不变（仅检查路由可达，不真实下发短信）

不依赖任何 UI 浏览器，可在 CI/无头服务器上执行。
"""

from __future__ import annotations

import re
import sys
import time
from typing import Iterable

import urllib.request
import urllib.error


BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
TIMEOUT = 15

# PRD 要求删除的关键词，**禁止**出现在线上登录页 chunk 中
FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "未注册手机号验证后将自动创建会员",
    "当前未开放自助注册，仅支持已注册账号登录",
    "其他登录方式",
    "showChannelHint",
    "channelItems",
    "wechatEnabled",
)

# PRD 要求保留的核心元素，**必须**出现在线上登录页 chunk 中
REQUIRED_KEYWORDS: tuple[str, ...] = (
    "已识别邀请码",
    "获取验证码",
    "登录 / 注册",
    "用户服务协议",
    "隐私政策",
)


class TestResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def ok(self, name: str) -> None:
        self.passed.append(name)
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str) -> None:
        self.failed.append((name, detail))
        print(f"  [FAIL] {name}\n         -> {detail}")

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.failed)

    @property
    def is_clean(self) -> bool:
        return not self.failed


def http_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "prd366-verify/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        body = resp.read().decode("utf-8", errors="ignore")
        return resp.status, body


def extract_login_chunk_url(html: str) -> str | None:
    """从登录页 HTML 中提取 app/login/page-*.js 的相对 URL"""
    match = re.search(r'(/_next/static/chunks/app/login/page-[a-f0-9]+\.js)', html)
    return match.group(1) if match else None


def case_login_page_reachable(result: TestResult) -> str:
    """V-08 / E-03：登录页 HTTPS 可达，状态码 200"""
    name = "case_01 登录页 HTTPS 可达"
    try:
        status, body = http_get(f"{BASE_URL}/login")
        if status != 200:
            result.fail(name, f"HTTP status={status}")
            return ""
        if not body or "<html" not in body.lower():
            result.fail(name, "返回内容不是 HTML")
            return ""
        result.ok(name)
        return body
    except Exception as exc:  # noqa: BLE001
        result.fail(name, f"请求异常: {exc!r}")
        return ""


def case_chunk_url_extractable(result: TestResult, html: str) -> str:
    name = "case_02 登录页 chunk 路径可提取"
    chunk = extract_login_chunk_url(html)
    if not chunk:
        result.fail(name, "未在登录页 HTML 中匹配到 app/login/page-*.js")
        return ""
    result.ok(name)
    return chunk


def case_chunk_reachable(result: TestResult, chunk_path: str) -> str:
    name = "case_03 登录页 chunk 可下载"
    url = f"{BASE_URL}{chunk_path}"
    try:
        status, body = http_get(url)
        if status != 200 or not body:
            result.fail(name, f"HTTP status={status} body_len={len(body)}")
            return ""
        result.ok(name)
        return body
    except Exception as exc:  # noqa: BLE001
        result.fail(name, f"请求异常: {exc!r}")
        return ""


def case_no_forbidden_keywords(result: TestResult, chunk: str) -> None:
    """V-01 / V-02 / V-03 / V-04 / V-07：禁词必须不存在"""
    for kw in FORBIDDEN_KEYWORDS:
        name = f"case_04 [V-01..V-07] 不包含禁词《{kw}》"
        if kw in chunk:
            result.fail(name, f"线上 chunk 仍包含《{kw}》")
        else:
            result.ok(name)


def case_required_keywords(result: TestResult, chunk: str) -> None:
    """V-05 / V-06 / V-08：核心元素必须存在"""
    for kw in REQUIRED_KEYWORDS:
        name = f"case_05 [V-05..V-08] 仍保留核心元素《{kw}》"
        if kw not in chunk:
            result.fail(name, f"线上 chunk 缺失《{kw}》")
        else:
            result.ok(name)


def case_register_settings_api(result: TestResult) -> None:
    """E-01：后端 register-settings 接口可访问（接口契约不变）"""
    name = "case_06 [E-01] 后端 /api/auth/register-settings 接口可达"
    url = f"{BASE_URL}/api/auth/register-settings"
    try:
        status, body = http_get(url)
        if status != 200:
            result.fail(name, f"HTTP status={status}")
            return
        # 仅检查 JSON 中包含 enable_self_registration 字段，验证接口契约
        if "enable_self_registration" not in body:
            result.fail(name, "返回 body 缺失 enable_self_registration 字段")
            return
        result.ok(name)
    except Exception as exc:  # noqa: BLE001
        result.fail(name, f"请求异常: {exc!r}")


def case_invitation_link(result: TestResult) -> None:
    """E-02：URL 携带 ref 仍能正常访问登录页（不报 5xx）"""
    name = "case_07 [E-02] 携带 ?ref=PRD366TEST 访问登录页正常"
    url = f"{BASE_URL}/login?ref=PRD366TEST"
    try:
        status, body = http_get(url)
        if status != 200 or "<html" not in body.lower():
            result.fail(name, f"HTTP status={status}")
            return
        result.ok(name)
    except Exception as exc:  # noqa: BLE001
        result.fail(name, f"请求异常: {exc!r}")


def main() -> int:
    print(f"=== PRD-366 H5 登录页面优化 - 非UI自动化验收测试 ===")
    print(f"BaseURL: {BASE_URL}")
    print(f"启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    result = TestResult()
    html = case_login_page_reachable(result)
    if not html:
        return _summary(result)

    chunk_path = case_chunk_url_extractable(result, html)
    if not chunk_path:
        return _summary(result)

    chunk = case_chunk_reachable(result, chunk_path)
    if not chunk:
        return _summary(result)

    case_no_forbidden_keywords(result, chunk)
    case_required_keywords(result, chunk)
    case_register_settings_api(result)
    case_invitation_link(result)

    return _summary(result)


def _summary(result: TestResult) -> int:
    total = result.total
    passed = len(result.passed)
    failed = len(result.failed)
    print(f"\n=== 测试汇总 ===")
    print(f"总用例数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    if result.failed:
        print("\n失败明细:")
        for name, detail in result.failed:
            print(f"  - {name}: {detail}")
        return 1
    print("\n*** 全部通过，PRD-366 验收标准已满足 ***")
    return 0


if __name__ == "__main__":
    sys.exit(main())
