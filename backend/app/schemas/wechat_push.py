from typing import Optional

from pydantic import BaseModel


class WechatPushConfigResponse(BaseModel):
    enable_wechat_push: bool = False
    wechat_app_id: Optional[str] = None
    has_wechat_app_secret: bool = False
    order_notify_template: Optional[str] = None
    service_notify_template: Optional[str] = None


class WechatPushConfigUpdate(BaseModel):
    enable_wechat_push: Optional[bool] = None
    wechat_app_id: Optional[str] = None
    wechat_app_secret: Optional[str] = None
    order_notify_template: Optional[str] = None
    service_notify_template: Optional[str] = None
