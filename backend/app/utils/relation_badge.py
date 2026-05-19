"""[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 家庭成员关系徽章字映射工具。

按"健康档案页 · 顶部成员 Tab V2"方案 §2.2 关系字徽映射规则：
- 本人 → 我
- 爸爸/父亲 → 爸
- 妈妈/母亲 → 妈
- 儿子 → 儿 ；女儿 → 女 （由"娃"细化拆分）
- 老公/老婆/丈夫/妻子/伴侣 → 爱
- 哥哥/弟弟/姐姐/妹妹 → 哥/弟/姐/妹
- 爷爷/奶奶 → 爷/奶
- 外公/外婆 → 外
- 其他亲属：取关系字段第一个字
- 无关系字段时取昵称首字
"""
from __future__ import annotations

_RELATION_BADGE_MAP: dict[str, str] = {
    # 本人
    "本人": "我",
    "自己": "我",
    "我": "我",
    # 父母
    "爸爸": "爸", "父亲": "爸", "爸": "爸",
    "妈妈": "妈", "母亲": "妈", "妈": "妈",
    # 子女（v2 微调：儿/女 拆分，不再统一显示"娃"）
    "儿子": "儿",
    "女儿": "女",
    # 配偶/伴侣
    "老公": "爱", "老婆": "爱",
    "丈夫": "爱", "妻子": "爱",
    "伴侣": "爱", "爱人": "爱",
    # 兄弟姐妹
    "哥哥": "哥", "哥": "哥",
    "弟弟": "弟", "弟": "弟",
    "姐姐": "姐", "姐": "姐",
    "妹妹": "妹", "妹": "妹",
    # 祖辈
    "爷爷": "爷", "奶奶": "奶",
    "外公": "外", "外婆": "外",
    "姥姥": "外", "姥爷": "外",
}


def relation_badge_char(relation: str | None, fallback_name: str | None = None) -> str:
    """根据关系字段返回单字徽章字符。

    优先匹配 _RELATION_BADGE_MAP；未命中时取关系字段首字；都没有则取昵称首字；
    再都没有则返回 "?"，避免渲染为空字符串。
    """
    rel = (relation or "").strip()
    if rel and rel in _RELATION_BADGE_MAP:
        return _RELATION_BADGE_MAP[rel]
    if rel:
        return rel[0]
    name = (fallback_name or "").strip()
    if name:
        return name[0]
    return "?"
