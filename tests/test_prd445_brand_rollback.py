"""
PRD-445 · 「晴空诊室」→「宾尼小康」全域品牌名回滚 · 服务器侧非 UI 自动化测试

覆盖目标（基于影响盘点清单）：
- T01：H5 主入口可达 + 含新品牌词「宾尼小康」
- T02：登录页可达 + 含新品牌词「宾尼小康」
- T03：H5 主入口、登录页、首页 home 等关键页面**不再包含**「晴空诊室」/「晴空」字样
- T04：底部导航 home / profile / services 主路由可达
- T05：H5 主入口仍保留天蓝主色 hex（品牌色不变）
- T06：design-system-v2 静态资源可达
- T07：核心业务页（drug / checkup / health-plan / tcm / symptom）可达
- T08：landing 页含「宾尼小康」、不含「晴空诊室」
- T09：服务协议 / 隐私政策两份法律页含「宾尼小康」、不含「晴空」
"""
import urllib.request
import urllib.error
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def _get(path: str) -> tuple[int, str]:
    url = BASE_URL + path
    req = urllib.request.Request(url, headers={"User-Agent": "PRD445-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.getcode(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


# T01-T02：H5 主入口与登录页含新品牌词
@pytest.mark.parametrize("path", ["/", "/login/"])
def test_t01_t02_root_login_contains_new_brand(path: str) -> None:
    code, body = _get(path)
    assert code == 200, f"path={path} code={code}"
    assert "宾尼小康" in body, f"path={path} 缺少新品牌词「宾尼小康」"


# T03：关键页面不再包含旧品牌词「晴空诊室」/「晴空」
@pytest.mark.parametrize("path", ["/", "/login/", "/home/", "/landing/"])
def test_t03_no_legacy_brand_qingkong(path: str) -> None:
    code, body = _get(path)
    assert code == 200, f"path={path} code={code}"
    legacy_words = ["晴空诊室", "晴空"]
    found = [w for w in legacy_words if w in body]
    assert not found, f"path={path} 仍含旧品牌词: {found}"


# T04：底部导航主路由可达
@pytest.mark.parametrize("path", ["/home/", "/profile/", "/services/", "/ai/"])
def test_t04_tab_routes_reachable(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"tab route {path} code={code}"


# T05：H5 主入口仍保留天蓝主色 hex（品牌色无变化）
def test_t05_home_keeps_brand_blue() -> None:
    code, body = _get("/home/")
    assert code == 200
    has_blue = any(s in body for s in ["#0EA5E9", "#0ea5e9", "#38BDF8", "#38bdf8", "0EA5E9", "0ea5e9"])
    assert has_blue, "/home/ HTML 未发现天蓝 brand 色（应至少含 #0EA5E9 或 #38BDF8）"


# T06：design-system-v2 静态资源可达（PRD-442 设计基建回归）
@pytest.mark.parametrize("path", [
    "/design-system-v2/index.html",
    "/design-system-v2/design-tokens.css",
    "/design-system-v2/PRD-442.md",
])
def test_t06_design_system_v2_assets(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"design-system-v2 asset {path} code={code}"


# T07：核心业务页可达
@pytest.mark.parametrize("path", [
    "/drug/", "/checkup/", "/health-plan/", "/symptom/", "/tcm/",
])
def test_t07_business_routes(path: str) -> None:
    code, _ = _get(path)
    assert code == 200, f"business route {path} code={code}"


# T08：landing 页含新品牌词、不含旧品牌词
def test_t08_landing_brand_correct() -> None:
    code, body = _get("/landing/")
    assert code == 200
    assert "宾尼小康" in body, "/landing/ 缺少新品牌词「宾尼小康」"
    assert "晴空诊室" not in body, "/landing/ 仍含旧品牌词「晴空诊室」"


# T09：法律页含新品牌词、不含旧品牌词
@pytest.mark.parametrize("path", [
    "/legal/service-agreement/",
    "/legal/privacy-policy/",
])
def test_t09_legal_pages_brand_correct(path: str) -> None:
    code, body = _get(path)
    assert code == 200, f"path={path} code={code}"
    assert "宾尼小康" in body, f"path={path} 缺少「宾尼小康」"
    assert "晴空" not in body, f"path={path} 仍含「晴空」"
