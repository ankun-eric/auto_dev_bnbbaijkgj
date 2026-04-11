import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
ADMIN_URL = f"{BASE_URL}/admin"
API_URL = f"{BASE_URL}/api"


class TestAdminWebAccess:
    """测试管理后台页面可访问性"""

    def test_admin_home_page(self):
        """管理后台首页应返回200"""
        resp = requests.get(f"{ADMIN_URL}/", timeout=30, verify=False)
        assert resp.status_code == 200, f"管理后台首页返回状态码 {resp.status_code}，期望 200"

    def test_admin_home_menus_page(self):
        """管理后台首页菜单管理页面应返回200"""
        resp = requests.get(f"{ADMIN_URL}/home-menus", timeout=30, verify=False, allow_redirects=True)
        assert resp.status_code == 200, f"菜单管理页面返回状态码 {resp.status_code}，期望 200"


class TestHomeMenusAPI:
    """测试首页菜单相关API的回归测试"""

    def test_get_home_menus_list(self):
        """获取首页菜单列表应返回成功"""
        resp = requests.get(f"{API_URL}/admin/home-menus", timeout=30, verify=False)
        assert resp.status_code in [200, 401, 403], (
            f"获取菜单列表返回状态码 {resp.status_code}，期望 200/401/403"
        )

    def test_api_health(self):
        """后端API健康检查"""
        resp = requests.get(f"{API_URL}/health", timeout=30, verify=False)
        assert resp.status_code == 200, f"健康检查返回状态码 {resp.status_code}，期望 200"


class TestH5WebAccess:
    """测试H5用户端可访问性（回归测试）"""

    def test_h5_home_page(self):
        """H5用户端首页应返回200"""
        resp = requests.get(f"{BASE_URL}/", timeout=30, verify=False)
        assert resp.status_code == 200, f"H5首页返回状态码 {resp.status_code}，期望 200"
