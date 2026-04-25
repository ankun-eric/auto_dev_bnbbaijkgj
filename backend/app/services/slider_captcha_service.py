"""滑块拼图验证码服务

Bug 修复 V1.0 / 2026-04-25：
原有字符验证码（captcha_service.py）在三端登录页字号偏小、字符旋转 + 干扰线干扰强，
用户难以识别。本模块新增「滑块拼图」验证形态，仅供商家 H5/PC + 平台管理后台登录使用，
用户端 H5 仍走旧字符验证。

核心能力：
- issue_challenge(): 从 backend/static/captcha_bg/ 随机抽底图，生成「带缺口背景图 + 缺块拼图」
- verify(): 三层校验 —— 位置对齐 ±5px + 轨迹合理性 + 失败风控锁定
- take_token(): 一次性 captcha_token 设计（5 分钟有效），登录接口取出即销毁

存储：复用 captcha_service._MemoryStore 的内存模式，新增挑战 / token 表。
"""
from __future__ import annotations

import base64
import io
import logging
import math
import random
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# ─────────────── 常量 ───────────────

BG_WIDTH = 320
BG_HEIGHT = 160
PUZZLE_SIZE = 50  # 缺口边长（正方形）
POSITION_TOLERANCE = 5  # 位置对齐允许偏差（像素）

CHALLENGE_TTL = 2 * 60  # 挑战 2 分钟过期
TOKEN_TTL = 5 * 60  # 一次性 token 5 分钟过期

LOCK_FAIL_THRESHOLD = 3  # 同 IP 连续失败 N 次锁定
LOCK_DURATION = 60  # 锁定 60 秒
FAIL_WINDOW = 60  # 失败计数窗口

TRAIL_MIN_POINTS = 5
TRAIL_MIN_DURATION_MS = 200
TRAIL_MAX_DURATION_MS = 8000

# 内置降级图（无 static/captcha_bg 文件时使用）
_BG_COLOR_PALETTE = [
    (255, 196, 156), (192, 255, 200), (180, 220, 255),
    (255, 220, 240), (220, 220, 255), (200, 240, 220),
    (255, 240, 180), (180, 240, 240),
]

# ─────────────── 数据结构 ───────────────


@dataclass
class _ChallengeEntry:
    gap_x: int
    gap_y: int
    expire_at: float
    consumed: bool = False


@dataclass
class _TokenEntry:
    expire_at: float


@dataclass
class _FailEntry:
    timestamps: List[float] = field(default_factory=list)
    locked_until: float = 0.0


# ─────────────── 内存存储 ───────────────


class _SliderStore:
    """挑战 / token / 失败计数 内存存储（线程安全）"""

    def __init__(self) -> None:
        self._challenges: dict[str, _ChallengeEntry] = {}
        self._tokens: dict[str, _TokenEntry] = {}
        self._fails: dict[str, _FailEntry] = {}
        self._mutex = Lock()

    def _gc(self) -> None:
        if random.random() > 0.05:
            return
        now = time.time()
        with self._mutex:
            for k in list(self._challenges.keys()):
                if self._challenges[k].expire_at < now:
                    self._challenges.pop(k, None)
            for k in list(self._tokens.keys()):
                if self._tokens[k].expire_at < now:
                    self._tokens.pop(k, None)
            for k in list(self._fails.keys()):
                entry = self._fails[k]
                entry.timestamps = [t for t in entry.timestamps if now - t < FAIL_WINDOW]
                if not entry.timestamps and entry.locked_until < now:
                    self._fails.pop(k, None)

    def put_challenge(self, cid: str, gap_x: int, gap_y: int) -> None:
        with self._mutex:
            self._challenges[cid] = _ChallengeEntry(
                gap_x=gap_x, gap_y=gap_y, expire_at=time.time() + CHALLENGE_TTL
            )
        self._gc()

    def take_challenge(self, cid: str) -> Optional[_ChallengeEntry]:
        with self._mutex:
            entry = self._challenges.get(cid)
            if entry is None:
                return None
            if entry.expire_at < time.time():
                self._challenges.pop(cid, None)
                return None
            if entry.consumed:
                return None
            entry.consumed = True
            return entry

    def remaining_lock(self, key: str) -> int:
        with self._mutex:
            entry = self._fails.get(key)
            if not entry:
                return 0
            remain = int(entry.locked_until - time.time())
            return max(remain, 0)

    def record_failure(self, key: str) -> int:
        now = time.time()
        with self._mutex:
            entry = self._fails.setdefault(key, _FailEntry())
            entry.timestamps = [t for t in entry.timestamps if now - t < FAIL_WINDOW]
            entry.timestamps.append(now)
            if len(entry.timestamps) >= LOCK_FAIL_THRESHOLD:
                entry.locked_until = now + LOCK_DURATION
                entry.timestamps = []
                return -1
            return len(entry.timestamps)

    def clear_failure(self, key: str) -> None:
        with self._mutex:
            self._fails.pop(key, None)

    def put_token(self, token: str) -> None:
        with self._mutex:
            self._tokens[token] = _TokenEntry(expire_at=time.time() + TOKEN_TTL)
        self._gc()

    def take_token(self, token: str) -> bool:
        """取出并销毁 token；返回是否有效"""
        with self._mutex:
            entry = self._tokens.pop(token, None)
        if entry is None:
            return False
        if entry.expire_at < time.time():
            return False
        return True


_store = _SliderStore()


# ─────────────── 背景图加载 ───────────────


def _bg_dir() -> Path:
    """backend/static/captcha_bg/ 目录"""
    return Path(__file__).resolve().parent.parent.parent / "static" / "captcha_bg"


def _list_bg_files() -> List[Path]:
    bg = _bg_dir()
    if not bg.exists():
        return []
    files = [p for p in bg.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    return files


def _load_random_bg() -> Image.Image:
    """加载一张背景图；目录无图时降级为程序生成的渐变图"""
    files = _list_bg_files()
    if files:
        try:
            img = Image.open(random.choice(files)).convert("RGB")
            img = img.resize((BG_WIDTH, BG_HEIGHT), Image.LANCZOS)
            return img
        except Exception as e:
            logger.warning("load captcha bg failed: %s; fall back to generated bg", e)
    return _generate_fallback_bg()


def _generate_fallback_bg() -> Image.Image:
    """无内置图片时的降级方案：生成两色对角渐变 + 网格 + 抽象图形"""
    c1 = random.choice(_BG_COLOR_PALETTE)
    c2 = random.choice(_BG_COLOR_PALETTE)
    img = Image.new("RGB", (BG_WIDTH, BG_HEIGHT), c1)
    draw = ImageDraw.Draw(img)
    for y in range(BG_HEIGHT):
        ratio = y / BG_HEIGHT
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        draw.line([(0, y), (BG_WIDTH, y)], fill=(r, g, b))
    # 抽象图形增加局部纹理，避免缺口轮廓被均匀色掩盖
    for _ in range(8):
        x = random.randint(-20, BG_WIDTH)
        y = random.randint(-20, BG_HEIGHT)
        radius = random.randint(20, 60)
        color = (random.randint(80, 230), random.randint(80, 230), random.randint(80, 230))
        draw.ellipse((x, y, x + radius, y + radius), outline=color, width=2)
    return img


# ─────────────── 拼图制作 ───────────────


def _puzzle_mask() -> Image.Image:
    """生成一个带凸起 / 凹陷的拼图块掩码（灰度图，255=保留，0=透明）"""
    size = PUZZLE_SIZE
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    # 主体方块
    pad = 4
    draw.rectangle((pad, pad, size - pad, size - pad), fill=255)
    # 顶部凸起小圆（拼图特征，提高辨识度）
    bump_r = 8
    cx = size // 2
    draw.ellipse((cx - bump_r, pad - bump_r, cx + bump_r, pad + bump_r), fill=255)
    # 右侧凹陷
    draw.ellipse((size - pad - bump_r, cx - bump_r, size - pad + bump_r, cx + bump_r), fill=0)
    return mask


def _make_pieces(bg: Image.Image, gap_x: int, gap_y: int) -> Tuple[Image.Image, Image.Image]:
    """根据底图和缺口位置，生成 (带缺口的背景图, 缺块拼图)"""
    mask = _puzzle_mask()
    size = PUZZLE_SIZE

    piece_region = bg.crop((gap_x, gap_y, gap_x + size, gap_y + size))
    piece = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    piece.paste(piece_region, (0, 0), mask)
    # 给拼图块加细描边，强化轮廓
    edge_draw = ImageDraw.Draw(piece)
    edge_mask = mask.filter(ImageFilter.FIND_EDGES)
    for y in range(size):
        for x in range(size):
            if edge_mask.getpixel((x, y)) > 30:
                edge_draw.point((x, y), fill=(60, 60, 60, 220))

    # 在底图上挖出缺口（用半透明灰覆盖，体现缺口位置）
    bg_with_hole = bg.copy().convert("RGBA")
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(size):
        for x in range(size):
            m = mask.getpixel((x, y))
            if m > 0:
                overlay_draw.point((x, y), fill=(40, 40, 40, 160))
    bg_with_hole.paste(overlay, (gap_x, gap_y), overlay)
    # 加缺口边线
    bg_edge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_edge_draw = ImageDraw.Draw(bg_edge)
    for y in range(size):
        for x in range(size):
            if edge_mask.getpixel((x, y)) > 30:
                bg_edge_draw.point((x, y), fill=(255, 255, 255, 220))
    bg_with_hole.paste(bg_edge, (gap_x, gap_y), bg_edge)
    return bg_with_hole.convert("RGB"), piece


def _img_to_data_url(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


# ─────────────── 公共 API ───────────────


def issue_challenge() -> dict:
    """下发一道滑块拼图挑战"""
    bg = _load_random_bg()
    # 缺口位置：x 留在右半部分（避开滑块起点 0），y 居中带随机偏移
    gap_x = random.randint(int(BG_WIDTH * 0.35), BG_WIDTH - PUZZLE_SIZE - 10)
    gap_y = random.randint(20, BG_HEIGHT - PUZZLE_SIZE - 20)

    bg_holed, puzzle = _make_pieces(bg, gap_x, gap_y)
    cid = secrets.token_urlsafe(16)
    _store.put_challenge(cid, gap_x, gap_y)

    return {
        "challenge_id": cid,
        "bg_image_base64": _img_to_data_url(bg_holed, "PNG"),
        "puzzle_image_base64": _img_to_data_url(puzzle, "PNG"),
        "puzzle_y": gap_y,
        "bg_width": BG_WIDTH,
        "bg_height": BG_HEIGHT,
        "puzzle_size": PUZZLE_SIZE,
    }


def _ip_key(ip: str) -> str:
    return f"slider_fail:ip:{ip}"


def verify(
    challenge_id: str,
    user_x: int,
    trail: List[dict],
    client_ip: Optional[str] = None,
) -> dict:
    """校验滑动结果

    返回 dict：
    - {"ok": True, "captcha_token": "...", "expires_in": 300}
    - {"ok": False, "reason": "...", "locked_seconds": N}
    """
    ip = client_ip or "unknown"
    key = _ip_key(ip)
    locked = _store.remaining_lock(key)
    if locked > 0:
        return {"ok": False, "reason": "locked", "locked_seconds": locked}

    if not challenge_id:
        return {"ok": False, "reason": "challenge_expired", "locked_seconds": 0}

    entry = _store.take_challenge(challenge_id)
    if entry is None:
        # 挑战不存在或已被使用；不计入 IP 失败（这通常是误传、不是攻击信号）
        return {"ok": False, "reason": "challenge_expired", "locked_seconds": 0}

    # 1. 位置校验
    if abs(int(user_x) - entry.gap_x) > POSITION_TOLERANCE:
        _record_fail_and_return(key, "position_mismatch")
        return _build_fail("position_mismatch", _store.remaining_lock(key))

    # 2. 轨迹校验
    trail_ok, trail_reason = _check_trail(trail, target_x=entry.gap_x)
    if not trail_ok:
        _record_fail_and_return(key, trail_reason)
        return _build_fail(trail_reason, _store.remaining_lock(key))

    # 通过
    _store.clear_failure(key)
    token = secrets.token_urlsafe(24)
    _store.put_token(token)
    return {"ok": True, "captcha_token": token, "expires_in": TOKEN_TTL}


def _build_fail(reason: str, locked_seconds: int) -> dict:
    return {"ok": False, "reason": reason, "locked_seconds": locked_seconds}


def _record_fail_and_return(key: str, reason: str) -> None:
    _store.record_failure(key)
    logger.info("slider verify failed key=%s reason=%s", key, reason)


def _check_trail(trail: List[dict], target_x: int) -> Tuple[bool, str]:
    """轨迹合理性校验：
    - 点数 >= 5
    - 总耗时 200ms ~ 8000ms
    - x 单调递增（允许小幅回退，回退总和 < 总位移 30%）
    - y 方向有抖动（max-min y >= 1）
    """
    if not isinstance(trail, list) or len(trail) < TRAIL_MIN_POINTS:
        return False, "trail_invalid"

    try:
        xs = [float(p.get("x", 0)) for p in trail]
        ys = [float(p.get("y", 0)) for p in trail]
        ts = [float(p.get("t", 0)) for p in trail]
    except Exception:
        return False, "trail_invalid"

    duration = ts[-1] - ts[0]
    if duration < TRAIL_MIN_DURATION_MS or duration > TRAIL_MAX_DURATION_MS:
        return False, "trail_invalid"

    # x 末点应接近 target_x（前端坐标系下用户拖到的位置；允许稍大容差，因为 trail.x 是相对位移）
    # 这里不强校最终 x（已在外层做 ±5 校验），仅校验单调 + 抖动
    forward = 0.0
    backward = 0.0
    for i in range(1, len(xs)):
        dx = xs[i] - xs[i - 1]
        if dx >= 0:
            forward += dx
        else:
            backward += -dx
    if forward <= 0:
        return False, "trail_invalid"
    if backward / max(forward, 1.0) > 0.3:
        return False, "trail_invalid"

    if max(ys) - min(ys) < 1:
        # 完全水平直线 → 脚本可能性极高
        return False, "trail_invalid"

    # 速度合理性：平均速度应在 [5, 4000] px/s（防止瞬移和过慢的 bot 模拟）
    if duration > 0:
        avg_speed = (xs[-1] - xs[0]) / (duration / 1000.0)
        if avg_speed < 5 or avg_speed > 4000:
            return False, "trail_invalid"

    # 简单的"非匀速"校验：标准差不能为 0（匀速直线运动是脚本特征）
    if len(xs) >= 4:
        speeds = []
        for i in range(1, len(xs)):
            dt = ts[i] - ts[i - 1]
            if dt > 0:
                speeds.append((xs[i] - xs[i - 1]) / dt)
        if len(speeds) >= 3:
            mean = sum(speeds) / len(speeds)
            var = sum((s - mean) ** 2 for s in speeds) / len(speeds)
            if var < 1e-6:
                return False, "trail_invalid"

    return True, ""


def take_token(token: Optional[str]) -> bool:
    """登录接口调用：取出并销毁 captcha_token，返回是否有效"""
    if not token:
        return False
    return _store.take_token(token)


# 测试辅助：仅用于单元测试，生产路径不会调用
def _force_lock(ip: str, seconds: int = LOCK_DURATION) -> None:
    key = _ip_key(ip)
    with _store._mutex:
        entry = _store._fails.setdefault(key, _FailEntry())
        entry.locked_until = time.time() + seconds


def _reset_store_for_test() -> None:
    with _store._mutex:
        _store._challenges.clear()
        _store._tokens.clear()
        _store._fails.clear()
