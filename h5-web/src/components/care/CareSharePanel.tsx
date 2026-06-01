'use client';

// [PRD-CARE-OPTIM-FINAL-V1 2026-06-01 §优化3 / §三 海报最终版] 关怀版「分享给好友」面板
// - 纯拉新分享（第 3 种邀请），落地注册引导页，完全不带「守护」意图
// - 顶部为分享卡片预览（统一文案）；底部 3 个渠道：微信好友 / 生成海报 / 复制链接
// - 「生成海报」弹出方案 A 温情暖色海报（机器人头像 + 品牌名 + 温情大标题 + 3 功能 + 小程序码占位）

import { useState } from 'react';
import { Popup } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';

interface CareSharePanelProps {
  visible: boolean;
  onClose: () => void;
  // 分享落地页（注册引导页 / 拉新链接），来自 /invite 的能力支撑
  shareUrl?: string;
  // 机器人头像（关怀模式欢迎区同款），由调用方传入完整地址
  logoUrl?: string;
}

// 统一分享文案（§优化3 + §三）
export const CARE_SHARE_SLOGAN = '我在用 宾尼小康 守护家人健康，推荐您也来试试~';

const WARM_ORANGE = '#FB8C00';
const WARM_ORANGE_DEEP = '#F4731F';
const WARM_BG = '#FFF6EC';

function ChannelIcon({ kind }: { kind: 'wechat' | 'poster' | 'copy' }) {
  const common = {
    width: 26,
    height: 26,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: WARM_ORANGE_DEEP,
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  switch (kind) {
    case 'wechat':
      return (
        <svg {...common}>
          <path d="M9 4.5C5.13 4.5 2 7.13 2 10.4c0 1.84 1.04 3.48 2.66 4.55L4 17.5l2.86-1.55c.68.16 1.4.25 2.14.25 .27 0 .54-.01.8-.04" />
          <circle cx="6.6" cy="10" r="0.7" fill={WARM_ORANGE_DEEP} stroke="none" />
          <circle cx="11.2" cy="10" r="0.7" fill={WARM_ORANGE_DEEP} stroke="none" />
          <path d="M22 14.7c0-2.7-2.6-4.9-5.8-4.9s-5.8 2.2-5.8 4.9c0 2.7 2.6 4.9 5.8 4.9 .63 0 1.24-.08 1.81-.22L20.5 21l-.55-2.04C21.13 18.13 22 16.5 22 14.7z" />
        </svg>
      );
    case 'poster':
      return (
        <svg {...common}>
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <circle cx="9" cy="9" r="1.6" />
          <path d="M20 15l-4-4-6 6" />
          <path d="M8 21v-2" />
        </svg>
      );
    case 'copy':
      return (
        <svg {...common}>
          <rect x="9" y="9" width="11" height="11" rx="2" />
          <path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5" />
        </svg>
      );
  }
}

/** 方案 A 温情暖色海报（顶部头像 + 品牌名 + 温情大标题 + 3 功能 + 小程序码占位） */
function WarmPoster({ logoUrl }: { logoUrl: string }) {
  return (
    <div
      data-testid="care-share-poster"
      style={{
        width: 300,
        borderRadius: 20,
        overflow: 'hidden',
        background: `linear-gradient(180deg, ${WARM_BG} 0%, #FFE9D2 100%)`,
        boxShadow: '0 12px 40px rgba(244,115,31,0.25)',
        margin: '0 auto',
      }}
    >
      {/* 顶部：机器人头像 + 品牌名 */}
      <div style={{ padding: '22px 20px 12px', textAlign: 'center' }}>
        <div
          style={{
            width: 76,
            height: 76,
            borderRadius: '50%',
            background: '#FFFFFF',
            border: '3px solid #FFFFFF',
            boxShadow: '0 6px 16px rgba(244,115,31,0.22)',
            margin: '0 auto 8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={logoUrl} alt="宾尼小康" style={{ width: 70, height: 70, borderRadius: '50%', objectFit: 'cover' }} />
        </div>
        <div style={{ fontSize: 18, fontWeight: 800, color: WARM_ORANGE_DEEP, letterSpacing: 1 }}>宾尼小康</div>
      </div>

      {/* 温情大标题 */}
      <div style={{ padding: '4px 22px 16px', textAlign: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#5B3A1E', lineHeight: 1.6 }}>
          我在用 <span style={{ color: WARM_ORANGE_DEEP }}>宾尼小康</span> 守护家人健康，
          <br />推荐您也来试试~
        </div>
      </div>

      {/* 中间：温馨陪伴小画面（简洁插画占位）+ 3 个核心功能 */}
      <div style={{ padding: '0 18px 14px' }}>
        <div
          aria-hidden="true"
          style={{
            height: 70,
            borderRadius: 14,
            background: 'linear-gradient(135deg, #FFD9A8 0%, #FFB877 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 34,
            marginBottom: 12,
          }}
        >
          <span>👵</span>
          <span style={{ fontSize: 22, margin: '0 6px' }}>💗</span>
          <span>👨‍👩‍👧</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-around' }}>
          {[
            { icon: '💊', label: '用药提醒' },
            { icon: '📈', label: '健康记录' },
            { icon: '🛡️', label: '家人守护' },
          ].map((f) => (
            <div key={f.label} style={{ textAlign: 'center', flex: 1 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 12,
                  background: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 20,
                  margin: '0 auto 4px',
                  boxShadow: '0 2px 8px rgba(244,115,31,0.12)',
                }}
              >
                {f.icon}
              </div>
              <div style={{ fontSize: 12, color: '#8A5A2E', fontWeight: 600 }}>{f.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部：小程序码占位 */}
      <div
        style={{
          background: '#FFFFFF',
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <div
          data-testid="care-share-poster-qr"
          style={{
            width: 64,
            height: 64,
            borderRadius: 10,
            background: '#F2F2F2',
            border: '1px dashed #C9A06A',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 22,
            flexShrink: 0,
          }}
        >
          ▦
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: WARM_ORANGE_DEEP }}>微信扫一扫</div>
          <div style={{ fontSize: 12, color: '#9A7B5C', overflow: 'hidden' }}>立即体验宾尼小康</div>
        </div>
      </div>
    </div>
  );
}

export default function CareSharePanel({ visible, onClose, shareUrl, logoUrl }: CareSharePanelProps) {
  const [posterOpen, setPosterOpen] = useState(false);
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const effectiveLogo = logoUrl || `${basePath}/binni-xiaokang-logo.png`;
  const url = shareUrl || (typeof window !== 'undefined' ? `${window.location.origin}${basePath}/invite` : '');

  const channels: Array<{ kind: 'wechat' | 'poster' | 'copy'; label: string; action: () => void }> = [
    {
      kind: 'wechat',
      label: '微信好友',
      action: () => showToast('请在微信中打开并转发给好友'),
    },
    {
      kind: 'poster',
      label: '生成海报',
      action: () => setPosterOpen(true),
    },
    {
      kind: 'copy',
      label: '复制链接',
      action: () => {
        if (navigator.clipboard) {
          navigator.clipboard
            .writeText(url)
            .then(() => showToast('链接已复制', 'success'))
            .catch(() => showToast('复制失败'));
        } else {
          showToast('复制失败');
        }
      },
    },
  ];

  return (
    <>
      <Popup
        visible={visible}
        onMaskClick={onClose}
        position="bottom"
        bodyStyle={{ borderRadius: '20px 20px 0 0' }}
        data-testid="care-share-panel"
      >
        <div style={{ padding: '18px 18px 24px' }} data-testid="care-share-panel-body">
          {/* 分享卡片预览 */}
          <div
            data-testid="care-share-card-preview"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              background: WARM_BG,
              border: `1px solid #FFE0BD`,
              borderRadius: 14,
              padding: 14,
              marginBottom: 18,
            }}
          >
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                background: '#FFFFFF',
                border: '2px solid #FFFFFF',
                boxShadow: '0 2px 8px rgba(244,115,31,0.18)',
                flexShrink: 0,
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={effectiveLogo} alt="宾尼小康" style={{ width: 48, height: 48, borderRadius: '50%', objectFit: 'cover' }} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#5B3A1E', lineHeight: 1.5 }} data-testid="care-share-slogan">
                {CARE_SHARE_SLOGAN}
              </div>
            </div>
          </div>

          {/* 3 个分享渠道 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {channels.map((c) => (
              <div
                key={c.label}
                data-testid={`care-share-channel-${c.kind}`}
                onClick={() => {
                  c.action();
                  if (c.kind !== 'poster') onClose();
                }}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, cursor: 'pointer' }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, rgba(251,140,0,0.12) 0%, rgba(244,115,31,0.12) 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <ChannelIcon kind={c.kind} />
                </div>
                <span style={{ fontSize: 13, color: '#8A5A2E' }}>{c.label}</span>
              </div>
            ))}
          </div>

          <button
            onClick={onClose}
            style={{
              width: '100%',
              marginTop: 20,
              padding: 12,
              borderRadius: 12,
              border: 'none',
              background: '#F5F5F5',
              color: '#888',
              fontSize: 14,
            }}
          >
            取消
          </button>
        </div>
      </Popup>

      {/* 海报弹层（方案 A 温情暖色） */}
      <Popup visible={posterOpen} onMaskClick={() => setPosterOpen(false)} position="bottom" bodyStyle={{ borderRadius: '20px 20px 0 0' }}>
        <div style={{ padding: '20px 18px 28px', textAlign: 'center' }} data-testid="care-share-poster-wrap">
          <WarmPoster logoUrl={effectiveLogo} />
          <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 14 }}>长按上方海报即可保存图片，分享给亲友</div>
          <button
            onClick={() => setPosterOpen(false)}
            style={{
              width: '100%',
              marginTop: 16,
              padding: 12,
              borderRadius: 12,
              border: 'none',
              background: WARM_ORANGE,
              color: '#FFF',
              fontSize: 15,
              fontWeight: 600,
            }}
          >
            完成
          </button>
        </div>
      </Popup>
    </>
  );
}
