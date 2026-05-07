"""
PRD-370 BUG-FIX-LOGIN-DESIGN-ALIGN-V1
登录页 UI 版本远程开关。
四端启动时拉取本接口，决定使用 v2（设计稿对齐版）或 v1（旧版兜底）。
回滚预案：如新版上线后核心登录接口错误率 > 1% 或转化率下降 > 15%，
将开关切回 'v1' 即可全量降级到旧 UI，无需重新发版。
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["登录 UI 配置"])

# 默认使用新版 v2（设计稿对齐版本）
_DEFAULT_LOGIN_UI_VERSION = "v2"

# 内存级远程开关，可通过 PUT 接口切换
_login_ui_state: dict = {"version": _DEFAULT_LOGIN_UI_VERSION}


class LoginUiVersionResponse(BaseModel):
    version: str
    rollback_supported: bool = True


class LoginUiVersionUpdate(BaseModel):
    version: str  # "v1" | "v2"


@router.get("/api/config/login_ui_version", response_model=LoginUiVersionResponse)
async def get_login_ui_version():
    """四端登录页拉取的远程开关，无需鉴权。"""
    return LoginUiVersionResponse(
        version=_login_ui_state.get("version", _DEFAULT_LOGIN_UI_VERSION),
        rollback_supported=True,
    )


@router.put("/api/admin/config/login_ui_version", response_model=LoginUiVersionResponse)
async def update_login_ui_version(payload: LoginUiVersionUpdate):
    """运营管理端切换 UI 版本，仅支持 v1 / v2。"""
    if payload.version not in ("v1", "v2"):
        # 兜底回退到默认值
        _login_ui_state["version"] = _DEFAULT_LOGIN_UI_VERSION
    else:
        _login_ui_state["version"] = payload.version
    return LoginUiVersionResponse(
        version=_login_ui_state["version"],
        rollback_supported=True,
    )
