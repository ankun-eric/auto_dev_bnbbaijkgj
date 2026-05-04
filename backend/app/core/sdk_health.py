"""[2026-05-05 SDK 健康看板] 运行时三方依赖可见性。

设计目标：
- 启动期分级自检：核心依赖缺失 → 硬失败容器退出；可选三方 SDK 缺失 → CRITICAL 日志告警，
  但不阻塞启动，并把结果写入全局快照供后台 / 接口读取。
- 提供 `refresh_snapshot` 重新检测能力（管理员后台「重新检测」按钮使用）。
- 注册表中模块名以最常见的可 import 名为准，部分 SDK 安装名与 import 名不一致，
  通过 `import_name` 与 `install_cmd` 分别表达。

复发背景：
2026-05-04 修复了支付宝 H5 测试报错「未安装 python-alipay-sdk」，但 2026-05-05 再次复发。
根因：服务器代码版本未及时更新 / Docker 镜像缓存未失效。本模块作为长期治理手段，
确保任何 SDK 缺失/异常都能在启动期与运维侧第一时间可见。

参考文档：bug 修复方案文档「支付宝 H5 测试报错 python-alipay-sdk 未安装 复发」§6 / §7
"""
from __future__ import annotations

import datetime as _dt
import importlib
import logging
from enum import Enum
from typing import Any

logger = logging.getLogger("app.sdk_health")


class DependencyLevel(str, Enum):
    CORE = "core"          # 缺失 → 硬失败容器退出
    OPTIONAL = "optional"  # 缺失 → 软告警 + 健康看板红灯


class DependencyGroup(str, Enum):
    CORE = "core"
    PAYMENT = "payment"
    SMS = "sms"
    STORAGE = "storage"
    OTHER = "other"


# 注册表：每个 SDK 一行
# 字段语义：
#   import_name : 真实 import 模块名（用于 importlib.import_module）
#   level       : core / optional
#   group       : 用于前端分组展示
#   name        : 友好中文名
#   install_cmd : 安装命令，前端「一键复制」用
#   usage       : 用途说明
SDK_REGISTRY: list[dict[str, Any]] = [
    # ── 核心运行时（缺失 → 硬失败）──
    {"import_name": "fastapi",        "level": DependencyLevel.CORE,
     "group": DependencyGroup.CORE,
     "name": "FastAPI",            "install_cmd": "pip install fastapi",
     "usage": "Web 框架（核心）"},
    {"import_name": "sqlalchemy",     "level": DependencyLevel.CORE,
     "group": DependencyGroup.CORE,
     "name": "SQLAlchemy",         "install_cmd": "pip install sqlalchemy",
     "usage": "ORM（核心）"},
    {"import_name": "aiomysql",       "level": DependencyLevel.CORE,
     "group": DependencyGroup.CORE,
     "name": "aiomysql",           "install_cmd": "pip install aiomysql",
     "usage": "MySQL 异步驱动（核心）"},
    {"import_name": "pydantic",       "level": DependencyLevel.CORE,
     "group": DependencyGroup.CORE,
     "name": "Pydantic",           "install_cmd": "pip install pydantic",
     "usage": "数据校验（核心）"},

    # ── 支付（缺失 → 软告警）──
    {"import_name": "alipay",         "level": DependencyLevel.OPTIONAL,
     "group": DependencyGroup.PAYMENT,
     "name": "支付宝 SDK",         "install_cmd": "pip install python-alipay-sdk",
     "usage": "支付宝 H5/APP/Web/扫码 支付"},
    {"import_name": "wechatpy",       "level": DependencyLevel.OPTIONAL,
     "group": DependencyGroup.PAYMENT,
     "name": "微信 SDK",           "install_cmd": "pip install wechatpy",
     "usage": "微信支付 / 公众号"},

    # ── 短信 ──
    {"import_name": "tencentcloud",   "level": DependencyLevel.OPTIONAL,
     "group": DependencyGroup.SMS,
     "name": "腾讯云 SDK",         "install_cmd": "pip install tencentcloud-sdk-python",
     "usage": "短信验证码 / 云通讯"},
    {"import_name": "aliyunsdkcore",  "level": DependencyLevel.OPTIONAL,
     "group": DependencyGroup.SMS,
     "name": "阿里云短信 SDK",     "install_cmd": "pip install aliyun-python-sdk-core",
     "usage": "阿里云短信验证码"},

    # ── 对象存储 ──
    {"import_name": "oss2",           "level": DependencyLevel.OPTIONAL,
     "group": DependencyGroup.STORAGE,
     "name": "阿里云 OSS",         "install_cmd": "pip install oss2",
     "usage": "图片/附件存储（阿里云）"},
    {"import_name": "qcloud_cos",     "level": DependencyLevel.OPTIONAL,
     "group": DependencyGroup.STORAGE,
     "name": "腾讯云 COS",         "install_cmd": "pip install cos-python-sdk-v5",
     "usage": "图片/附件存储（腾讯云）"},
]


# 全局快照：模块名 → 检测结果 dict
SDK_HEALTH_SNAPSHOT: dict[str, dict[str, Any]] = {}
# 最近一次检测时间（带时区）
SDK_HEALTH_CHECKED_AT: str | None = None


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).isoformat(timespec="seconds")


def _do_check(item: dict[str, Any]) -> dict[str, Any]:
    mod = item["import_name"]
    info: dict[str, Any] = {
        "key": mod,
        "name": item["name"],
        "level": item["level"].value,
        "group": item["group"].value,
        "install_cmd": item["install_cmd"],
        "usage": item["usage"],
        "ok": False,
        "error": None,
        "version": None,
    }
    try:
        m = importlib.import_module(mod)
        info["ok"] = True
        info["version"] = getattr(m, "__version__", None)
    except Exception as e:  # noqa: BLE001
        info["ok"] = False
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def refresh_snapshot() -> dict[str, dict[str, Any]]:
    """对注册表中所有 SDK 重新跑一次 importlib，更新全局快照。
    供启动期与「重新检测」按钮调用。
    返回新的快照副本。
    """
    global SDK_HEALTH_CHECKED_AT
    snapshot: dict[str, dict[str, Any]] = {}
    for item in SDK_REGISTRY:
        snapshot[item["import_name"]] = _do_check(item)
    SDK_HEALTH_SNAPSHOT.clear()
    SDK_HEALTH_SNAPSHOT.update(snapshot)
    SDK_HEALTH_CHECKED_AT = _now_iso()
    return dict(SDK_HEALTH_SNAPSHOT)


def get_snapshot() -> dict[str, Any]:
    """读取当前快照。若尚未初始化则触发一次检测（懒加载兜底）。"""
    if not SDK_HEALTH_SNAPSHOT:
        refresh_snapshot()
    items = list(SDK_HEALTH_SNAPSHOT.values())

    groups: dict[str, list[dict[str, Any]]] = {
        DependencyGroup.CORE.value: [],
        DependencyGroup.PAYMENT.value: [],
        DependencyGroup.SMS.value: [],
        DependencyGroup.STORAGE.value: [],
        DependencyGroup.OTHER.value: [],
    }
    for it in items:
        groups.setdefault(it["group"], []).append(it)

    total = len(items)
    ok_n = sum(1 for it in items if it["ok"])
    miss_core = sum(1 for it in items if (not it["ok"]) and it["level"] == DependencyLevel.CORE.value)
    miss_optional = sum(1 for it in items if (not it["ok"]) and it["level"] == DependencyLevel.OPTIONAL.value)

    overall_ok = (miss_core == 0) and (miss_optional == 0)
    return {
        "ok": overall_ok,
        "summary": {
            "total": total,
            "ok": ok_n,
            "missing_core": miss_core,
            "missing_optional": miss_optional,
        },
        "groups": groups,
        "checked_at": SDK_HEALTH_CHECKED_AT,
    }


def run_startup_sdk_check() -> None:
    """启动期分级自检。
    - 可选 SDK 缺失：CRITICAL 日志，不抛异常
    - 核心 SDK 缺失：CRITICAL 日志 + RuntimeError → 容器退出
    """
    snap = refresh_snapshot()
    missing_core: list[tuple[str, str]] = []
    missing_optional: list[tuple[str, str]] = []
    for mod, info in snap.items():
        if info["ok"]:
            continue
        if info["level"] == DependencyLevel.CORE.value:
            missing_core.append((mod, info["install_cmd"]))
        else:
            missing_optional.append((mod, info["install_cmd"]))

    if missing_optional:
        for mod, cmd in missing_optional:
            logger.critical(
                "[SDK-HEALTH] 可选 SDK 缺失（不影响启动，但相关功能将不可用）："
                "%s ；安装命令：%s",
                mod, cmd,
            )

    if missing_core:
        msg = (
            "[SDK-HEALTH] 核心依赖缺失，启动中止："
            + ", ".join(f"{m}（{cmd}）" for m, cmd in missing_core)
        )
        logger.critical(msg)
        raise RuntimeError(msg)

    if not missing_optional and not missing_core:
        logger.info("[SDK-HEALTH] 全部 %d 个依赖通过自检 ✅", len(snap))
