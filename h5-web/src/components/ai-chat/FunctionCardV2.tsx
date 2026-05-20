/**
 * [PRD-AICHAT-FUNCCARD-V2 2026-05-20]
 * [PRD-AICHAT-FUNCCARD-V2-DESIGN-D 2026-05-20 v1.2]
 *
 * AI 对话页「功能引导卡片」新版统一渲染组件 V2（方案 D · 图标左 + 标题右 · 宾尼天蓝）。
 *
 * v1.2 设计稿基准（参考稿 3c87314dcaf9435793c8021dd643baa4.html · 严格按像素还原）：
 *   ┌─────────────────────────────────────┐
 *   │ ████████████████████████████████████│  ← 顶部 4px 渐变色条 #0EA5E9→#38BDF8
 *   │                                      │
 *   │  [📋]  健康自查问卷                  │  ← 头部：图标 48×48 左 + 标题 20px/700 右
 *   │   ↑    ↑                             │     横向 flex / align-items:center / gap 14px
 *   │  48px 20px/700                       │
 *   │                                      │
 *   │  ┃ 通过专业问卷快速评估您的健康       │  ← 副标题色块：bg #F0F9FF + 左 3px #0EA5E9 竖线
 *   │  ┃ 状况……                            │     圆角 0 8px 8px 0
 *   │                                      │
 *   │     预计耗时 3-5 分钟 · 数据加密保护  │  ← 按钮副说明 12px #64748B 居中
 *   │                                      │
 *   │  ┌────────────────────────────┐     │
 *   │  │           开始              │     │  ← 主按钮 全宽 48 高 / 12 圆角 / #0EA5E9
 *   │  └────────────────────────────┘     │     字间距 1px / 文案固定「开始」
 *   └─────────────────────────────────────┘
 *
 * 视觉规范（v1.2 方案 D · 唯一基准）：
 *   - 卡片容器：白底 / 16 圆角 / shadow(0 4px 24px rgba(15,23,42,0.08)) / overflow:hidden
 *   - 顶部色条：高 4px / linear-gradient(90deg,#0EA5E9 0%,#38BDF8 100%)（全卡片必须存在）
 *   - 卡片内边距：24px 22px 22px
 *   - 头部：display:flex; align-items:center; gap:14px; margin-bottom:14px
 *   - 图标容器：48×48 / flex-shrink:0 / emoji 字号 28 / 无圆形背景框（纯图标）
 *   - 主标题：20px / weight 700 / #0F172A / 单行省略号 / flex:1 / min-width:0
 *   - 副标题色块：#F0F9FF + border-left:3px solid #0EA5E9 + padding:12px 14px
 *                + border-radius:0 8px 8px 0 / 字 14px / 行高 1.6 / #334155 / mb 18px
 *   - 按钮副说明：12px / #64748B / center / mb 10px
 *   - 主按钮：100% w / 48 h / border-none / radius 12 / bg #0EA5E9 / #fff 16/600 / letter-spacing 1px
 *   - 按钮文案：固定硬编码「开始」（v1.2 决策 12：忽略后端 button_text 字段）
 *
 * 兼容性说明：
 *   - 本期取消封面图模式（v1.2 决策 13）：cover_img 有值也按图标头部渲染
 *   - button_text / coverImage 字段保留供旧逻辑兼容，前端忽略
 *
 * 用法：被 ChatCards / QuestionnairePreCard 等卡片统一调用。
 */
'use client';

import React from 'react';

export interface FunctionCardV2Data {
  /** 主标题（必填） */
  title: string;
  /** 副标题（可选，方案 D 中以色块形式展示） */
  subtitle?: string | null;
  /** 封面图 URL（方案 D 本期忽略，仅保留兼容） */
  coverImage?: string | null;
  /** 图标：URL 或 Emoji */
  icon?: string | null;
  /** 图标类型：url / emoji / default */
  iconType?: 'url' | 'emoji' | 'default' | string | null;
  /** 按钮副说明文字（小字，居中在按钮上方） */
  buttonSubDesc?: string | null;
  /** 按钮主文案（方案 D 本期忽略，固定显示「开始」） */
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

/**
 * 方案 D 视觉令牌（v1.2 严格按参考稿）。
 *
 * 历史 v1.0 / v1.1 的部分 token（如 #E0F2FE、btnGradient #38BDF8→#0284C7、高 44 / 22 圆角）
 * 在源码中保留为常量参考，确保旧测试用例与历史文档可继续追溯，但实际渲染走方案 D。
 */
const COLORS = {
  // 方案 D 渲染用 token（v1.2 唯一基准）
  bg: '#FFFFFF',
  topBarFrom: '#0EA5E9',
  topBarTo: '#38BDF8',
  cardShadow: '0 4px 24px rgba(15, 23, 42, 0.08)',
  titlePrimary: '#0F172A',          // 20/700
  subBlockBg: '#F0F9FF',
  subBlockBorder: '#0EA5E9',        // 左竖线 3px
  subBlockText: '#334155',          // 14 / 1.6
  btnSubDesc: '#64748B',            // 12 / center
  btnSolid: '#0EA5E9',
  btnSolidHover: '#0284C7',
  btnShadowActive: '0 4px 14px rgba(14, 165, 233, 0.35)',

  // 兼容历史 v1.0 / v1.1 token（保留为追溯参考；不实际用于方案 D 渲染）
  border: '#E0F2FE',
  shadow: '0 2px 12px rgba(2, 132, 199, 0.10)',
  titleSecondary: '#64748B',
  subDescLegacy: '#94A3B8',
  primary: '#0EA5E9',
  primaryDark: '#0284C7',
  iconBg: 'linear-gradient(135deg, #ECFEFF 0%, #CFFAFE 100%)',
  btnGradient: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
  btnShadow: '0 4px 12px rgba(2, 132, 199, 0.25)',
  // 历史 v1 按钮尺寸（保留 token，方案 D 实际使用 48 / 12）
  legacyBtnHeight: 44,
  legacyBtnRadius: 22,
  legacyTitleSize: 18,
  legacySubtitleSize: 13,

  // 禁用态
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

/**
 * 方案 D 头部：左 48×48 图标 + 右 20/700 标题。
 *   - 图标：emoji（28px 字号居中）/ URL（48×48 contain）/ 默认 📋
 *   - 标题：单行省略号；flex:1; min-width:0 防止挤压
 *   - v1.2 决策 13：封面图模式取消，coverImage 有值也走图标头部
 */
function HeaderRow({ data }: { data: FunctionCardV2Data }) {
  const [imgError, setImgError] = React.useState(false);
  const iconType = data.iconType || 'default';
  const showIconUrl =
    iconType === 'url' && data.icon && isValidImageUrl(data.icon) && !imgError;
  const emoji =
    iconType === 'emoji' && data.icon
      ? data.icon
      : iconType === 'default'
      ? '📋'
      : data.icon || '📋';

  return (
    <div
      data-testid="fcv2-header-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        marginBottom: 14,
      }}
    >
      <div
        data-testid="fcv2-icon-slot"
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
            onError={() => setImgError(true)}
          />
        ) : (
          <span aria-hidden>{emoji}</span>
        )}
      </div>
      <div
        data-testid="fcv2-title"
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
    const target = e.target as HTMLElement;
    if (target.closest('[data-fcv2-stop="1"]')) return;
    if (target.tagName === 'BUTTON' || target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
    onClick?.();
  };

  // 方案 D 副标题缺失时整个色块隐藏，按钮区上推；按钮副说明缺失时该行不渲染
  const hasSubtitle = !!(data.subtitle && String(data.subtitle).trim());
  const hasBtnSubDesc = !!(data.buttonSubDesc && String(data.buttonSubDesc).trim());

  return (
    <div
      data-testid={testid || 'function-card-v2'}
      data-design-version="d-v1.2"
      data-disabled={disabled ? 'true' : 'false'}
      onClick={handleCardClick}
      style={{
        background: disabled ? COLORS.disabledBg : COLORS.bg,
        // v1.2 方案 D：圆角 16 / 蓝灰阴影 / 顶部色条用伪元素实现（这里直接用渐变 border-top）
        border: disabled ? `1px solid ${COLORS.disabledBorder}` : 'none',
        borderRadius: 16,
        boxShadow: disabled ? 'none' : COLORS.cardShadow,
        overflow: 'hidden',
        width: '100%',
        maxWidth: 340,
        margin: '4px 0',
        opacity: disabled ? 0.6 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'box-shadow .2s, transform .2s',
        position: 'relative',
      }}
    >
      {/* 顶部 4px 渐变色条（方案 D 全卡片必须存在的品牌锚点） */}
      <div
        data-testid="fcv2-top-bar"
        aria-hidden
        style={{
          height: 4,
          width: '100%',
          background: `linear-gradient(90deg, ${COLORS.topBarFrom} 0%, ${COLORS.topBarTo} 100%)`,
        }}
      />

      {/* 卡片正文：方案 D padding 24 22 22 */}
      <div style={{ padding: '24px 22px 22px' }}>
        <HeaderRow data={data} />

        {hasSubtitle ? (
          <div
            data-testid="fcv2-subtitle-block"
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

        {children ? <div style={{ marginBottom: 14 }}>{children}</div> : null}

        {!hideButton ? (
          <>
            {hasBtnSubDesc ? (
              <div
                data-testid="fcv2-btn-sub-desc"
                style={{
                  textAlign: 'center',
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: COLORS.btnSubDesc,
                  marginBottom: 10,
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
                height: 48,
                border: 'none',
                borderRadius: 12,
                color: '#FFFFFF',
                fontSize: 16,
                fontWeight: 600,
                cursor: disabled ? 'not-allowed' : 'pointer',
                background: disabled ? COLORS.disabledBtn : COLORS.btnSolid,
                boxShadow: disabled ? 'none' : COLORS.btnShadowActive,
                letterSpacing: 1,
              }}
            >
              {/* v1.2 决策 12：主按钮文案固定「开始」，前端忽略 button_text 字段 */}
              开始
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}

export const FUNCTION_CARD_V2_TOKENS = COLORS;
