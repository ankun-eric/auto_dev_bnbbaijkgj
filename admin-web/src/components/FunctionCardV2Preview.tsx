/**
 * [PRD-AICHAT-FUNCCARD-V2 2026-05-20]
 * [PRD-AICHAT-FUNCCARD-V2-DESIGN-D 2026-05-20 v1.2]
 *
 * 管理后台「卡片预览浮层」内使用的 FunctionCardV2 复刻渲染器（方案 D · v1.2）。
 *
 * 视觉规范 / token 与 h5-web 端 `FunctionCardV2.tsx` 严格一致，
 * 用于在 375x667 手机框内 1:1 还原 H5 真机效果。
 *
 * 注意：本组件**纯展示**，不绑定任何交互；点击主按钮无响应，仅展示效果。
 * 如要修改视觉细节，请同步修改 h5-web 端的源组件，保证全端像素级一致。
 */
'use client';

import React from 'react';

export interface FunctionCardV2PreviewData {
  title: string;
  subtitle?: string | null;
  /** 封面图（v1.2 方案 D 本期忽略，仅保留字段兼容） */
  coverImage?: string | null;
  icon?: string | null;
  iconType?: 'url' | 'emoji' | 'default' | string | null;
  buttonSubDesc?: string | null;
  /** 按钮主文案（v1.2 方案 D 本期忽略，固定显示「开始」） */
  buttonText?: string;
}

const COLORS = {
  bg: '#FFFFFF',
  topBarFrom: '#0EA5E9',
  topBarTo: '#38BDF8',
  cardShadow: '0 4px 24px rgba(15, 23, 42, 0.08)',
  titlePrimary: '#0F172A',
  subBlockBg: '#F0F9FF',
  subBlockBorder: '#0EA5E9',
  subBlockText: '#334155',
  btnSubDesc: '#64748B',
  btnSolid: '#0EA5E9',
  btnShadowActive: '0 4px 14px rgba(14, 165, 233, 0.35)',

  // 历史 v1 token 保留为追溯参考（不影响方案 D 渲染）
  border: '#E0F2FE',
  shadow: '0 2px 12px rgba(2, 132, 199, 0.10)',
  titleSecondary: '#64748B',
  subDescLegacy: '#94A3B8',
  primaryDark: '#0284C7',
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

function HeaderRow({ data }: { data: FunctionCardV2PreviewData }) {
  const iconType = data.iconType || 'default';
  const showIconUrl = iconType === 'url' && data.icon && isValidImageUrl(data.icon);
  const emoji =
    iconType === 'emoji' && data.icon
      ? data.icon
      : iconType === 'default'
      ? '📋'
      : data.icon || '📋';
  return (
    <div
      data-testid="fcv2-preview-header-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        marginBottom: 14,
      }}
    >
      <div
        data-testid="fcv2-preview-icon-slot"
        style={{
          width: 48,
          height: 48,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 28,
          lineHeight: 1,
        }}
      >
        {showIconUrl ? (
          <img
            src={data.icon as string}
            alt=""
            style={{ width: 48, height: 48, objectFit: 'contain' }}
          />
        ) : (
          <span aria-hidden>{emoji}</span>
        )}
      </div>
      <div
        data-testid="fcv2-preview-title"
        title={data.title || ''}
        style={{
          flex: 1,
          minWidth: 0,
          fontSize: 20,
          lineHeight: 1.3,
          fontWeight: 700,
          color: COLORS.titlePrimary,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {data.title || '功能引导'}
      </div>
    </div>
  );
}

export default function FunctionCardV2Preview({ data }: { data: FunctionCardV2PreviewData }) {
  const hasSubtitle = !!(data.subtitle && String(data.subtitle).trim());
  const hasBtnSubDesc = !!(data.buttonSubDesc && String(data.buttonSubDesc).trim());
  return (
    <div
      data-testid="function-card-v2-preview"
      data-design-version="d-v1.2"
      style={{
        background: COLORS.bg,
        border: 'none',
        borderRadius: 16,
        boxShadow: COLORS.cardShadow,
        overflow: 'hidden',
        width: '100%',
        maxWidth: 340,
      }}
    >
      {/* 顶部 4px 渐变色条 */}
      <div
        data-testid="fcv2-preview-top-bar"
        aria-hidden
        style={{
          height: 4,
          width: '100%',
          background: `linear-gradient(90deg, ${COLORS.topBarFrom} 0%, ${COLORS.topBarTo} 100%)`,
        }}
      />
      <div style={{ padding: '24px 22px 22px' }}>
        <HeaderRow data={data} />
        {hasSubtitle ? (
          <div
            data-testid="fcv2-preview-subtitle-block"
            style={{
              background: COLORS.subBlockBg,
              borderLeft: `3px solid ${COLORS.subBlockBorder}`,
              borderRadius: '0 8px 8px 0',
              padding: '12px 14px',
              fontSize: 14,
              lineHeight: 1.6,
              color: COLORS.subBlockText,
              marginBottom: 18,
            }}
          >
            {data.subtitle}
          </div>
        ) : null}
        {hasBtnSubDesc ? (
          <div
            data-testid="fcv2-preview-btn-sub-desc"
            style={{
              fontSize: 12,
              lineHeight: 1.5,
              color: COLORS.btnSubDesc,
              textAlign: 'center',
              marginBottom: 10,
            }}
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
            height: 48,
            border: 'none',
            borderRadius: 12,
            color: '#FFFFFF',
            fontSize: 16,
            fontWeight: 600,
            cursor: 'pointer',
            background: COLORS.btnSolid,
            boxShadow: COLORS.btnShadowActive,
            letterSpacing: 1,
          }}
        >
          {/* v1.2 决策 12：固定「开始」 */}
          开始
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
