'use client';

import { Popup } from 'antd-mobile';
import { THEME } from '@/lib/theme';

interface MoreMenuProps {
  visible: boolean;
  onClose: () => void;
  onScan?: () => void;
  onFontSize?: () => void;
  onShare?: () => void;
}

export default function MoreMenu({ visible, onClose, onScan, onFontSize, onShare }: MoreMenuProps) {
  const items = [
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
          style={{ background: THEME.cardBg, minWidth: 160 }}
        >
          {items.map((item, i) => (
            <div
              key={item.label}
              className="flex items-center gap-3 px-4 py-3 cursor-pointer active:bg-gray-50"
              style={{ borderBottom: i < items.length - 1 ? `1px solid ${THEME.divider}` : 'none' }}
              onClick={() => { item.action?.(); onClose(); }}
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
