import pytest
from app.core.price_formatter import _strip_trailing_zeros


class TestStripTrailingZeros:
    """测试价格格式化器 _strip_trailing_zeros 函数"""

    def test_integer_float(self):
        """19.00 → 19"""
        assert _strip_trailing_zeros(19.0) == 19
        assert isinstance(_strip_trailing_zeros(19.0), int)

    def test_one_decimal(self):
        """19.10 → 19.1"""
        assert _strip_trailing_zeros(19.1) == 19.1

    def test_two_decimals(self):
        """19.12 → 19.12（不变）"""
        assert _strip_trailing_zeros(19.12) == 19.12

    def test_zero(self):
        """0.00 → 0"""
        assert _strip_trailing_zeros(0.0) == 0
        assert isinstance(_strip_trailing_zeros(0.0), int)

    def test_half(self):
        """0.50 → 0.5"""
        assert _strip_trailing_zeros(0.5) == 0.5

    def test_hundred(self):
        """100.00 → 100"""
        assert _strip_trailing_zeros(100.0) == 100
        assert isinstance(_strip_trailing_zeros(100.0), int)

    def test_negative(self):
        """-5.00 → -5"""
        assert _strip_trailing_zeros(-5.0) == -5
        assert isinstance(_strip_trailing_zeros(-5.0), int)

    def test_none(self):
        """None 保持不变"""
        assert _strip_trailing_zeros(None) is None

    def test_string(self):
        """字符串保持不变"""
        assert _strip_trailing_zeros("hello") == "hello"

    def test_integer(self):
        """整数保持不变"""
        assert _strip_trailing_zeros(19) == 19

    def test_dict(self):
        """字典中的 float 值被格式化"""
        input_data = {"sale_price": 19.0, "name": "test", "original_price": 39.1}
        expected = {"sale_price": 19, "name": "test", "original_price": 39.1}
        assert _strip_trailing_zeros(input_data) == expected

    def test_list(self):
        """列表中的 float 值被格式化"""
        input_data = [19.0, 19.1, 19.12]
        expected = [19, 19.1, 19.12]
        assert _strip_trailing_zeros(input_data) == expected

    def test_nested(self):
        """嵌套结构中的 float 值被格式化"""
        input_data = {
            "items": [
                {"price": 19.0, "name": "A"},
                {"price": 19.10, "name": "B"},
            ],
            "total": 38.1,
        }
        expected = {
            "items": [
                {"price": 19, "name": "A"},
                {"price": 19.1, "name": "B"},
            ],
            "total": 38.1,
        }
        assert _strip_trailing_zeros(input_data) == expected

    def test_bool_not_affected(self):
        """布尔值不受影响（Python 中 bool 是 int 的子类）"""
        assert _strip_trailing_zeros(True) is True
        assert _strip_trailing_zeros(False) is False
