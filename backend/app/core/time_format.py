from datetime import datetime
from typing import Optional


def format_bj(dt: Optional[datetime]) -> Optional[str]:
    """将 datetime 格式化为北京时间字符串 "YYYY-MM-DD HH:mm:ss" """
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")
