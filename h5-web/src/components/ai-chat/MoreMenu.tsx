'use client';

import { Popup } from 'antd-mobile';
import { THEME } from '@/lib/theme';

interface MoreMenuProps {
  visible: boolean;
  onClose: () => void;
  onScan?: () => void;
  onFontSize?: () => void;
  onShare?: () => void;
  // [Bug 修复 v1.2 §11.1] 新增「会员中心」入口（替换原"我的硬件"语义；因健康档案里已有硬件入口）
  onMemberCenter?: () => void;

  // [PRD-AI-HOME-3TAB-WARMBLUE-V1 2026-06-01 §五] AI 首页「+ 圆圈」菜单 V2：
  //   当 menuVariant === 'ai-home-v2' 时，渲染 PRD 指定的 4 项：
  //   发起新对话 / 切换模式（带当前模式小标签）/ 邀请好友 / 帮助与反馈
  //   其它页面（如关怀首页）不传该 prop，保持原有菜单不变（向后兼容）。
  menuVariant?: 'default' | 'ai-home-v2';
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

  // [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] AI 首页「⊕ 加号圈」菜单合并：
  //   标准版 / 关怀版去重后统一为 8 项，两版完全一致，顺序按「高频在前」：
  //   1.💬发起新对话 2.🔀切换模式 3.👑会员中心 4.🎁邀请好友
  //   5.📷扫一扫 6.🔤字体大小 7.📤立即分享 8.❓帮助与反馈
  const items: MenuItem[] = menuVariant === 'ai-home-v2'
    ? [
        { icon: '💬', label: '发起新对话', action: onNewChat },
        { icon: '🔀', label: '切换模式', action: onSwitchMode, tag: currentModeLabel },
        { icon: '👑', label: '会员中心', action: onMemberCenter, gold: true },
        { icon: '🎁', label: '邀请好友', action: onInviteFriend },
        { icon: '📷', label: '扫一扫', action: onScan },
        { icon: '🔤', label: '字体大小', action: onFontSize },
        { icon: '📤', label: '立即分享', action: onShare },
        { icon: '❓', label: '帮助与反馈', action: onHelpFeedback },
      ]
    : [
        // [PRD-467 FR-01/FR-02] 「扫一扫」「字体大小」可点击；会员中心金色加亮
        { icon: '👑', label: '会员中心', action: onMemberCenter, gold: true },
        { icon: '📷', label: '扫一扫', action: onScan },
        { icon: '🔤', label: '字体大小', action: onFontSize },
        { icon: '📤', label: '立即分享', action: onShare },
      ];

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="top"
      bodyStyle={{
        borderRadius: '0 0 16px 16px',
        padding: 0,
        background: 'transparent',
      }}
    >
      <div className="flex justify-end px-4 pt-12 pb-3">
        <div
          className="rounded-2xl overflow-hidden shadow-lg"
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
    </Popup>
  );
}
