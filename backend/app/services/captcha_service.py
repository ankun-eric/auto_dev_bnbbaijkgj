"""图形验证码服务（PRD: 后台登录页滑动验证码改造为图形验证码 v1.0 / 2026-04-25）

- 4 位字符验证码（数字 2-9 + 大写字母去 OIL）
- 图片视觉规格：160×60，字号 38px，字符随机旋转 -15~15°，2~3 条干扰曲线 + 少量噪点
- 5 分钟过期、一次性使用、不区分大小写
- 同 IP / 同手机号 5 分钟内账密错误 5 次 → 锁定 10 分钟
- 验证码生成接口 IP 限流：1 秒最多 5 次
"""
from __future__ import annotations

import io
import logging
import math
import random
import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# 字符集：31 个去歧义字符（数字 2-9 + 大写字母去 O/I/L）
SAFE_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CAPTCHA_LENGTH = 4
CAPTCHA_TTL_SECONDS = 5 * 60  # 5 分钟

# 登录失败风控
LOCK_FAIL_THRESHOLD = 5            # 5 分钟内 5 次失败
FAIL_WINDOW_SECONDS = 5 * 60       # 滑动窗口 5 分钟
LOCK_DURATION_SECONDS = 10 * 60    # 锁定 10 分钟

# 验证码生成接口 IP 限流
ISSUE_RATE_WINDOW_SECONDS = 1
ISSUE_RATE_MAX = 5

# 图片视觉规格
IMG_WIDTH = 160
IMG_HEIGHT = 60
FONT_SIZE = 38


@dataclass
class _CaptchaEntry:
    code: str
    expire_at: float


class _MemoryStore:
    """简单内存存储，带 TTL；多 worker 部署时建议替换为 Redis。"""

    def __init__(self) -> None:
        self._captcha: dict[str, _CaptchaEntry] = {}
        self._fail_counter: dict[str, list[float]] = {}
        self._lock_until: dict[str, float] = {}
        self._issue_rate: dict[str, list[float]] = {}
        self._mutex = Lock()

    def _gc(self) -> None:
        now = time.time()
        if random.random() > 0.05:
            return
        with self._mutex:
            expired = [k for k, v in self._captcha.items() if v.expire_at < now]
            for k in expired:
                self._captcha.pop(k, None)
            for k in list(self._fail_counter.keys()):
                self._fail_counter[k] = [t for t in self._fail_counter[k] if now - t < FAIL_WINDOW_SECONDS]
                if not self._fail_counter[k]:
                    self._fail_counter.pop(k, None)
            for k in list(self._lock_until.keys()):
                if self._lock_until[k] < now:
                    self._lock_until.pop(k, None)
            for k in list(self._issue_rate.keys()):
                self._issue_rate[k] = [t for t in self._issue_rate[k] if now - t < ISSUE_RATE_WINDOW_SECONDS]
                if not self._issue_rate[k]:
                    self._issue_rate.pop(k, None)

    def put_captcha(self, captcha_id: str, code: str) -> None:
        with self._mutex:
            self._captcha[captcha_id] = _CaptchaEntry(code=code, expire_at=time.time() + CAPTCHA_TTL_SECONDS)
        self._gc()

    def take_captcha(self, captcha_id: str) -> Optional[str]:
        """取出并销毁（一次性使用）"""
        with self._mutex:
            entry = self._captcha.pop(captcha_id, None)
        if not entry:
            return None
        if entry.expire_at < time.time():
            return None
        return entry.code

    def is_locked(self, key: str) -> int:
        with self._mutex:
            until = self._lock_until.get(key)
        if not until:
            return 0
        remain = int(until - time.time())
        return max(remain, 0)

    def record_failure(self, key: str) -> int:
        now = time.time()
        with self._mutex:
            arr = self._fail_counter.setdefault(key, [])
            arr.append(now)
            arr[:] = [t for t in arr if now - t < FAIL_WINDOW_SECONDS]
            count = len(arr)
            if count >= LOCK_FAIL_THRESHOLD:
                self._lock_until[key] = now + LOCK_DURATION_SECONDS
                self._fail_counter.pop(key, None)
        return count

    def clear_failure(self, key: str) -> None:
        with self._mutex:
            self._fail_counter.pop(key, None)
            self._lock_until.pop(key, None)

    def acquire_issue_token(self, key: str) -> bool:
        """验证码生成接口 IP 限流（1 秒 5 次）。返回 True 表示放行。"""
        now = time.time()
        with self._mutex:
            arr = self._issue_rate.setdefault(key, [])
            arr[:] = [t for t in arr if now - t < ISSUE_RATE_WINDOW_SECONDS]
            if len(arr) >= ISSUE_RATE_MAX:
                return False
            arr.append(now)
            return True


_store = _MemoryStore()


def generate_captcha_code() -> str:
    return "".join(secrets.choice(SAFE_CHARS) for _ in range(CAPTCHA_LENGTH))


def _load_font() -> ImageFont.FreeTypeFont:
    """加载 38px 加粗字体；失败则用 PIL 默认。"""
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    )
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, FONT_SIZE)
        except Exception:
            continue
    return ImageFont.load_default()


_FONT = _load_font()


def render_captcha_png(code: str) -> bytes:
    """渲染 PNG 字节。

    规格（PRD §F1）：
    - 160 × 60，字号 38px
    - 字符随机深色（与背景对比度 ≥ 4.5:1）
    - 4 字符均匀分布，单字符宽度 ~35px
    - 每字符随机 -15~15° 轻微旋转
    - 2~3 条随机曲线
    - 少量噪点
    - 浅色随机渐变背景
    """
    width, height = IMG_WIDTH, IMG_HEIGHT

    # 浅色随机渐变背景（左上→右下）
    image = Image.new("RGB", (width, height), (255, 255, 255))
    bg_top = (
        random.randint(235, 252),
        random.randint(235, 252),
        random.randint(235, 252),
    )
    bg_bot = (
        random.randint(220, 240),
        random.randint(225, 245),
        random.randint(228, 248),
    )
    pixels = image.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(bg_top[0] * (1 - ratio) + bg_bot[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bot[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bot[2] * ratio)
        for x in range(width):
            pixels[x, y] = (r, g, b)

    draw = ImageDraw.Draw(image)

    # 字符布局：4 个字符均分宽度
    char_box_w = (width - 16) // CAPTCHA_LENGTH  # ≈ 36
    for i, ch in enumerate(code):
        ch_img = Image.new("RGBA", (char_box_w + 12, height), (0, 0, 0, 0))
        ch_draw = ImageDraw.Draw(ch_img)
        # 随机深色（确保对比度）
        color = (
            random.randint(10, 80),
            random.randint(10, 80),
            random.randint(10, 90),
        )
        # 文字垂直居中（38px 字号在 60px 高图上居中）
        text_y = max((height - FONT_SIZE) // 2 - 4, 0)
        ch_draw.text((4, text_y), ch, font=_FONT, fill=color)
        angle = random.uniform(-15, 15)
        rotated = ch_img.rotate(angle, resample=Image.BILINEAR, expand=False)
        image.paste(rotated, (8 + i * char_box_w, 0), rotated)

    # 2~3 条随机曲线
    for _ in range(random.randint(2, 3)):
        amplitude = random.randint(4, 10)
        period = random.uniform(width / 2, width)
        phase = random.uniform(0, math.pi * 2)
        y_base = random.randint(15, height - 15)
        color = (
            random.randint(80, 160),
            random.randint(80, 160),
            random.randint(80, 160),
        )
        last_pt: Optional[tuple[int, int]] = None
        for x in range(0, width, 2):
            y = int(y_base + amplitude * math.sin(2 * math.pi * x / period + phase))
            y = max(0, min(height - 1, y))
            pt = (x, y)
            if last_pt is not None:
                draw.line((last_pt, pt), fill=color, width=1)
            last_pt = pt

    # 少量噪点
    for _ in range(40):
        draw.point(
            (random.randint(0, width - 1), random.randint(0, height - 1)),
            fill=(random.randint(60, 200), random.randint(60, 200), random.randint(60, 200)),
        )

    # 轻度模糊柔和处理
    image = image.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def issue_captcha() -> tuple[str, bytes]:
    """生成新验证码：返回 (captcha_id, png_bytes)"""
    captcha_id = secrets.token_urlsafe(16)
    code = generate_captcha_code()
    _store.put_captcha(captcha_id, code)
    png_bytes = render_captcha_png(code)
    return captcha_id, png_bytes


def acquire_issue_rate(client_ip: str) -> bool:
    """验证码生成接口 IP 级限流。返回 True 放行；False 表示超出限频。"""
    return _store.acquire_issue_token(f"issue:{client_ip}")


def verify_captcha(captcha_id: Optional[str], user_input: Optional[str]) -> tuple[bool, str]:
    """校验图形验证码。返回 (ok, error_code)。

    error_code:
        ""            校验通过
        "missing"     缺少 captchaId / captchaCode（业务码 40103）
        "expired"     captchaId 不存在或已过期（业务码 40101）
        "mismatch"    答案不匹配（业务码 40102）
    """
    if not captcha_id or not user_input:
        return False, "missing"
    expected = _store.take_captcha(captcha_id)
    if not expected:
        return False, "expired"
    user_norm = (user_input or "").strip().upper()
    if expected.strip().upper() != user_norm:
        return False, "mismatch"
    return True, ""


# ────────────────── 失败次数风控 ──────────────────


def _ip_key(ip: str) -> str:
    return f"login_fail:ip:{ip}"


def _phone_key(phone: str) -> str:
    return f"login_fail:phone:{phone}"


def is_login_locked(ip: Optional[str], phone: Optional[str]) -> int:
    """返回剩余锁定秒数；0 表示未被锁定。任意维度被锁均返回 >0"""
    remain = 0
    if ip:
        remain = max(remain, _store.is_locked(_ip_key(ip)))
    if phone:
        remain = max(remain, _store.is_locked(_phone_key(phone)))
    return remain


def record_login_failure(ip: Optional[str], phone: Optional[str]) -> None:
    if ip:
        _store.record_failure(_ip_key(ip))
    if phone:
        _store.record_failure(_phone_key(phone))


def clear_login_failure(ip: Optional[str], phone: Optional[str]) -> None:
    if ip:
        _store.clear_failure(_ip_key(ip))
    if phone:
        _store.clear_failure(_phone_key(phone))
