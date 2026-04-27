'use client';

import { Popup, Toast } from 'antd-mobile';
import { THEME } from '@/lib/theme';

interface SharePanelProps {
  visible: boolean;
  onClose: () => void;
  url?: string;
  title?: string;
}

export default function SharePanel({ visible, onClose, url, title }: SharePanelProps) {
  const shareUrl = url || (typeof window !== 'undefined' ? window.location.href : '');

  const items = [
    {
      icon: '💬',
      label: '微信好友',
      action: () => {
        Toast.show({ content: '请在微信中打开分享' });
      },
    },
    {
      icon: '🌐',
      label: '朋友圈',
      action: () => {
        Toast.show({ content: '请在微信中打开分享' });
      },
    },
    {
      icon: '🔗',
      label: '复制链接',
      action: () => {
        navigator.clipboard?.writeText(shareUrl).then(() => {
          Toast.show({ content: '链接已复制', icon: 'success' });
        }).catch(() => {
          Toast.show({ content: '复制失败' });
        });
      },
    },
    {
      icon: '🖼️',
      label: '生成海报',
      action: () => {
        Toast.show({ content: '海报生成中...' });
      },
    },
  ];

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="bottom"
      bodyStyle={{ borderRadius: '20px 20px 0 0' }}
    >
      <div className="px-4 pb-8 pt-4">
        <div className="text-center text-base font-bold mb-5" style={{ color: THEME.textPrimary }}>
          分享给好友
        </div>
        <div className="grid grid-cols-4 gap-4">
          {items.map(item => (
            <div
              key={item.label}
              className="flex flex-col items-center gap-2 cursor-pointer active:opacity-70"
              onClick={() => { item.action(); onClose(); }}
            >
              <div
                className="flex items-center justify-center rounded-full text-2xl"
                style={{ width: 56, height: 56, background: THEME.primaryLight }}
              >
                {item.icon}
              </div>
              <span className="text-xs" style={{ color: THEME.textSecondary }}>{item.label}</span>
            </div>
          ))}
        </div>
        <button
          className="w-full mt-6 py-3 rounded-xl text-sm font-medium"
          style={{ background: THEME.background, color: THEME.textSecondary }}
          onClick={onClose}
        >
          取消
        </button>
      </div>
    </Popup>
  );
}
