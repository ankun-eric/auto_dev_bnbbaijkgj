'use client';

import React from 'react';

/**
 * 卡面渲染器（H5 端，与 admin 端 CardFacePreview 行为一致）。
 * 4 风格 + 8 色板 + 4 显示位 + ON_CARD 信息布局。
 * 色卡到位后修改 BG_HEX 一处常量即可。
 */

const BG_HEX: Record<string, string> = {
  BG1: '#F4E5C2',
  BG2: '#F5A623',
  BG3: '#E64A4A',
  BG4: '#1F3A5F',
  BG5: '#7EC8E3',
  BG6: '#3DBE6E',
  BG7: '#2A2A2A',
  BG8: '#F4C2C2',
};

export const DEFAULT_FACE_SHOW_FLAGS = 7;

export function isShowFlagOn(flags: number, bit: number): boolean {
  return (Number(flags || 0) & bit) === bit;
}

export interface CardFaceProps {
  faceStyle?: string;
  faceBgCode?: string;
  faceShowFlags?: number;
  cardName?: string;
  itemsSummary?: string;
  price?: number | string | null;
  originalPrice?: number | string | null;
  validDays?: number | null;
  size?: 'sm' | 'md' | 'lg';
  cardType?: 'times' | 'period' | string;
  totalTimes?: number | null;
  scopeType?: 'platform' | 'merchant' | string;
  remainingTimes?: number | null;
  daysToExpire?: number | null;
}

const SIZE_MAP = {
  sm: { h: 110, padding: 12, name: 16, hint: 11, price: 18, radius: 14 },
  md: { h: 170, padding: 16, name: 22, hint: 13, price: 26, radius: 16 },
  lg: { h: 200, padding: 18, name: 24, hint: 13, price: 30, radius: 18 },
} as const;

function getStyleBackground(style: string, bgCode: string): string {
  const base = BG_HEX[bgCode] || BG_HEX.BG1;
  switch (style) {
    case 'ST1':
      return `linear-gradient(135deg, ${base} 0%, ${base} 100%)`;
    case 'ST2':
      return `linear-gradient(135deg, ${base} 0%, rgba(0,0,0,0.35) 100%)`;
    case 'ST3':
      return `linear-gradient(135deg, ${base} 0%, #C9A76A 100%)`;
    case 'ST4':
      return `linear-gradient(135deg, ${base} 0%, #C9A76A 50%, #E0C892 100%)`;
    default:
      return base;
  }
}

function getTextColor(style: string, bgCode: string): string {
  if (style === 'ST2' || style === 'ST4') return '#fff';
  if (bgCode === 'BG3' || bgCode === 'BG4' || bgCode === 'BG7') return '#fff';
  if (style === 'ST3') return '#fff';
  return '#1a1a1a';
}

function getSubColor(textColor: string): string {
  return textColor === '#fff' ? 'rgba(255,255,255,0.78)' : 'rgba(0,0,0,0.55)';
}

const CardFace: React.FC<CardFaceProps> = ({
  faceStyle = 'ST1',
  faceBgCode = 'BG1',
  faceShowFlags = DEFAULT_FACE_SHOW_FLAGS,
  cardName,
  itemsSummary,
  price,
  originalPrice,
  validDays,
  size = 'md',
  cardType,
  totalTimes,
  scopeType,
  remainingTimes,
  daysToExpire,
}) => {
  const sm = SIZE_MAP[size];
  const bg = getStyleBackground(faceStyle, faceBgCode);
  const textColor = getTextColor(faceStyle, faceBgCode);
  const subColor = getSubColor(textColor);

  const showName = isShowFlagOn(faceShowFlags, 1);
  const showItems = isShowFlagOn(faceShowFlags, 2);
  const showPrice = isShowFlagOn(faceShowFlags, 4);
  const showValid = isShowFlagOn(faceShowFlags, 8);

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
            'linear-gradient(0deg, rgba(212,175,55,0.4) 0%, rgba(212,175,55,0.4) 1px, transparent 1px)',
          backgroundSize: '100% 24px',
        }
      : {};

  return (
    <div
      style={{
        background: bg,
        height: sm.h,
        borderRadius: sm.radius,
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
        style={{ position: 'absolute', inset: 0, ...decoration, pointerEvents: 'none' }}
      />
      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 999,
              background: textColor === '#fff' ? 'rgba(255,255,255,0.20)' : 'rgba(0,0,0,0.08)',
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
              {cardType === 'times' && (remainingTimes !== undefined && remainingTimes !== null) ? (
                <span style={{ fontSize: sm.hint, color: subColor }}>
                  · 剩 {remainingTimes}/{totalTimes ?? '?'} 次
                </span>
              ) : cardType === 'times' && totalTimes ? (
                <span style={{ fontSize: sm.hint, color: subColor }}>
                  · {totalTimes} 次
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        {showValid ? (
          <div style={{ fontSize: sm.hint, color: subColor }}>
            {daysToExpire !== undefined && daysToExpire !== null
              ? `剩 ${daysToExpire} 天到期`
              : validDays
              ? `有效 ${validDays} 天`
              : ''}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default CardFace;
