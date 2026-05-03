'use client';

import React from 'react';

/**
 * 卡面渲染器（admin 实时预览 + 列表预览统一使用）
 * - 4 风格：ST1 简约现代 / ST2 沉稳商务 / ST3 节日喜庆 / ST4 奢华尊享
 * - 8 色板：BG1~BG8（按 PRD v1.1 第 3.2 节临时 HEX）
 * - 4 显示位：SH1 卡名 / SH2 服务内容 / SH3 价格 / SH4 有效期
 *
 * 注意：色卡到位后只需修改本文件 BG_HEX 常量即可，无需改业务逻辑。
 */

export const FACE_STYLES = [
  { code: 'ST1', name: '简约现代', hint: '纯色卡面 + 细黑字，留白多，圆角大' },
  { code: 'ST2', name: '沉稳商务', hint: '深蓝/墨黑底 + 白字 + 细金线点缀' },
  { code: 'ST3', name: '节日喜庆', hint: '中国红/朱砂底 + 烫金/祥云纹' },
  { code: 'ST4', name: '奢华尊享', hint: '香槟金/玫瑰金渐变 + 金属质感' },
] as const;

export const BG_OPTIONS = [
  { code: 'BG1', name: '米黄', hex: '#F4E5C2' },
  { code: 'BG2', name: '暖橙', hex: '#F5A623' },
  { code: 'BG3', name: '朱红', hex: '#E64A4A' },
  { code: 'BG4', name: '深蓝', hex: '#1F3A5F' },
  { code: 'BG5', name: '天蓝', hex: '#7EC8E3' },
  { code: 'BG6', name: '鲜绿', hex: '#3DBE6E' },
  { code: 'BG7', name: '沉黑', hex: '#2A2A2A' },
  { code: 'BG8', name: '裸粉', hex: '#F4C2C2' },
] as const;

export const SHOW_FLAGS = [
  { bit: 1, code: 'SH1', name: '卡名' },
  { bit: 2, code: 'SH2', name: '服务内容' },
  { bit: 4, code: 'SH3', name: '价格' },
  { bit: 8, code: 'SH4', name: '有效期' },
] as const;

const BG_HEX: Record<string, string> = Object.fromEntries(
  BG_OPTIONS.map((b) => [b.code, b.hex]),
);

export const DEFAULT_FACE_SHOW_FLAGS = 7; // SH1+SH2+SH3

export function isShowFlagOn(flags: number, bit: number): boolean {
  return (Number(flags || 0) & bit) === bit;
}

export function toggleShowFlag(flags: number, bit: number, on: boolean): number {
  const v = Number(flags || 0);
  return on ? v | bit : v & ~bit;
}

export interface CardFaceProps {
  faceStyle: string; // ST1~ST4
  faceBgCode: string; // BG1~BG8
  faceShowFlags: number;
  cardName?: string;
  itemsSummary?: string; // 服务内容摘要
  price?: number | string | null;
  originalPrice?: number | string | null;
  validDays?: number | null;
  size?: 'sm' | 'md' | 'lg';
  cardType?: 'times' | 'period' | string;
  totalTimes?: number | null;
  scopeType?: 'platform' | 'merchant' | string;
}

const SIZE_MAP = {
  sm: { h: 110, padding: 12, name: 16, hint: 11, price: 18 },
  md: { h: 170, padding: 16, name: 22, hint: 13, price: 26 },
  lg: { h: 210, padding: 20, name: 26, hint: 14, price: 32 },
} as const;

function getStyleBackground(style: string, bgCode: string): string {
  const base = BG_HEX[bgCode] || BG_HEX.BG1;
  switch (style) {
    case 'ST1':
      // 简约现代：纯色 + 极淡渐层
      return `linear-gradient(135deg, ${base} 0%, ${base} 100%)`;
    case 'ST2':
      // 沉稳商务：底色加深
      return `linear-gradient(135deg, ${base} 0%, rgba(0,0,0,0.35) 100%)`;
    case 'ST3':
      // 节日喜庆：底色 + 金色渐层
      return `linear-gradient(135deg, ${base} 0%, #C9A76A 100%)`;
    case 'ST4':
      // 奢华尊享：底色 + 香槟金
      return `linear-gradient(135deg, ${base} 0%, #C9A76A 50%, #E0C892 100%)`;
    default:
      return base;
  }
}

function getTextColor(style: string, bgCode: string): string {
  // 深色底（BG3/BG4/BG7）或商务/奢华，统一白色字
  if (style === 'ST2' || style === 'ST4') return '#fff';
  if (bgCode === 'BG3' || bgCode === 'BG4' || bgCode === 'BG7') return '#fff';
  if (style === 'ST3') return '#fff';
  return '#1a1a1a';
}

function getSubTextColor(textColor: string): string {
  return textColor === '#fff' ? 'rgba(255,255,255,0.78)' : 'rgba(0,0,0,0.55)';
}

export const CardFace: React.FC<CardFaceProps> = ({
  faceStyle,
  faceBgCode,
  faceShowFlags,
  cardName,
  itemsSummary,
  price,
  originalPrice,
  validDays,
  size = 'md',
  cardType,
  totalTimes,
  scopeType,
}) => {
  const sm = SIZE_MAP[size];
  const bg = getStyleBackground(faceStyle, faceBgCode);
  const textColor = getTextColor(faceStyle, faceBgCode);
  const subColor = getSubTextColor(textColor);

  const showName = isShowFlagOn(faceShowFlags, 1);
  const showItems = isShowFlagOn(faceShowFlags, 2);
  const showPrice = isShowFlagOn(faceShowFlags, 4);
  const showValid = isShowFlagOn(faceShowFlags, 8);

  // ST3/ST4 视觉点缀
  const decoration =
    faceStyle === 'ST3'
      ? {
          backgroundImage:
            'radial-gradient(circle at 90% 10%, rgba(255,215,0,0.35) 0%, transparent 40%), radial-gradient(circle at 10% 90%, rgba(255,215,0,0.25) 0%, transparent 35%)',
        }
      : faceStyle === 'ST4'
      ? {
          backgroundImage:
            'linear-gradient(120deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0) 30%, rgba(255,255,255,0) 70%, rgba(255,255,255,0.18) 100%)',
        }
      : faceStyle === 'ST2'
      ? {
          backgroundImage:
            'linear-gradient(90deg, transparent 0%, transparent calc(100% - 1px), rgba(212,175,55,0.5) 100%), linear-gradient(0deg, rgba(212,175,55,0.4) 0%, rgba(212,175,55,0.4) 1px, transparent 1px)',
          backgroundSize: '100% 100%, 100% 24px',
        }
      : {};

  return (
    <div
      style={{
        background: bg,
        height: sm.h,
        borderRadius: faceStyle === 'ST1' ? 18 : 14,
        padding: sm.padding,
        boxShadow: '0 4px 14px rgba(0,0,0,0.10)',
        color: textColor,
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          ...decoration,
          pointerEvents: 'none',
        }}
      />
      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 999,
              background: textColor === '#fff' ? 'rgba(255,255,255,0.20)' : 'rgba(0,0,0,0.08)',
              color: textColor,
            }}
          >
            {cardType === 'times' ? '次卡' : cardType === 'period' ? '时卡' : '卡'}
          </span>
          {scopeType === 'merchant' ? (
            <span
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 999,
                background: textColor === '#fff' ? 'rgba(255,255,255,0.20)' : 'rgba(0,0,0,0.08)',
              }}
            >
              商家专属
            </span>
          ) : null}
        </div>

        {showName && cardName ? (
          <div
            style={{
              fontSize: sm.name,
              fontWeight: 700,
              marginTop: 6,
              letterSpacing: faceStyle === 'ST2' || faceStyle === 'ST4' ? 1 : 0,
              textShadow: textColor === '#fff' ? '0 1px 2px rgba(0,0,0,0.15)' : 'none',
            }}
          >
            {cardName}
          </div>
        ) : null}
        {showItems && itemsSummary ? (
          <div
            style={{
              fontSize: sm.hint,
              color: subColor,
              marginTop: 4,
              maxWidth: '100%',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {itemsSummary}
          </div>
        ) : null}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 8,
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div style={{ minWidth: 0 }}>
          {showPrice && price !== undefined && price !== null ? (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: sm.price, fontWeight: 700 }}>
                ¥{Number(price).toFixed(0)}
              </span>
              {originalPrice ? (
                <span
                  style={{
                    fontSize: sm.hint,
                    color: subColor,
                    textDecoration: 'line-through',
                  }}
                >
                  ¥{Number(originalPrice).toFixed(0)}
                </span>
              ) : null}
              {cardType === 'times' && totalTimes ? (
                <span style={{ fontSize: sm.hint, color: subColor }}>
                  · {totalTimes} 次
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        {showValid && validDays ? (
          <div style={{ fontSize: sm.hint, color: subColor }}>
            有效 {validDays} 天
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default CardFace;
