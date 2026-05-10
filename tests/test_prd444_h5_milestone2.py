"""
PRD-442 里程碑 2 · H5 端「晴空诊室」品牌色全量落地服务器侧非UI自动化测试

覆盖：
- T01：H5 主入口可达 + 含「晴空诊室」品牌词
- T02：登录页可达 + 含「晴空诊室」品牌词
- T03：底部导航 home / profile / services 主路由可达
- T04：AI 主战场 ai-home / chat-history / health-archive 可达
- T05：drug-chat / checkup / health-plan 可达
- T06：PRD-442 设计基建静态资源（design-system-v2）可达（回归保障）
- T07：design-tokens.css 含 brand-500 (#0ea5e9) 天蓝主色
- T08：H5 主入口 HTML 不含旧绿色 hex（#52c41a / #389e0d / #13c2c2）
- T09：H5 主入口 HTML 不含旧紫色 hex（#5B6CFF / #4A5AE8）
- T10：H5 主入口 HTML 不含旧品牌词「宾尼小康」
"""
import re
import urllib.request
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def _get(path: str) -> tuple[int, str]:
    url = BASE_URL + path
    req = urllib.request.Request(url, headers={"User-Agent": "PRD444-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.getcode(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


# T01-T05：核心路由可达性
@pytest.mark.parametrize("path,must_contain", [
    ("/", "晴空诊室"),
    ("/login/", "晴空诊室"),
])
def test_t01_t02_root_login_brand(path: str, must_contain: str) -> None:
    code, body = _get(path)
    assert code == 200, f"path={path} code={code}"
    assert must_contain in body, f"path={path} missing '{must_contain}'"


@pytest.mark.parametrize("path", [
    "/home/",
    "/profile/",
    "/services/",
    "/ai/",
])
def test_t03_tabs_routes(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"tab route {path} code={code}"


@pytest.mark.parametrize("path", [
    "/ai-home/",
    "/chat-history/",
    "/health-archive/",
    "/ai-settings/",
])
def test_t04_ai_chat_routes(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"ai-chat route {path} code={code}"


@pytest.mark.parametrize("path", [
    "/drug/",
    "/checkup/",
    "/health-plan/",
    "/symptom/",
    "/tcm/",
])
def test_t05_business_routes(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"business route {path} code={code}"


# T06：PRD-442 设计基建回归
@pytest.mark.parametrize("path", [
    "/design-system-v2/index.html",
    "/design-system-v2/design-tokens.css",
    "/design-system-v2/icons.json",
    "/design-system-v2/PRD-442.md",
])
def test_t06_design_system_v2_assets(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"design-system-v2 asset {path} code={code}"


# T07：design-tokens.css 含天蓝主色
def test_t07_design_tokens_contains_brand_500() -> None:
    code, body = _get("/design-system-v2/design-tokens.css")
    assert code == 200
    assert "--color-brand-500: #0ea5e9" in body, "design-tokens.css 未含天蓝 brand-500"
    assert "--color-brand-400: #38bdf8" in body, "design-tokens.css 未含天蓝 brand-400"


# T08：主入口不含旧绿色硬编码
def test_t08_home_no_legacy_green() -> None:
    code, body = _get("/home/")
    assert code == 200
    legacy_greens = ["#52c41a", "#52C41A", "#389e0d", "#389E0D", "#13c2c2", "#13C2C2"]
    found = [c for c in legacy_greens if c in body]
    assert not found, f"/home/ 含旧绿色 hex: {found}"


# T09：主入口不含旧紫色硬编码
def test_t09_home_no_legacy_purple() -> None:
    code, body = _get("/home/")
    assert code == 200
    legacy_purples = ["#5B6CFF", "#5b6cff", "#4A5AE8", "#4a5ae8", "#8B5CF6"]
    found = [c for c in legacy_purples if c in body]
    assert not found, f"/home/ 含旧紫色 hex: {found}"


# T10：主入口不含旧品牌词
def test_t10_home_no_legacy_brand() -> None:
    code, body = _get("/home/")
    assert code == 200
    legacy_brands = ["宾尼小康", "宾尼诊所", "宾尼健康"]
    found = [b for b in legacy_brands if b in body]
    assert not found, f"/home/ 含旧品牌词: {found}"


# T11：主入口含天蓝主色 hex（任一形式）
def test_t11_home_contains_brand_blue() -> None:
    code, body = _get("/home/")
    assert code == 200
    has_blue = any(s in body for s in ["#0EA5E9", "#0ea5e9", "#38BDF8", "#38bdf8", "0EA5E9", "0ea5e9"])
    assert has_blue, "/home/ HTML 未发现天蓝 brand 色（应至少含 #0EA5E9 或 #38BDF8）"


# T12：login 页不含旧绿色
def test_t12_login_no_legacy_green() -> None:
    code, body = _get("/login/")
    assert code == 200
    legacy_greens = ["#52c41a", "#52C41A", "#389e0d", "#13c2c2"]
    found = [c for c in legacy_greens if c in body]
    assert not found, f"/login/ 含旧绿色 hex: {found}"
