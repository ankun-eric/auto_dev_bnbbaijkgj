'use client';

import { Popup } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import { THEME } from '@/lib/theme';
import { SvgGradientDefs, AI_ACTION_BAR_GRADIENT_ID } from './AiActionBar';

interface SharePanelProps {
  visible: boolean;
  onClose: () => void;
  url?: string;
  title?: string;
}

/**
 * [PRD-440] 转发弹窗内的渠道小图标统一升级为方案 C 双色渐变风（#6a8dff → #b07cff），
 * 与 AI 回答下方操作栏的图标视觉风格保持一致。
 */
function ChannelIcon({ kind }: { kind: 'wechat' | 'moments' | 'copy' | 'poster' }) {
  const stroke = `url(#${AI_ACTION_BAR_GRADIENT_ID})`;
  const common = {
    width: 28,
    height: 28,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke,
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  switch (kind) {
    case 'wechat':
      // 简化的对话气泡图（微信好友）
      return (
        <svg {...common}>
          <path d="M9 4.5C5.13 4.5 2 7.13 2 10.4c0 1.84 1.04 3.48 2.66 4.55L4 17.5l2.86-1.55c.68.16 1.4.25 2.14.25 .27 0 .54-.01.8-.04" />
          <circle cx="6.6" cy="10" r="0.7" fill={stroke} stroke="none" />
          <circle cx="11.2" cy="10" r="0.7" fill={stroke} stroke="none" />
          <path d="M22 14.7c0-2.7-2.6-4.9-5.8-4.9s-5.8 2.2-5.8 4.9c0 2.7 2.6 4.9 5.8 4.9 .63 0 1.24-.08 1.81-.22L20.5 21l-.55-2.04C21.13 18.13 22 16.5 22 14.7z" />
        </svg>
      );
    case 'moments':
      // 朋友圈：相机+点
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <circle cx="12" cy="12" r="3.2" />
          <circle cx="12" cy="12" r="1" fill={stroke} stroke="none" />
        </svg>
      );
    case 'copy':
      return (
        <svg {...common}>
          <rect x="9" y="9" width="11" height="11" rx="2" />
          <path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5" />
        </svg>
      );
    case 'poster':
      return (
        <svg {...common}>
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <circle cx="8.5" cy="9.5" r="1.5" />
          <path d="M21 16l-5-5-7 7" />
        </svg>
      );
  }
}

export default function SharePanel({ visible, onClose, url }: SharePanelProps) {
  const shareUrl = url || (typeof window !== 'undefined' ? window.location.href : '');

  const items: Array<{ kind: 'wechat' | 'moments' | 'copy' | 'poster'; label: string; action: () => void }> = [
    {
      kind: 'wechat',
      label: '微信好友',
      action: () => {
        showToast('请在微信中打开分享');
      },
    },
    {
      kind: 'moments',
      label: '朋友圈',
      action: () => {
        showToast('请在微信中打开分享');
      },
    },
    {
      kind: 'copy',
      label: '复制链接',
      action: () => {
        navigator.clipboard?.writeText(shareUrl).then(() => {
          showToast('链接已复制', 'success');
        }).catch(() => {
          showToast('复制失败');
        });
      },
    },
    {
      kind: 'poster',
      label: '生成海报',
      action: () => {
        showToast('海报生成中...');
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
      <SvgGradientDefs />
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
                className="flex items-center justify-center rounded-full"
                style={{
                  width: 56,
                  height: 56,
                  background: 'linear-gradient(135deg, rgba(106,141,255,0.1) 0%, rgba(176,124,255,0.1) 100%)',
                }}
              >
                <ChannelIcon kind={item.kind} />
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
