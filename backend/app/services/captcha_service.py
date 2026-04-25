"""图形验证码服务

PRD §M7：图形验证码 + 登录失败风控
- 4 位字符（数字 + 大小写字母，避开易混淆字符）
- 干扰线 + 字符扭曲 + 彩色背景
- 5 分钟过期
- captcha_id 与验证码绑定，用后即销毁（防重放）
- 同 IP / 同手机号 5 次失败即锁 15 分钟
"""
from __future__ import annotations

import io
import logging
import random
import secrets
import string
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# 排除易混淆字符 0/O、1/l/I/i
SAFE_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
CAPTCHA_LENGTH = 4
CAPTCHA_TTL_SECONDS = 5 * 60  # 5 分钟
LOCK_FAIL_THRESHOLD = 5
LOCK_DURATION_SECONDS = 15 * 60  # 15 分钟
FAIL_WINDOW_SECONDS = 15 * 60


@dataclass
class _CaptchaEntry:
    code: str
    expire_at: float


class _MemoryStore:
    """简单内存存储，带 TTL；多 worker 部署时建议替换为 Redis。

    本项目当前未引入 Redis，使用模块级单例线程安全字典。FastAPI 单 worker
    模式下足够；多 worker 时同一 captcha_id 可能落到不同 worker，但因为
    captcha 是登录前的一次性短期 token，可接受最差情况下用户多刷一次的体验
    成本，避免引入 Redis 部署依赖。
    """

    def __init__(self) -> None:
        self._captcha: dict[str, _CaptchaEntry] = {}
        self._fail_counter: dict[str, list[float]] = {}
        self._lock_until: dict[str, float] = {}
        self._mutex = Lock()

    def _gc(self) -> None:
        now = time.time()
        # 限制 GC 频率，避免每次都遍历
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

    def put_captcha(self, captcha_id: str, code: str) -> None:
        with self._mutex:
            self._captcha[captcha_id] = _CaptchaEntry(code=code, expire_at=time.time() + CAPTCHA_TTL_SECONDS)
        self._gc()

    def take_captcha(self, captcha_id: str) -> Optional[str]:
        """取出并销毁（防重放）"""
        with self._mutex:
            entry = self._captcha.pop(captcha_id, None)
        if not entry:
            return None
        if entry.expire_at < time.time():
            return None
        return entry.code

    def is_locked(self, key: str) -> int:
        """返回剩余锁定秒数；0 表示未锁定"""
        with self._mutex:
            until = self._lock_until.get(key)
        if not until:
            return 0
        remain = int(until - time.time())
        return max(remain, 0)

    def record_failure(self, key: str) -> int:
        """记录一次失败，返回当前累计失败次数。失败 >= 阈值时自动加锁。"""
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


_store = _MemoryStore()


def generate_captcha_code() -> str:
    return "".join(secrets.choice(SAFE_CHARS) for _ in range(CAPTCHA_LENGTH))


def render_captcha_png(code: str) -> bytes:
    """渲染 PNG 字节，干扰线 + 字符扭曲 + 彩色背景"""
    width, height = 140, 48
    # 浅色随机背景
    bg = (
        random.randint(220, 250),
        random.randint(220, 250),
        random.randint(220, 250),
    )
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    # 字体：尝试系统字体，失败则用默认
    font: ImageFont.ImageFont
    font_size = 30
    font = None  # type: ignore
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # 字符位置 + 旋转 + 颜色
    char_width = (width - 16) // CAPTCHA_LENGTH
    for i, ch in enumerate(code):
        # 单字符渲染到独立透明图层后旋转，再粘贴
        ch_img = Image.new("RGBA", (char_width + 8, height), (255, 255, 255, 0))
        ch_draw = ImageDraw.Draw(ch_img)
        color = (random.randint(20, 130), random.randint(20, 130), random.randint(20, 160))
        ch_draw.text((4, random.randint(0, 8)), ch, font=font, fill=color)
        angle = random.uniform(-25, 25)
        rotated = ch_img.rotate(angle, resample=Image.BILINEAR, expand=False)
        image.paste(rotated, (8 + i * char_width, 0), rotated)

    # 干扰线
    for _ in range(random.randint(4, 7)):
        x1 = random.randint(0, width - 1)
        y1 = random.randint(0, height - 1)
        x2 = random.randint(0, width - 1)
        y2 = random.randint(0, height - 1)
        draw.line(
            ((x1, y1), (x2, y2)),
            fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)),
            width=1,
        )

    # 干扰点
    for _ in range(80):
        draw.point(
            (random.randint(0, width - 1), random.randint(0, height - 1)),
            fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
        )

    # 轻度模糊
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


def verify_captcha(captcha_id: Optional[str], user_input: Optional[str]) -> bool:
    """校验图形验证码；校验后立即销毁（不论成功与否）"""
    if not captcha_id or not user_input:
        return False
    expected = _store.take_captcha(captcha_id)
    if not expected:
        return False
    return expected.strip().lower() == user_input.strip().lower()


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
