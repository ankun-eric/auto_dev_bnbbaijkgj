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
}

// [PRD-467 FR-07] ⋯ 菜单卡片视觉与首页 THEME.background 浅蓝主题打通：
//  - 背景：白色 → THEME.background (#F0F9FF)
//  - 分隔线：THEME.divider (#E5E7EB) → THEME.primaryLight 色阶下的 #BAE6FD
//  - 圆角 / 阴影 / 文字色保持不变
const MENU_BG = THEME.background; // #F0F9FF
const MENU_DIVIDER = '#BAE6FD'; // 主题浅蓝点缀色

export default function MoreMenu({ visible, onClose, onScan, onFontSize, onShare, onMemberCenter }: MoreMenuProps) {
  // [PRD-467 FR-01/FR-02] 「扫一扫」「字体大小」可点击：action 由父组件挂接到 onScan / onFontSize
  // 注意：点击后 onClose 仍会被调用以关闭⋯菜单，与字号 popover 互斥（FR-02）
  // [会员中心优化 PRD v2.0 §3.1] 会员中心提到第一项（替换原"我的设备"语义），并加入金色皇冠图标
  const items = [
    { icon: '👑', label: '会员中心', action: onMemberCenter },
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
            minWidth: 160,
          }}
          data-testid="ai-home-more-menu-card"
        >
          {items.map((item, i) => (
            <div
              key={item.label}
              className="flex items-center gap-3 px-4 py-3 cursor-pointer active:bg-sky-100"
              style={{
                borderBottom: i < items.length - 1 ? `1px solid ${MENU_DIVIDER}` : 'none',
              }}
              onClick={() => { item.action?.(); onClose(); }}
              data-testid={`ai-home-more-menu-item-${item.label}`}
            >
              <span className="text-lg">{item.icon}</span>
              <span className="text-sm" style={{ color: THEME.textPrimary }}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </Popup>
  );
}
