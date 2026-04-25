"""图形验证码服务单元测试

PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）
覆盖：
- 字符集仅含 31 个去歧义字符
- 长度固定 4 位
- 一次性使用（取出即销毁）
- 大小写不敏感
- 缺字段 → missing；过期/不存在 → expired；不匹配 → mismatch
- IP 限流（1 秒 5 次）
- 失败风控（5 分钟 5 次 → 锁 10 分钟）
- 渲染 PNG 字节非空
"""
import time

import pytest

from app.services import captcha_service as cs


def test_char_set_strict():
    code = cs.generate_captcha_code()
    assert len(code) == 4
    assert all(ch in cs.SAFE_CHARS for ch in code)
    forbidden = set("01OILoil")
    assert not (set(code) & forbidden)


def test_issue_then_verify_success():
    cid, png = cs.issue_captcha()
    assert isinstance(cid, str) and len(cid) > 8
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    code = cs._store._captcha[cid].code  # 通过内部读取真实答案
    ok, err = cs.verify_captcha(cid, code)
    assert ok and err == ""


def test_verify_case_insensitive():
    cid, _ = cs.issue_captcha()
    code = cs._store._captcha[cid].code
    ok, err = cs.verify_captcha(cid, code.lower())
    assert ok


def test_verify_one_time_use():
    cid, _ = cs.issue_captcha()
    code = cs._store._captcha[cid].code
    ok1, _ = cs.verify_captcha(cid, code)
    ok2, err2 = cs.verify_captcha(cid, code)
    assert ok1 is True
    assert ok2 is False
    assert err2 == "expired"


def test_verify_missing_returns_missing():
    ok, err = cs.verify_captcha(None, "ABCD")
    assert not ok and err == "missing"
    ok, err = cs.verify_captcha("anyid", None)
    assert not ok and err == "missing"


def test_verify_unknown_id_returns_expired():
    ok, err = cs.verify_captcha("not-exist-id", "ABCD")
    assert not ok and err == "expired"


def test_verify_mismatch():
    cid, _ = cs.issue_captcha()
    ok, err = cs.verify_captcha(cid, "ZZZZ")
    assert not ok and err == "mismatch"


def test_issue_rate_limit():
    ip = "10.10.10.10"
    # 清空状态
    cs._store._issue_rate.pop(f"issue:{ip}", None)
    for _ in range(cs.ISSUE_RATE_MAX):
        assert cs.acquire_issue_rate(ip) is True
    # 第 6 次应该失败
    assert cs.acquire_issue_rate(ip) is False


def test_login_failure_lock_after_threshold():
    ip = "10.10.10.11"
    phone = "13900000001"
    cs.clear_login_failure(ip, phone)
    assert cs.is_login_locked(ip, phone) == 0
    for _ in range(cs.LOCK_FAIL_THRESHOLD):
        cs.record_login_failure(ip, phone)
    remain = cs.is_login_locked(ip, phone)
    assert 0 < remain <= cs.LOCK_DURATION_SECONDS


def test_lock_by_phone_only():
    """同手机号的账号在不同 IP 也应被锁"""
    phone = "13900000002"
    cs.clear_login_failure("1.1.1.1", phone)
    cs.clear_login_failure("2.2.2.2", phone)
    for _ in range(cs.LOCK_FAIL_THRESHOLD):
        cs.record_login_failure("1.1.1.1", phone)
    # 改 IP，但同手机号
    assert cs.is_login_locked("9.9.9.9", phone) > 0


def test_clear_login_failure_unlocks():
    ip = "10.10.10.12"
    phone = "13900000003"
    cs.clear_login_failure(ip, phone)
    for _ in range(cs.LOCK_FAIL_THRESHOLD):
        cs.record_login_failure(ip, phone)
    assert cs.is_login_locked(ip, phone) > 0
    cs.clear_login_failure(ip, phone)
    assert cs.is_login_locked(ip, phone) == 0


def test_render_png_size():
    png = cs.render_captcha_png("AB23")
    assert png.startswith(b"\x89PNG")
    # PIL 渲染出的 PNG 至少几百字节
    assert len(png) > 500


def test_v14_visual_spec_physical_pixels_160x60():
    """v1.4 视觉规格回退验证：PNG 物理像素必须严格等于 CSS 显示尺寸 160 × 60。"""
    import io as _io
    from PIL import Image as _Image

    png = cs.render_captcha_png("AB23")
    img = _Image.open(_io.BytesIO(png))
    assert img.size == (160, 60), f"v1.4 物理像素必须为 160x60，实际为 {img.size}"
    assert cs.IMG_WIDTH == 160
    assert cs.IMG_HEIGHT == 60


def test_v14_font_size_38():
    """v1.4 视觉规格回退验证：字号必须回归 38px（与 v1.0 一致）。"""
    assert cs.FONT_SIZE == 38, f"v1.4 字号必须为 38，实际为 {cs.FONT_SIZE}"


def test_v14_no_super_sampling_scale():
    """v1.4 视觉规格回退验证：不得再保留 SCALE / 2x DPI 等放大常量分支。"""
    assert not hasattr(cs, "SCALE"), "v1.4 应已删除 SCALE 常量（取消 2× DPI）"


def test_v14_png_file_size_le_3kb():
    """v1.4 视觉规格回退验证：单张 PNG 文件体积 ≤ 3 KB。"""
    sizes = [len(cs.render_captcha_png("AB23")) for _ in range(20)]
    assert max(sizes) <= 3 * 1024, f"v1.4 PNG 体积必须 ≤3KB，最大值实际为 {max(sizes)}"
