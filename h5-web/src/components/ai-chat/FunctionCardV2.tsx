/**
 * [PRD-AICHAT-FUNCCARD-V2 2026-05-20]
 *
 * AI 对话页「功能引导卡片」新版统一渲染组件 V2。
 *
 * 设计稿基准（卡片自上而下）：
 *   ┌─────────────────────────────────┐
 *   │  [图标/封面图]                   │
 *   │                                  │
 *   │  主标题（大号、加粗）             │
 *   │  副标题（次级灰字）               │
 *   │                                  │
 *   │  按钮副说明文字（灰色小字）       │
 *   │  ┌─────────────────────────┐    │
 *   │  │     按钮文案（高亮）       │    │
 *   │  └─────────────────────────┘    │
 *   └─────────────────────────────────┘
 *
 * 视觉规范（来自 UI 标注稿 v1）：
 *   - 卡片容器：白底 + 1px #E0F2FE 描边 + 16px 圆角 + shadow(2,8,rgba(2,132,199,.10))
 *   - 主色系：#0EA5E9 / #0284C7（与 AI 首页输入区蓝色锚点同源）
 *   - 主标题：18px / 26px / weight 600 / #0F172A
 *   - 副标题：13px / 20px / weight 400 / #64748B
 *   - 按钮副说明：12px / 18px / #94A3B8 / 居中
 *   - 按钮：高 44 / 圆角 22 / 渐变 #38BDF8 → #0284C7 / 白字 16px 600
 *   - 圆角图标位：56×56 / 圆角 14 / 浅蓝渐变底
 *
 * 用法：被 ChatCards / QuestionnairePreCard 等卡片统一调用，作为对话流内嵌
 *       "功能引导卡片"的唯一视觉源头。
 */
'use client';

import React from 'react';

export interface FunctionCardV2Data {
  /** 主标题（必填） */
  title: string;
  /** 副标题（可选，次级灰字） */
  subtitle?: string | null;
  /** 封面图 URL（优先级最高） */
  coverImage?: string | null;
  /** 图标：URL 或 Emoji */
  icon?: string | null;
  /** 图标类型：url / emoji / default */
  iconType?: 'url' | 'emoji' | 'default' | string | null;
  /** 按钮副说明文字（灰色小字，位于按钮上方） */
  buttonSubDesc?: string | null;
  /** 按钮主文案（默认"立即查看"） */
  buttonText?: string;
  /** 是否禁用（重复点击折叠后置灰） */
  disabled?: boolean;
}

export interface FunctionCardV2Props {
  data: FunctionCardV2Data;
  onClick?: () => void;
  /** 当 children 非空时，渲染在按钮上方（用于 upload 卡的相册/拍照子项） */
  children?: React.ReactNode;
  /** 当为 true 时不渲染主按钮（用于完全自定义底部，如 quick_ask） */
  hideButton?: boolean;
  /** 透传 data-testid 便于测试用例定位 */
  testid?: string;
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
  disabledBg: '#F1F5F9',
  disabledBorder: '#E2E8F0',
  disabledBtn: '#CBD5E1',
};

function isValidImageUrl(s: any): boolean {
  if (typeof s !== 'string') return false;
  const t = s.trim();
  if (!t) return false;
  if (t.startsWith('http://') || t.startsWith('https://')) return true;
  if (t.startsWith('/') || t.startsWith('./') || t.startsWith('data:image/') || t.startsWith('blob:')) return true;
  return false;
}

function HeaderMedia({ data }: { data: FunctionCardV2Data }) {
  const [imgError, setImgError] = React.useState(false);
  const iconType = data.iconType || 'default';

  if (data.coverImage && isValidImageUrl(data.coverImage) && !imgError) {
    return (
      <div
        data-testid="fcv2-cover-image"
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
      >
        <img
          src={data.coverImage as string}
          alt=""
          style={{ display: 'none' }}
          onError={() => setImgError(true)}
        />
      </div>
    );
  }

  // 图标位（URL 图标或 Emoji 或默认 SVG）
  const showIconUrl = iconType === 'url' && data.icon && isValidImageUrl(data.icon);
  const emoji =
    iconType === 'emoji' && data.icon
      ? data.icon
      : iconType === 'default'
      ? '📋'
      : data.icon || '📋';

  return (
    <div
      data-testid="fcv2-icon-slot"
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
        lineHeight: 1,
        color: COLORS.primaryDark,
      }}
    >
      {showIconUrl ? (
        <img
          src={data.icon as string}
          alt=""
          style={{ width: 36, height: 36, borderRadius: 10, objectFit: 'cover' }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      ) : (
        <span aria-hidden>{emoji}</span>
      )}
    </div>
  );
}

export default function FunctionCardV2({
  data,
  onClick,
  children,
  hideButton,
  testid,
}: FunctionCardV2Props) {
  const disabled = !!data.disabled;
  const handleCardClick = (e: React.MouseEvent) => {
    if (disabled) return;
    // 点击落在按钮上时由按钮自身的 onClick 处理（避免双发）
    const target = e.target as HTMLElement;
    if (target.closest('[data-fcv2-stop="1"]')) return;
    if (target.tagName === 'BUTTON' || target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
    onClick?.();
  };

  return (
    <div
      data-testid={testid || 'function-card-v2'}
      data-disabled={disabled ? 'true' : 'false'}
      onClick={handleCardClick}
      style={{
        background: disabled ? COLORS.disabledBg : COLORS.bg,
        border: `1px solid ${disabled ? COLORS.disabledBorder : COLORS.border}`,
        borderRadius: 16,
        boxShadow: disabled ? 'none' : COLORS.shadow,
        overflow: 'hidden',
        width: '100%',
        maxWidth: 340,
        margin: '4px 0',
        opacity: disabled ? 0.6 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'box-shadow .2s, transform .2s',
      }}
    >
      <HeaderMedia data={data} />

      <div style={{ padding: '14px 20px 4px' }}>
        <div
          data-testid="fcv2-title"
          style={{
            fontSize: 18,
            lineHeight: '26px',
            fontWeight: 600,
            color: COLORS.titlePrimary,
            letterSpacing: 0.2,
          }}
        >
          {data.title || '功能引导'}
        </div>
        {data.subtitle ? (
          <div
            data-testid="fcv2-subtitle"
            style={{
              fontSize: 13,
              lineHeight: '20px',
              fontWeight: 400,
              color: COLORS.titleSecondary,
              marginTop: 6,
            }}
          >
            {data.subtitle}
          </div>
        ) : null}
      </div>

      {children ? <div style={{ padding: '12px 20px 0' }}>{children}</div> : null}

      {!hideButton ? (
        <div style={{ padding: '14px 20px 18px' }}>
          {data.buttonSubDesc ? (
            <div
              data-testid="fcv2-btn-sub-desc"
              style={{
                fontSize: 12,
                lineHeight: '18px',
                color: COLORS.btnSubDesc,
                textAlign: 'center',
                marginBottom: 8,
              }}
            >
              {data.buttonSubDesc}
            </div>
          ) : null}
          <button
            data-testid="fcv2-primary-btn"
            data-fcv2-stop="1"
            type="button"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              if (!disabled) onClick?.();
            }}
            style={{
              display: 'block',
              width: '100%',
              height: 44,
              border: 'none',
              borderRadius: 22,
              color: '#FFFFFF',
              fontSize: 16,
              fontWeight: 600,
              cursor: disabled ? 'not-allowed' : 'pointer',
              background: disabled ? COLORS.disabledBtn : COLORS.btnGradient,
              boxShadow: disabled ? 'none' : COLORS.btnShadow,
              letterSpacing: 1,
            }}
          >
            {data.buttonText || '立即查看'}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export const FUNCTION_CARD_V2_TOKENS = COLORS;
