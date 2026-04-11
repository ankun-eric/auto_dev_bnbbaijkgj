"""健康打卡Bug修复 + 积分规则优化 + 完善健康档案送积分 测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.points = 100
    return user


class TestCheckinPointsConfig:
    """测试打卡积分配置读取"""

    @pytest.mark.asyncio
    async def test_config_reads_new_keys(self, mock_db):
        """验证配置从新字段(healthCheckIn/healthCheckInDailyLimit)读取"""
        from app.services.checkin_points_service import get_checkin_points_config
        
        mock_config_1 = MagicMock()
        mock_config_1.config_key = "healthCheckIn"
        mock_config_1.config_value = "5"
        mock_config_2 = MagicMock()
        mock_config_2.config_key = "healthCheckInDailyLimit"
        mock_config_2.config_value = "100"
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config_1, mock_config_2]
        mock_db.execute.return_value = mock_result
        
        config = await get_checkin_points_config(mock_db)
        assert config["enabled"] == True
        assert config["per_action"] == 5
        assert config["daily_limit"] == 100

    @pytest.mark.asyncio
    async def test_config_disabled_when_zero(self, mock_db):
        """验证 healthCheckIn=0 时 enabled=False"""
        from app.services.checkin_points_service import get_checkin_points_config
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        config = await get_checkin_points_config(mock_db)
        assert config["enabled"] == False
        assert config["per_action"] == 0

    @pytest.mark.asyncio
    async def test_config_handles_invalid_values(self, mock_db):
        """验证配置值无效时使用默认值"""
        from app.services.checkin_points_service import get_checkin_points_config
        
        mock_config = MagicMock()
        mock_config.config_key = "healthCheckIn"
        mock_config.config_value = "invalid"
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_db.execute.return_value = mock_result
        
        config = await get_checkin_points_config(mock_db)
        assert config["per_action"] == 0
        assert config["enabled"] == False


class TestAwardCheckinPoints:
    """测试打卡积分发放"""

    @pytest.mark.asyncio
    async def test_award_returns_safe_default_on_exception(self, mock_db, mock_user):
        """验证积分发放异常时返回安全默认值"""
        from app.services.checkin_points_service import award_checkin_points
        
        mock_db.execute.side_effect = Exception("DB Error")
        
        result = await award_checkin_points(mock_db, mock_user, "测试打卡")
        assert result["points_earned"] == 0
        assert result["points_limit_reached"] == False

    @pytest.mark.asyncio
    async def test_no_limit_when_daily_limit_zero(self, mock_db, mock_user):
        """验证 daily_limit=0 时不限制"""
        from app.services.checkin_points_service import award_checkin_points
        
        mock_config = MagicMock()
        mock_config.config_key = "healthCheckIn"
        mock_config.config_value = "5"
        
        mock_config_result = MagicMock()
        mock_config_result.scalars.return_value.all.return_value = [mock_config]
        
        mock_today_result = MagicMock()
        mock_today_result.scalar.return_value = 999
        
        mock_db.execute.side_effect = [mock_config_result, mock_today_result]
        
        result = await award_checkin_points(mock_db, mock_user, "测试打卡")
        assert result["points_earned"] == 5


class TestAwardCompleteProfilePoints:
    """测试完善健康档案积分发放"""

    @pytest.mark.asyncio
    async def test_no_points_when_fields_incomplete(self, mock_db, mock_user):
        """验证4字段未全部填写时不发积分"""
        from app.services.checkin_points_service import award_complete_profile_points
        
        profile = MagicMock()
        profile.gender = "male"
        profile.birthday = None
        profile.height = 170
        profile.weight = 65
        
        result = await award_complete_profile_points(mock_db, mock_user, profile)
        assert result["points_earned"] == 0

    @pytest.mark.asyncio
    async def test_returns_safe_default_on_exception(self, mock_db, mock_user):
        """验证异常时返回安全默认值，不影响档案保存"""
        from app.services.checkin_points_service import award_complete_profile_points
        
        profile = MagicMock()
        profile.gender = "male"
        profile.birthday = date(1990, 1, 1)
        profile.height = 170
        profile.weight = 65
        
        mock_db.execute.side_effect = Exception("DB Error")
        
        result = await award_complete_profile_points(mock_db, mock_user, profile)
        assert result["points_earned"] == 0


class TestPointsRulesAPI:
    """测试积分规则API"""

    def test_admin_page_no_tabs(self):
        """验证前端页面不包含Tabs组件"""
        import os
        page_path = os.path.join(os.path.dirname(__file__), "..", "..", "admin-web", "src", "app", "(admin)", "points", "rules", "page.tsx")
        if os.path.exists(page_path):
            with open(page_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Tabs" not in content, "页面不应包含Tabs组件"
            assert "打卡规则" not in content, "页面不应包含打卡规则Tab"
            assert "完善健康档案" in content, "应显示'完善健康档案'"
            assert "healthCheckInDailyLimit" in content, "应包含健康打卡每日上限字段"

    def test_checkin_service_no_old_config_keys(self):
        """验证服务不再读取旧配置key"""
        import os
        svc_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "checkin_points_service.py")
        if os.path.exists(svc_path):
            with open(svc_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "checkin_points_enabled" not in content
            assert "checkin_points_per_action" not in content
            assert "checkin_points_daily_limit" not in content
