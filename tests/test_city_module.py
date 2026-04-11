"""
City Module - Non-UI Automated Tests (城市定位与切换)
Tests run against the deployed server using requests (synchronous HTTP).

Covers: public city list / hot / locate, and admin city list / hot CRUD / auth.
Admin token: POST /api/admin/login with phone + password (see ADMIN_PHONE).
"""
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
TIMEOUT = 15
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.verify = False
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _flatten_groups(groups):
    """Flatten CityListResponse.groups into a list of city dicts."""
    out = []
    for g in groups or []:
        assert isinstance(g, dict)
        for c in g.get("cities") or []:
            out.append(c)
    return out


def _short_names_from_cities(cities):
    return {c.get("short_name", "") for c in (cities or [])}


class TestCityModule:
    """TC-001 ~ TC-016: run in definition order — public tests before admin hot mutations."""

    # ── 用户端（无需认证）──

    def test_tc001_get_city_list(self, session):
        """TC-001: 获取城市列表 - groups 结构，total > 300"""
        r = session.get(
            f"{BASE_URL}/api/cities/list",
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "groups" in data and "total" in data
        assert isinstance(data["groups"], list)
        assert data["total"] > 300
        for g in data["groups"]:
            assert "letter" in g and "cities" in g
        print(f"[TC-001] OK total={data['total']} groups={len(data['groups'])}")

    def test_tc002_groups_have_letter_and_cities(self, session):
        """TC-002: 每个分组有 letter 与 cities"""
        r = session.get(f"{BASE_URL}/api/cities/list", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        for g in data["groups"]:
            assert isinstance(g["letter"], str) and len(g["letter"]) >= 1
            assert isinstance(g["cities"], list)
            for c in g["cities"]:
                for key in ("id", "name", "short_name", "first_letter"):
                    assert key in c, f"missing {key} in {c}"
        print("[TC-002] OK group structure validated")

    def test_tc003_search_keyword_beijing_cn(self, session):
        """TC-003: keyword=北京 包含北京"""
        r = session.get(
            f"{BASE_URL}/api/cities/list",
            params={"keyword": "北京"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        flat = _flatten_groups(data["groups"])
        names = " ".join(c.get("name", "") + c.get("short_name", "") for c in flat)
        assert "北京" in names, f"expected 北京 in results: {names[:200]}"
        print(f"[TC-003] OK matches={len(flat)}")

    def test_tc004_search_keyword_beijing_pinyin(self, session):
        """TC-004: keyword=beijing 返回北京"""
        r = session.get(
            f"{BASE_URL}/api/cities/list",
            params={"keyword": "beijing"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        flat = _flatten_groups(data["groups"])
        names = " ".join(c.get("name", "") for c in flat)
        assert "北京" in names, f"expected 北京 for beijing: {names[:200]}"
        print(f"[TC-004] OK matches={len(flat)}")

    def test_tc005_search_no_results(self, session):
        """TC-005: 无结果时 groups 为空或 total 为 0"""
        r = session.get(
            f"{BASE_URL}/api/cities/list",
            params={"keyword": "不存在的城市xxx"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("total", -1) == 0 or len(_flatten_groups(data.get("groups", []))) == 0
        print("[TC-005] OK empty search")

    def test_tc006_get_hot_cities_default_count(self, session):
        """TC-006: 热门城市 cities 列表，默认 12 个"""
        r = session.get(f"{BASE_URL}/api/cities/hot", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "cities" in data
        cities = data["cities"]
        assert isinstance(cities, list)
        assert len(cities) == 12, f"expected 12 hot cities, got {len(cities)}"
        print(f"[TC-006] OK hot count={len(cities)}")

    def test_tc007_hot_includes_beijing_shanghai(self, session):
        """TC-007: 热门含北京、上海"""
        r = session.get(f"{BASE_URL}/api/cities/hot", timeout=TIMEOUT)
        assert r.status_code == 200
        shorts = _short_names_from_cities(r.json().get("cities", []))
        assert "北京" in shorts
        assert "上海" in shorts
        print("[TC-007] OK 北京+上海 in hot")

    def test_tc008_locate_beijing(self, session):
        """TC-008: 经纬度定位北京"""
        r = session.get(
            f"{BASE_URL}/api/cities/locate",
            params={"lng": 116.4, "lat": 39.9},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "city" in data and "message" in data
        assert data["city"] is not None
        assert data["city"]["short_name"] == "北京"
        print("[TC-008] OK locate 北京")

    def test_tc009_locate_shanghai(self, session):
        """TC-009: 经纬度定位上海"""
        r = session.get(
            f"{BASE_URL}/api/cities/locate",
            params={"lng": 121.47, "lat": 31.23},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["city"] is not None
        assert data["city"]["short_name"] == "上海"
        print("[TC-009] OK locate 上海")

    def test_tc010_locate_invalid_extreme(self, session):
        """TC-010: 极端经纬度 — city 为 null 或最近城市"""
        r = session.get(
            f"{BASE_URL}/api/cities/locate",
            params={"lng": 179.99, "lat": -89.99},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        city = data.get("city")
        assert city is None or isinstance(city, dict)
        if city is not None:
            assert "id" in city and "name" in city
        print(f"[TC-010] OK city={city}")

    # ── 管理端（需管理员）──

    def test_tc011_admin_list_pagination(self, session, admin_headers):
        """TC-011: 管理端列表分页字段"""
        r = session.get(
            f"{BASE_URL}/api/admin/cities/list",
            headers=admin_headers,
            params={"page": 1, "page_size": 20},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("items", "total", "page", "page_size"):
            assert key in data
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert isinstance(data["items"], list)
        assert len(data["items"]) <= 20
        print(f"[TC-011] OK total={data['total']} page={data['page']}")

    def test_tc012_admin_search_keyword(self, session, admin_headers):
        """TC-012: 管理端 keyword 搜索"""
        r = session.get(
            f"{BASE_URL}/api/admin/cities/list",
            headers=admin_headers,
            params={"keyword": "北京", "page": 1, "page_size": 10},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        names = [it.get("name", "") for it in data["items"]]
        assert any("北京" in n for n in names)
        print(f"[TC-012] OK items={len(data['items'])}")

    def test_tc013_admin_get_hot(self, session, admin_headers):
        """TC-013: 管理端获取热门城市"""
        r = session.get(
            f"{BASE_URL}/api/admin/cities/hot",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "cities" in data
        assert isinstance(data["cities"], list)
        print(f"[TC-013] OK hot admin count={len(data['cities'])}")

    def test_tc014_admin_set_hot_cities(self, session, admin_headers):
        """TC-014: POST 批量设置热门城市"""
        rb = session.get(
            f"{BASE_URL}/api/cities/locate",
            params={"lng": 116.4, "lat": 39.9},
            timeout=TIMEOUT,
        )
        rs = session.get(
            f"{BASE_URL}/api/cities/locate",
            params={"lng": 121.47, "lat": 31.23},
            timeout=TIMEOUT,
        )
        assert rb.status_code == 200 and rs.status_code == 200
        bj = rb.json().get("city")
        sh = rs.json().get("city")
        assert bj and sh
        city_ids = [bj["id"], sh["id"]]

        r = session.post(
            f"{BASE_URL}/api/admin/cities/hot",
            headers=admin_headers,
            json={"city_ids": city_ids},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("message") == "热门城市设置成功"
        rh = session.get(f"{BASE_URL}/api/cities/hot", timeout=TIMEOUT)
        assert rh.status_code == 200
        hot_shorts = _short_names_from_cities(rh.json().get("cities", []))
        assert "北京" in hot_shorts and "上海" in hot_shorts
        print(f"[TC-014] OK set hot city_ids={city_ids}")

    def test_tc015_admin_remove_hot_city(self, session, admin_headers):
        """TC-015: DELETE 移除热门城市"""
        rb = session.get(
            f"{BASE_URL}/api/cities/locate",
            params={"lng": 116.4, "lat": 39.9},
            timeout=TIMEOUT,
        )
        assert rb.status_code == 200
        bj = rb.json().get("city")
        assert bj
        city_id = bj["id"]

        r = session.delete(
            f"{BASE_URL}/api/admin/cities/hot/{city_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        rh = session.get(f"{BASE_URL}/api/cities/hot", timeout=TIMEOUT)
        assert rh.status_code == 200
        shorts = _short_names_from_cities(rh.json().get("cities", []))
        assert "北京" not in shorts
        print(f"[TC-015] OK removed hot city_id={city_id}")

    def test_tc016_admin_unauthorized(self, session):
        """TC-016: 未认证访问管理端返回 401"""
        for method, path in (
            ("GET", f"{BASE_URL}/api/admin/cities/list"),
            ("GET", f"{BASE_URL}/api/admin/cities/hot"),
            ("POST", f"{BASE_URL}/api/admin/cities/hot"),
            ("DELETE", f"{BASE_URL}/api/admin/cities/hot/1"),
        ):
            if method == "GET":
                r = session.get(path, timeout=TIMEOUT)
            elif method == "POST":
                r = session.post(path, json={"city_ids": [1]}, timeout=TIMEOUT)
            else:
                r = session.delete(path, timeout=TIMEOUT)
            assert r.status_code == 401, f"{method} {path} expected 401 got {r.status_code}"
        print("[TC-016] OK all admin city endpoints return 401 without token")
