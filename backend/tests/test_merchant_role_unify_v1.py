"""[PRD v1.0 §R1 / §R3 / §B1] 商家角色统一治理 — 单元测试

覆盖范围（不依赖完整 DB fixture，pure unit）：
  * R1：_normalize_role_code / _normalize_merchant_role_code 把
        verifier/staff/owner/manager 4 个历史别名归一化到 boss/store_manager/finance/clerk
  * R1：admin 后端 ROLE_NAME_MAP 中 4 角色中文名正确
  * B1：路由冲突扫描 — /api/merchant/profile 必须只命中 1 个 endpoint
  * B1：scan_route_conflicts.collect_conflicts 函数对人造重复路由能正确识别
"""
import pytest


# -------- R1 角色归一化 --------

class _Stub:
    """模拟 FastAPI Route：仅需要 path / methods / endpoint 三个属性。"""

    def __init__(self, path, methods, endpoint):
        self.path = path
        self.methods = methods
        self.endpoint = endpoint


def _ep(name, module="testmod"):
    f = lambda: None  # noqa: E731
    f.__name__ = name
    f.__module__ = module
    return f


def test_admin_normalize_role_code_legacy_aliases():
    from app.api.admin_merchant import _normalize_role_code
    assert _normalize_role_code("verifier") == "clerk"
    assert _normalize_role_code("staff") == "clerk"
    assert _normalize_role_code("owner") == "boss"
    assert _normalize_role_code("manager") == "store_manager"
    # 4 角色本身不变
    assert _normalize_role_code("boss") == "boss"
    assert _normalize_role_code("store_manager") == "store_manager"
    assert _normalize_role_code("finance") == "finance"
    assert _normalize_role_code("clerk") == "clerk"
    # 大小写 / 空白 兼容
    assert _normalize_role_code("  Verifier  ") == "clerk"
    assert _normalize_role_code(None) is None
    assert _normalize_role_code("") is None


def test_account_security_normalize_role_code_legacy_aliases():
    from app.api.account_security import _normalize_merchant_role_code
    assert _normalize_merchant_role_code("verifier") == "clerk"
    assert _normalize_merchant_role_code("staff") == "clerk"
    assert _normalize_merchant_role_code("owner") == "boss"
    assert _normalize_merchant_role_code("manager") == "store_manager"
    assert _normalize_merchant_role_code("clerk") == "clerk"
    assert _normalize_merchant_role_code(None) is None


def test_admin_role_name_map_only_4_roles_official_names():
    from app.api.admin_merchant import ROLE_NAME_MAP
    # 4 个官方 role_code 必须全部存在并对应正确中文
    assert ROLE_NAME_MAP.get("boss") == "老板"
    assert ROLE_NAME_MAP.get("store_manager") == "店长"
    assert ROLE_NAME_MAP.get("finance") == "财务"
    assert ROLE_NAME_MAP.get("clerk") == "店员"


def test_admin_role_to_member_role_only_4_roles():
    """4 角色统一治理后，ROLE_TO_MEMBER_ROLE 仅保留 4 个 key（不应再包含 manager/verifier/staff/owner 别名）。"""
    from app.api.admin_merchant import ROLE_TO_MEMBER_ROLE
    assert set(ROLE_TO_MEMBER_ROLE.keys()) == {"boss", "store_manager", "finance", "clerk"}


# -------- B1 路由冲突扫描 --------

def test_scan_route_conflicts_detect_duplicate_paths():
    from backend.scripts.scan_route_conflicts import collect_conflicts  # type: ignore

    class _App:
        def __init__(self, routes):
            self.routes = routes

    routes = [
        _Stub("/api/merchant/profile", {"GET"}, _ep("h_a", "mod1")),
        _Stub("/api/merchant/profile", {"GET"}, _ep("h_b", "mod2")),
        _Stub("/api/merchant/orders", {"GET"}, _ep("h_c", "mod3")),
    ]
    conflicts = collect_conflicts(_App(routes))
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["path"] == "/api/merchant/profile"
    assert c["method"] == "GET"
    assert len(c["endpoints"]) == 2


def test_scan_route_conflicts_no_false_positive():
    from backend.scripts.scan_route_conflicts import collect_conflicts  # type: ignore

    class _App:
        def __init__(self, routes):
            self.routes = routes

    routes = [
        _Stub("/api/merchant/profile", {"GET"}, _ep("h_a", "mod1")),
        _Stub("/api/merchant/profile", {"PUT"}, _ep("h_b", "mod2")),  # 不同 method 不算冲突
        _Stub("/api/merchant/orders", {"GET"}, _ep("h_c", "mod3")),
    ]
    conflicts = collect_conflicts(_App(routes))
    assert conflicts == []


def test_real_app_has_no_merchant_profile_get_conflict():
    """[B1 验收] 真实 FastAPI app 中 GET /api/merchant/profile 必须只有 1 个实现。

    PRD §B1 根因：此前 backend/app/api/merchant.py 与 account_security.py
    都注册了同路径同方法的 GET /api/merchant/profile，导致前端被覆盖。
    本测试确保未来不会再次回退。
    """
    try:
        from app.main import app  # type: ignore
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"app 未能加载: {e}")
    bucket: dict[tuple[str, str], list[str]] = {}
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        endpoint = getattr(r, "endpoint", None)
        if not path or endpoint is None:
            continue
        ep_name = f"{getattr(endpoint, '__module__', '?')}.{getattr(endpoint, '__name__', '?')}"
        for m in methods:
            bucket.setdefault((path, m.upper()), []).append(ep_name)
    eps = bucket.get(("/api/merchant/profile", "GET"), [])
    assert len(eps) == 1, f"GET /api/merchant/profile 必须仅有 1 个实现，实际：{eps}"
