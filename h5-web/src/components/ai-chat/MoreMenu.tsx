'use client';

import { THEME } from '@/lib/theme';

interface MoreMenuProps {
  visible: boolean;
  onClose: () => void;
  onScan?: () => void;
  onFontSize?: () => void;
  onShare?: () => void;
  // [Bug 修复 v1.2 §11.1] 新增「会员中心」入口（替换原"我的硬件"语义；因健康档案里已有硬件入口）
  onMemberCenter?: () => void;

  // [PRD-AI-HOME-3TAB-WARMBLUE-V1 2026-06-01 §五] AI 首页「+ 圆圈」菜单变体：
  //   - 'ai-home-standard'：标准模式（有 AI 对话），7 项，含「发起新对话 / 字体大小」
  //   - 'ai-home-care'：关怀模式（无 AI 对话），5 项，不含「发起新对话 / 字体大小」
  //   - 'ai-home-v2'：旧统一变体（保留向后兼容，等价于标准模式但含已废弃项）
  //   两个 AI 首页变体里的「🎁 分享好友」入口（图标/文案/行为）完全一致。
  //   其它页面不传该 prop，保持原有菜单不变（向后兼容）。
  menuVariant?: 'default' | 'ai-home-v2' | 'ai-home-standard' | 'ai-home-care';
  onNewChat?: () => void;
  onSwitchMode?: () => void;
  currentModeLabel?: string;
  onInviteFriend?: () => void;
  onHelpFeedback?: () => void;
}

// [PRD-467 FR-07] ⋯ 菜单卡片视觉与首页 THEME.background 浅蓝主题打通：
//  - 背景：白色 → THEME.background (#F0F9FF)
//  - 分隔线：THEME.divider (#E5E7EB) → THEME.primaryLight 色阶下的 #BAE6FD
//  - 圆角 / 阴影 / 文字色保持不变
const MENU_BG = THEME.background; // #F0F9FF
const MENU_DIVIDER = '#BAE6FD'; // 主题浅蓝点缀色

// [Bug 修复 v1.0 §3.1.1] 金色（与会员中心皇冠/等级胶囊一致），用于「会员中心」菜单项文字加亮
const GOLD = '#E5A23B';

// [PRD-AI-HOME-3TAB-WARMBLUE-V1 2026-06-01] 方案 C 暖蓝主色，用于 ai-home-v2 菜单的模式小标签
const WARM_PRIMARY = '#3FA9F5';

export default function MoreMenu({
  visible,
  onClose,
  onScan,
  onFontSize,
  onShare,
  onMemberCenter,
  menuVariant = 'default',
  onNewChat,
  onSwitchMode,
  currentModeLabel = '标准模式',
  onInviteFriend,
  onHelpFeedback,
}: MoreMenuProps) {
  // [PRD-AI-HOME-3TAB-WARMBLUE-V1 2026-06-01 §五] AI 首页 V2 菜单：发起新对话 / 切换模式 / 邀请好友 / 帮助与反馈
  type MenuItem = {
    icon: string;
    label: string;
    action?: () => void;
    gold?: boolean;
    tag?: string;
  };

  // [PRD-AIHOME-OPTIM-SHARE-V1 2026-06-02 §需求1/2] AI 首页「⊕ 加号圈」菜单整理：
  //   - 删除「📤 立即分享」（合并进「🎁 分享好友」）与「🎁 邀请好友」（拉守护人入口不放这里）
  //   - 新增统一「🎁 分享好友」入口（图标🎁 / 文案"分享好友" / 点击弹分享面板），两版完全一致
  //   - 关怀模式无 AI 对话，删除「💬 发起新对话」「🔤 字体大小」
  //   标准模式 7 项 / 关怀模式 5 项；「🎁 分享好友」由 onShare 触发，两版行为一致。
  const SHARE_FRIEND_ITEM: MenuItem = { icon: '🎁', label: '分享好友', action: onShare };

  let items: MenuItem[];
  if (menuVariant === 'ai-home-care') {
    // 关怀模式：切换模式 / 会员中心 / 扫一扫 / 🎁分享好友 / 帮助与反馈（5 项）
    items = [
      { icon: '🔀', label: '切换模式', action: onSwitchMode, tag: currentModeLabel },
      { icon: '👑', label: '会员中心', action: onMemberCenter, gold: true },
      { icon: '📷', label: '扫一扫', action: onScan },
      SHARE_FRIEND_ITEM,
      { icon: '❓', label: '帮助与反馈', action: onHelpFeedback },
    ];
  } else if (menuVariant === 'ai-home-standard' || menuVariant === 'ai-home-v2') {
    // 标准模式：发起新对话 / 字体大小 / 切换模式 / 会员中心 / 扫一扫 / 🎁分享好友 / 帮助与反馈（7 项）
    items = [
      { icon: '💬', label: '发起新对话', action: onNewChat },
      { icon: '🔤', label: '字体大小', action: onFontSize },
      { icon: '🔀', label: '切换模式', action: onSwitchMode, tag: currentModeLabel },
      { icon: '👑', label: '会员中心', action: onMemberCenter, gold: true },
      { icon: '📷', label: '扫一扫', action: onScan },
      SHARE_FRIEND_ITEM,
      { icon: '❓', label: '帮助与反馈', action: onHelpFeedback },
    ];
  } else {
    // [PRD-467 FR-01/FR-02] 其它页面默认菜单（向后兼容）
    items = [
      { icon: '👑', label: '会员中心', action: onMemberCenter, gold: true },
      { icon: '📷', label: '扫一扫', action: onScan },
      { icon: '🔤', label: '字体大小', action: onFontSize },
      SHARE_FRIEND_ITEM,
    ];
  }

  // [BUGFIX-AI-HOME-MENU-MASK-V1 2026-06-01 §问题1] 透明遮罩铺满全屏：
  //   旧实现用 antd-mobile 顶部弹层组件（position=top），其 body 只占据顶部一小块区域，
  //   遮罩未铺满整屏，导致只有点菜单正下方那一小块才能关菜单，点别处关不掉。
  //   现改为自绘「全屏 fixed 遮罩 + 右上角菜单卡」：点遮罩任意空白处即关闭菜单，
  //   点菜单卡本身阻止冒泡（不关闭）。恢复「点任意空白处收回菜单」的原有体验。
  if (!visible) return null;

  return (
    <div
      data-testid="ai-home-more-menu-mask"
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100vw',
        height: '100vh',
        background: 'transparent',
        zIndex: 1000,
      }}
    >
      <div className="flex justify-end px-4 pt-12 pb-3">
        <div
          className="rounded-2xl overflow-hidden shadow-lg"
          onClick={(e) => e.stopPropagation()}
          style={{
            background: MENU_BG,
            border: `1px solid ${MENU_DIVIDER}`,
            minWidth: 200,
          }}
          data-testid="ai-home-more-menu-card"
        >
          {items.map((item, i) => (
            <div
              key={item.label}
              className="flex items-center gap-3 px-4 py-3 cursor-pointer active:bg-sky-100"
              style={{
                borderBottom: i < items.length - 1 ? `1px solid ${MENU_DIVIDER}` : 'none',
                minHeight: 48,
              }}
              onClick={() => { item.action?.(); onClose(); }}
              data-testid={`ai-home-more-menu-item-${item.label}`}
            >
              <span className="text-lg">{item.icon}</span>
              <span
                className="text-sm"
                style={{
                  color: item.gold ? GOLD : THEME.textPrimary,
                  fontWeight: item.gold ? 700 : 400,
                  flex: 1,
                }}
              >
                {item.label}
              </span>
              {item.tag ? (
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: WARM_PRIMARY,
                    background: '#EAF6FF',
                    borderRadius: 10,
                    padding: '2px 8px',
                    whiteSpace: 'nowrap',
                  }}
                  data-testid="ai-home-more-menu-mode-tag"
                >
                  {item.tag}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
