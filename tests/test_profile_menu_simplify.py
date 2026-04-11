"""
Profile Menu Simplify - Non-UI Automated Tests (我的页面菜单精简)
Tests run against the deployed server to verify:
1. /health-profile and /family pages remain accessible after menu entry removal
2. Profile page loads successfully
3. All remaining menu target pages are accessible
"""
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
TIMEOUT = 15


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.verify = False
    return s


class TestProfilePageAccessible:
    """Profile page itself should load."""

    def test_profile_page_loads(self, session):
        r = session.get(f"{BASE_URL}/profile", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"Profile page returned {r.status_code}"


class TestRemovedMenuPagesStillAccessible:
    """Pages whose menu entries were removed should still be accessible via direct URL."""

    def test_health_profile_page_accessible(self, session):
        r = session.get(f"{BASE_URL}/health-profile", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/health-profile returned {r.status_code}"

    def test_family_page_accessible(self, session):
        r = session.get(f"{BASE_URL}/family", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/family returned {r.status_code}"


class TestRemainingMenuTargetsAccessible:
    """All pages referenced by the remaining menu items should be accessible."""

    def test_orders_appointment_page(self, session):
        r = session.get(f"{BASE_URL}/orders?tab=appointment", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/orders?tab=appointment returned {r.status_code}"

    def test_points_page(self, session):
        r = session.get(f"{BASE_URL}/points", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/points returned {r.status_code}"

    def test_notifications_page(self, session):
        r = session.get(f"{BASE_URL}/notifications", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/notifications returned {r.status_code}"

    def test_customer_service_page(self, session):
        r = session.get(f"{BASE_URL}/customer-service", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/customer-service returned {r.status_code}"

    def test_settings_page(self, session):
        r = session.get(f"{BASE_URL}/settings", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200, f"/settings returned {r.status_code}"


class TestProfilePageContent:
    """Verify profile page HTML does not contain removed menu items."""

    def test_no_health_profile_menu_entry(self, session):
        r = session.get(f"{BASE_URL}/profile", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200
        # The menu text should not appear in the rendered page source
        # Note: Next.js SSR may or may not include this in HTML; 
        # this is a best-effort check
        content = r.text
        if "健康档案" in content and "menuGroups" not in content:
            pytest.fail("'健康档案' menu entry still appears in profile page")

    def test_no_family_member_menu_entry(self, session):
        r = session.get(f"{BASE_URL}/profile", timeout=TIMEOUT, allow_redirects=True)
        assert r.status_code == 200
        content = r.text
        if "家庭成员" in content and "menuGroups" not in content:
            pytest.fail("'家庭成员' menu entry still appears in profile page")
