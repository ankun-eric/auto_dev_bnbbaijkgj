"""图形验证码服务

视觉规格（v1.5 / 2026-04-26 — 字符放大 + 锁深色 + 加描边 + 浅色干扰）：
- 4 位字符验证码（数字 2-9 + 大写字母去 OIL）
- CSS 显示尺寸 = 物理像素 = 160 × 60（保持 v1.4 画布尺寸不变，登录表单零侵入）
- 字号 48px（v1.4 的 38 → 48；字符高度约占画布 65%~70%）
- 字符颜色锁深色：HSL 亮度 25%~45%、饱和度 40%~80%（v1.4 完全随机 → v1.5 锁深色）
- 字符加 1px 同色系深色描边（v1.4 无描边 → v1.5 加描边，深色背景下也清晰）
- 字符随机旋转 -10~10°（v1.4 ±15° → v1.5 ±10°，更可读）
- 字符均分 + ±2px 抖动间距
- 1~2 条干扰曲线 + 颜色锁浅色 HSL 亮度 70%+（v1.4 2~3 条 + 颜色随机 → v1.5 1~2 条 + 浅色）
- 噪点约 20 个 + 颜色锁浅色 HSL 亮度 75%+（v1.4 ~40 个 + 颜色随机 → v1.5 ~20 个 + 浅色）
- 5 分钟过期、一次性使用、不区分大小写（业务规则完全不变）
- 同 IP / 同手机号 5 分钟内账密错误 5 次 → 锁定 10 分钟
- 验证码生成接口 IP 限流：1 秒最多 5 次

变更说明：
- v1.0：初始版本，160×60 / 38px / -15~15° / 2~3 条曲线 / 40 噪点
- v1.1~v1.2：曾尝试放大画布，因布局错位被回退（视觉规格未保留）
- v1.3：保持画布 160×60，但启用 2× 高 DPI（实际 320×120），字号放大到 96px
- v1.4：彻底回退到 v1.0 视觉规格，取消 2× DPI、字号回归 38、旋转/干扰/噪点全部回退到 v1.0 原值
- v1.5：保持画布 160×60；字号 38 → 48；字符颜色锁深色 + 加 1px 描边；
        旋转 ±15° → ±10°；干扰曲线 2~3 → 1~2 条且锁浅色；噪点 40 → 20 且锁浅色。
        业务逻辑完全不变，前端无需任何改动，H5 等比缩放后字符自动跟随放大。
"""
from __future__ import annotations

import colorsys
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

# 图片视觉规格（v1.5：保持画布 160×60；字号 48；锁深色 + 描边；浅色干扰）
IMG_WIDTH = 160
IMG_HEIGHT = 60
FONT_SIZE = 48


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
    """加载 v1.5 的 48px 加粗字体；失败则用 PIL 默认。"""
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


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def _random_dark_color() -> tuple[int, int, int]:
    """v1.5 字符主色：HSL 亮度 25%~45%、饱和度 40%~80%（深色，肉眼一眼可辨）"""
    h = random.random()
    s = random.uniform(0.40, 0.80)
    l = random.uniform(0.25, 0.45)
    return _hsl_to_rgb(h, s, l)


def _darker_outline(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """v1.5 字符描边色：基于主色加深 ~15% 亮度，构成同色系深色描边"""
    r, g, b = (c / 255.0 for c in color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, l - 0.15)
    return _hsl_to_rgb(h, s, l)


def _random_light_color(min_lightness: float) -> tuple[int, int, int]:
    """v1.5 干扰元素颜色：HSL 高亮度浅色，退到背景层"""
    h = random.random()
    s = random.uniform(0.10, 0.35)
    l = random.uniform(min_lightness, min(min_lightness + 0.20, 0.95))
    return _hsl_to_rgb(h, s, l)


def render_captcha_png(code: str) -> bytes:
    """渲染 PNG 字节（v1.5 视觉规格）。

    规格：
    - 物理像素 = CSS 显示尺寸 = 160 × 60（保持 v1.4 画布不变）
    - 字号 48px，字符撑满画布约 65%~70%
    - 字符颜色锁深色 HSL(亮度 25~45%、饱和度 40~80%)，加 1px 同色系深色描边
    - 4 字符均匀分布 + ±2px 抖动
    - 每字符随机 -10~10° 轻微旋转
    - 1~2 条浅色干扰曲线（HSL 亮度 70%+）
    - 约 20 个浅色噪点（HSL 亮度 75%+）
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

    # ───── 干扰先画到背景层（曲线 + 噪点），让字符叠在最上层最显眼 ─────

    # v1.5：1~2 条浅色干扰曲线（颜色锁定 HSL 亮度 70%+）
    for _ in range(random.randint(1, 2)):
        amplitude = random.randint(4, 9)
        period = random.uniform(width / 2, width)
        phase = random.uniform(0, math.pi * 2)
        y_base = random.randint(15, height - 15)
        color = _random_light_color(min_lightness=0.70)
        last_pt: Optional[tuple[int, int]] = None
        for x in range(0, width, 2):
            y = int(y_base + amplitude * math.sin(2 * math.pi * x / period + phase))
            y = max(0, min(height - 1, y))
            pt = (x, y)
            if last_pt is not None:
                draw.line((last_pt, pt), fill=color, width=1)
            last_pt = pt

    # v1.5：约 20 个浅色噪点（颜色锁定 HSL 亮度 75%+）
    for _ in range(20):
        draw.point(
            (random.randint(0, width - 1), random.randint(0, height - 1)),
            fill=_random_light_color(min_lightness=0.75),
        )

    # ───── 字符布局：4 个字符均分宽度 + ±2px 抖动 ─────
    # 上下各留 6px padding（v1.5 规格），48px 字号在 60px 高画布内合适
    padding_x = 8
    char_box_w = (width - 2 * padding_x) // CAPTCHA_LENGTH  # ≈ 36
    # 单字符渲染画布需更大以容纳 48px 字号 + 旋转 + 描边
    ch_canvas_w = char_box_w + 16
    ch_canvas_h = height + 16

    for i, ch in enumerate(code):
        ch_img = Image.new("RGBA", (ch_canvas_w, ch_canvas_h), (0, 0, 0, 0))
        ch_draw = ImageDraw.Draw(ch_img)

        # v1.5：字符颜色锁深色 + 1px 同色系深色描边
        color = _random_dark_color()
        outline = _darker_outline(color)

        # 文字垂直居中（48px 字号在 60+16 高画布上居中，留 6px 上下安全 padding）
        text_y = (ch_canvas_h - FONT_SIZE) // 2 - 4
        text_x = (ch_canvas_w - char_box_w) // 2

        # 1px 同色系深色描边：在主字符上下左右各偏移 1px 描一遍
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ch_draw.text((text_x + dx, text_y + dy), ch, font=_FONT, fill=outline)
        # 主字符（深色）
        ch_draw.text((text_x, text_y), ch, font=_FONT, fill=color)

        # v1.5：±10° 旋转
        angle = random.uniform(-10, 10)
        rotated = ch_img.rotate(angle, resample=Image.BILINEAR, expand=False)

        # ±2px 间距抖动
        jitter_x = random.randint(-2, 2)
        jitter_y = random.randint(-2, 2)
        paste_x = padding_x + i * char_box_w - (ch_canvas_w - char_box_w) // 2 + jitter_x
        paste_y = -8 + jitter_y
        image.paste(rotated, (paste_x, paste_y), rotated)

    # 轻度模糊柔和处理（不影响字符可读性）
    image = image.filter(ImageFilter.SMOOTH)
    # 转为 128 色自适应调色板 + 优化输出
    # （v1.5 比 v1.4 多了描边和深浅对比，128 色保留更细腻的描边过渡）
    image = image.convert("P", palette=Image.ADAPTIVE, colors=128)
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
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
