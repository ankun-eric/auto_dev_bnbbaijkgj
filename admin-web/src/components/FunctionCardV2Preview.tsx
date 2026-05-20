/**
 * [PRD-AICHAT-FUNCCARD-V2 2026-05-20]
 *
 * 管理后台"卡片预览浮层"内使用的 FunctionCardV2 复刻渲染器。
 * 视觉规范 / token 与 h5-web 端 `FunctionCardV2.tsx` 严格一致，
 * 用于在 375x667 手机框内 1:1 还原 H5 真机效果。
 *
 * 注意：本组件**纯展示**，不绑定任何交互；点击主按钮仅打印预览日志。
 * 如要修改视觉细节，请同步修改 h5-web 端的源组件。
 */
'use client';

import React from 'react';

export interface FunctionCardV2PreviewData {
  title: string;
  subtitle?: string | null;
  coverImage?: string | null;
  icon?: string | null;
  iconType?: 'url' | 'emoji' | 'default' | string | null;
  buttonSubDesc?: string | null;
  buttonText?: string;
}

const COLORS = {
  bg: '#FFFFFF',
  border: '#E0F2FE',
  shadow: '0 2px 12px rgba(2, 132, 199, 0.10)',
  titlePrimary: '#0F172A',
  titleSecondary: '#64748B',
  btnSubDesc: '#94A3B8',
  primary: '#0EA5E9',
  primaryDark: '#0284C7',
  iconBg: 'linear-gradient(135deg, #ECFEFF 0%, #CFFAFE 100%)',
  btnGradient: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
  btnShadow: '0 4px 12px rgba(2, 132, 199, 0.25)',
};

function isValidImageUrl(s: any): boolean {
  if (typeof s !== 'string') return false;
  const t = s.trim();
  if (!t) return false;
  if (t.startsWith('http://') || t.startsWith('https://')) return true;
  if (t.startsWith('/') || t.startsWith('./') || t.startsWith('data:image/') || t.startsWith('blob:')) return true;
  return false;
}

function HeaderMedia({ data }: { data: FunctionCardV2PreviewData }) {
  const iconType = data.iconType || 'default';
  if (data.coverImage && isValidImageUrl(data.coverImage)) {
    return (
      <div
        data-testid="fcv2-preview-cover-image"
        style={{
          width: '100%',
          height: 140,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          backgroundImage: `url(${data.coverImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundColor: '#F0F9FF',
        }}
      />
    );
  }
  const showIconUrl = iconType === 'url' && data.icon && isValidImageUrl(data.icon);
  const emoji =
    iconType === 'emoji' && data.icon
      ? data.icon
      : iconType === 'default'
      ? '📋'
      : data.icon || '📋';
  return (
    <div
      data-testid="fcv2-preview-icon-slot"
      style={{
        width: 56,
        height: 56,
        margin: '20px 20px 0',
        borderRadius: 14,
        background: COLORS.iconBg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 30,
        color: COLORS.primaryDark,
      }}
    >
      {showIconUrl ? (
        <img
          src={data.icon as string}
          alt=""
          style={{ width: 36, height: 36, borderRadius: 10, objectFit: 'cover' }}
        />
      ) : (
        <span aria-hidden>{emoji}</span>
      )}
    </div>
  );
}

export default function FunctionCardV2Preview({ data }: { data: FunctionCardV2PreviewData }) {
  return (
    <div
      data-testid="function-card-v2-preview"
      style={{
        background: COLORS.bg,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 16,
        boxShadow: COLORS.shadow,
        overflow: 'hidden',
        width: '100%',
        maxWidth: 340,
      }}
    >
      <HeaderMedia data={data} />
      <div style={{ padding: '14px 20px 4px' }}>
        <div style={{ fontSize: 18, lineHeight: '26px', fontWeight: 600, color: COLORS.titlePrimary }}>
          {data.title || '功能引导'}
        </div>
        {data.subtitle ? (
          <div style={{ fontSize: 13, lineHeight: '20px', color: COLORS.titleSecondary, marginTop: 6 }}>
            {data.subtitle}
          </div>
        ) : null}
      </div>
      <div style={{ padding: '14px 20px 18px' }}>
        {data.buttonSubDesc ? (
          <div
            data-testid="fcv2-preview-btn-sub-desc"
            style={{ fontSize: 12, lineHeight: '18px', color: COLORS.btnSubDesc, textAlign: 'center', marginBottom: 8 }}
          >
            {data.buttonSubDesc}
          </div>
        ) : null}
        <button
          type="button"
          data-testid="fcv2-preview-primary-btn"
          style={{
            display: 'block',
            width: '100%',
            height: 44,
            border: 'none',
            borderRadius: 22,
            color: '#FFFFFF',
            fontSize: 16,
            fontWeight: 600,
            cursor: 'pointer',
            background: COLORS.btnGradient,
            boxShadow: COLORS.btnShadow,
            letterSpacing: 1,
          }}
        >
          {data.buttonText || '立即查看'}
        </button>
      </div>
    </div>
  );
}

/**
 * 375x667 手机外框（带状态栏装饰），在 Modal 中提供"近似真机"的视觉容器。
 */
export function PhonePreviewFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      data-testid="phone-preview-frame"
      style={{
        width: 375,
        height: 667,
        margin: '0 auto',
        background: '#F0F9FF',
        borderRadius: 36,
        border: '8px solid #1E293B',
        boxShadow: '0 8px 32px rgba(15, 23, 42, 0.25)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* 状态栏装饰 */}
      <div
        style={{
          height: 24,
          background: '#0F172A',
          color: '#fff',
          fontSize: 11,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          letterSpacing: 0.5,
        }}
      >
        <span>9:41</span>
        <span>● ● ●</span>
      </div>
      {/* 内容区：模拟 H5 ai-home 页面背景 */}
      <div
        data-testid="phone-preview-body"
        style={{
          height: 667 - 24 - 16,
          padding: '20px 16px',
          overflowY: 'auto',
          background: '#F0F9FF',
        }}
      >
        {/* 模拟 AI 头像 */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
              fontWeight: 600,
              marginRight: 8,
            }}
          >
            康
          </div>
          <span style={{ fontSize: 13, color: '#666' }}>小康</span>
        </div>
        {children}
      </div>
    </div>
  );
}
