"""
[PRD-AIHOME-OPTIM-SHARE-V1 2026-06-02] AI 首页优化 · 非UI源码断言测试

本需求为纯前端 UI 调整（整理「+」圈菜单的分享相关入口、关怀模式删除 AI 对话设置、
底部分享按钮处理、欢迎区样式统一），不涉及后端 API。

由于该改动横跨 H5 / 小程序 / Flutter(安卓·苹果) 四平台，且无后端逻辑，
本测试通过对各端源码做结构化断言来验证需求点是否落地：

  需求1：「+」圈统一「🎁 分享好友」入口，删除「📤 立即分享」「🎁 邀请好友」
  需求2：关怀模式「+」圈删除「💬 发起新对话」「🔤 字体大小」（标准模式保留）
  需求3：关怀模式底部「分享好友」大按钮保留（🎁 + "分享好友"）；标准模式无底部大按钮
  需求4：标准模式欢迎区蓝绿渐变（已由 PRD-AIHOME-WELCOME-UNIFY-V1 完成，做存在性断言）

运行：python tests/test_aihome_share_optim_v1.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = [], []


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


# ───────────────────────── H5: MoreMenu 组件 ─────────────────────────
more_menu = read("h5-web/src/components/ai-chat/MoreMenu.tsx")

# 需求1：统一「🎁 分享好友」项存在且由 onShare 触发
check(
    "H5 MoreMenu: 含统一「🎁 分享好友」项（icon 🎁 + label 分享好友 + onShare）",
    re.search(r"SHARE_FRIEND_ITEM[^\n]*icon:\s*'🎁'[^\n]*label:\s*'分享好友'[^\n]*action:\s*onShare", more_menu)
    is not None,
)
# 需求1：关怀变体与标准变体复用同一 SHARE_FRIEND_ITEM（保证完全一致）
check(
    "H5 MoreMenu: 标准/关怀两变体均复用同一 SHARE_FRIEND_ITEM 保证一致",
    more_menu.count("SHARE_FRIEND_ITEM") >= 3,  # 定义 + 两处引用
)
# 需求1：删除「立即分享」与「邀请好友」菜单项（仅注释可保留，菜单项不再出现）
check(
    "H5 MoreMenu: 不再渲染「立即分享」菜单项",
    "label: '立即分享'" not in more_menu,
)
check(
    "H5 MoreMenu: 不再渲染「邀请好友」菜单项",
    "label: '邀请好友'" not in more_menu,
)
# 需求2：存在 ai-home-care / ai-home-standard 两个变体
check("H5 MoreMenu: 新增 'ai-home-care' 变体", "'ai-home-care'" in more_menu)
check("H5 MoreMenu: 新增 'ai-home-standard' 变体", "'ai-home-standard'" in more_menu)

# 关怀变体块：不含 发起新对话 / 字体大小
care_block = more_menu.split("if (menuVariant === 'ai-home-care')")[1].split("} else")[0]
check("H5 MoreMenu 关怀变体: 不含「发起新对话」", "发起新对话" not in care_block)
check("H5 MoreMenu 关怀变体: 不含「字体大小」", "字体大小" not in care_block)
check("H5 MoreMenu 关怀变体: 含「切换模式」", "切换模式" in care_block)
check("H5 MoreMenu 关怀变体: 含「会员中心」", "会员中心" in care_block)
check("H5 MoreMenu 关怀变体: 含「扫一扫」", "扫一扫" in care_block)
check("H5 MoreMenu 关怀变体: 含统一分享项", "SHARE_FRIEND_ITEM" in care_block)
check("H5 MoreMenu 关怀变体: 含「帮助与反馈」", "帮助与反馈" in care_block)

# 标准变体块：含 发起新对话 + 字体大小
std_block = more_menu.split("menuVariant === 'ai-home-standard'")[1].split("} else")[0]
check("H5 MoreMenu 标准变体: 含「发起新对话」", "发起新对话" in std_block)
check("H5 MoreMenu 标准变体: 含「字体大小」", "字体大小" in std_block)
check("H5 MoreMenu 标准变体: 含统一分享项", "SHARE_FRIEND_ITEM" in std_block)


# ───────────────────────── H5: 标准 / 关怀页面 ─────────────────────────
std_page = read("h5-web/src/app/(ai-chat)/ai-home/page.tsx")
care_page = read("h5-web/src/app/care-ai-home/page.tsx")

check("H5 标准页: MoreMenu 使用 ai-home-standard 变体", 'menuVariant="ai-home-standard"' in std_page)
check("H5 关怀页: MoreMenu 使用 ai-home-care 变体", 'menuVariant="ai-home-care"' in care_page)
check("H5 关怀页: 不再传 onInviteFriend 给 MoreMenu（入口移除）",
      "onInviteFriend=" not in care_page.split("menuVariant=\"ai-home-care\"")[1].split("/>")[0])

# 需求3：关怀模式底部「分享好友」大按钮保留，文案=分享好友、图标=🎁
share_btn_area = care_page.split("care-home-share-friend-btn")[1][:1200]
check("H5 关怀页: 底部分享大按钮文案为「分享好友」", "<span>分享好友</span>" in share_btn_area)
check("H5 关怀页: 底部分享大按钮图标为 🎁", "🎁" in share_btn_area)
check("H5 关怀页: 底部分享大按钮不再用旧文案「分享给好友」",
      "<span>分享给好友</span>" not in care_page)


# ───────────────────────── 小程序: 标准 ai / 关怀 care-ai-home ─────────────────────────
mp_ai_wxml = read("miniprogram/pages/ai/index.wxml")
mp_ai_js = read("miniprogram/pages/ai/index.js")
mp_care_wxml = read("miniprogram/pages/care-ai-home/index.wxml")
mp_care_js = read("miniprogram/pages/care-ai-home/index.js")

# 小程序标准：保留发起新对话/字体大小，删除立即分享/邀请好友，新增🎁分享好友
mp_ai_menu = mp_ai_wxml.split('data-testid="ai-home-more-menu-card"')[1].split("</view>\n\n")[0]
check("MP 标准: 菜单含「发起新对话」", "ai-home-more-menu-item-发起新对话" in mp_ai_menu)
check("MP 标准: 菜单含「字体大小」", "ai-home-more-menu-item-字体大小" in mp_ai_menu)
check("MP 标准: 菜单含「分享好友」(🎁)", "ai-home-more-menu-item-分享好友" in mp_ai_menu and "🎁" in mp_ai_menu)
check("MP 标准: 菜单删除「立即分享」", "立即分享" not in mp_ai_menu)
check("MP 标准: 菜单删除「邀请好友」", "邀请好友" not in mp_ai_menu)
check("MP 标准: JS 含 onTapShareFriend 处理", "onTapShareFriend(" in mp_ai_js)

# 小程序关怀：删除发起新对话/字体大小/立即分享/邀请好友，新增🎁分享好友
mp_care_menu = mp_care_wxml.split('data-testid="care-home-more-menu-card"')[1].split("</view>\n\n")[0]
check("MP 关怀: 菜单删除「发起新对话」", "发起新对话" not in mp_care_menu)
check("MP 关怀: 菜单删除「字体大小」", "字体大小" not in mp_care_menu)
check("MP 关怀: 菜单删除「立即分享」", "立即分享" not in mp_care_menu)
check("MP 关怀: 菜单删除「邀请好友」", "邀请好友" not in mp_care_menu)
check("MP 关怀: 菜单含「分享好友」(🎁)", "care-home-more-menu-item-分享好友" in mp_care_menu and "🎁" in mp_care_menu)
check("MP 关怀: 菜单含「切换模式/会员中心/扫一扫/帮助与反馈」",
      all(k in mp_care_menu for k in ["切换模式", "会员中心", "扫一扫", "帮助与反馈"]))
check("MP 关怀: JS 含 onTapShareFriend 处理", "onTapShareFriend(" in mp_care_js)

# 需求3：关怀底部分享大按钮保留，文案分享好友 + 🎁
mp_care_btn = mp_care_wxml.split("care-home-share-friend-btn")[1][:400]
check("MP 关怀: 底部分享按钮文案为「分享好友」", "分享好友" in mp_care_btn and "分享给好友" not in mp_care_btn)
check("MP 关怀: 底部分享按钮图标为 🎁", "🎁" in mp_care_btn)


# ───────────────────────── Flutter(安卓/苹果) 标准 AI 首页 ─────────────────────────
flutter_std = read("flutter_app/lib/screens/ai/ai_home_screen.dart")
check("Flutter 标准: 「分享好友」菜单项文案", "Text('分享好友')" in flutter_std)
check("Flutter 标准: 「分享好友」菜单项图标 🎁", "Text('🎁 '" in flutter_std)
check("Flutter 标准: 删除旧「立即分享」文案", "Text('立即分享')" not in flutter_std)


# ───────────────────────── 需求4：标准模式欢迎区蓝绿渐变 ─────────────────────────
# H5 标准模式仍保留蓝绿系渐变（已由 WELCOME-UNIFY 完成）；Flutter 标准欢迎区蓝绿渐变存在
check("Flutter 标准: 欢迎区蓝绿渐变(1976D2->43A047)",
      "Color(0xFF1976D2)" in flutter_std and "Color(0xFF43A047)" in flutter_std)
check("Flutter 标准: 欢迎区统一注释存在(WELCOME-UNIFY)",
      "PRD-AIHOME-WELCOME-UNIFY" in flutter_std)


# ───────────────────────── 汇总 ─────────────────────────
print("\n================ 测试汇总 ================")
print(f"通过: {len(PASS)}  失败: {len(FAIL)}")
if FAIL:
    print("失败用例:")
    for n in FAIL:
        print("  - " + n)
    sys.exit(1)
print("全部通过 ✅")
sys.exit(0)
