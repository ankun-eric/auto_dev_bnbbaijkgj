'use client';

/**
 * [PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 本月配额卡（F3）
 *
 * 付费态：蓝紫底 + 高对比白字 + 进度条；
 * 未付费态：白底 + 灰描边 + 蓝紫前景进度条。
 *
 * Props 严格按 PRD §F3：
 * - aiOutbound: { used, total }
 * - emergencyAi: { used, total }
 * - manageMember: { used, total }
 * - 数值 -1 或 >=9999：显示「不限」，隐藏进度条
 */
import React from 'react';
import { PURPLE_THEME, calcQuotaPercent, isPurpleThemeEnabled, type ThemeState } from '../theme-purple';

interface QuotaPair {
  used: number | null;
  total: number | null;
}

interface Props {
  themeState: ThemeState;
  aiOutbound: QuotaPair;
  emergencyAi: QuotaPair;
  manageMember: QuotaPair;
}

function fmtNum(v: number | null): string {
  if (v === null || v === undefined) return '--';
  if (v === -1 || v >= 9999) return '不限';
  return String(v);
}

function rowText(p: QuotaPair): string {
  const totalIsUnlimited = p.total === -1 || (typeof p.total === 'number' && p.total >= 9999);
  if (totalIsUnlimited) return '不限';
  if (p.total === null) return '--';
  return `${fmtNum(p.used)} / ${fmtNum(p.total)}`;
}

const Bar: React.FC<{ percent: number | null; trackColor: string; fillColor: string }> = ({ percent, trackColor, fillColor }) => {
  if (percent === null) return null;
  return (
    <div
      data-testid="mc-quota-bar-track"
      style={{
        height: 6,
        background: trackColor,
        borderRadius: 999,
        overflow: 'hidden',
        marginTop: 6,
      }}
    >
      <div
        data-testid="mc-quota-bar-fill"
        style={{
          width: `${percent}%`,
          height: '100%',
          background: fillColor,
          borderRadius: 999,
          transition: 'width 200ms ease',
        }}
      />
    </div>
  );
};

export default function MonthlyQuotaCard({ themeState, aiOutbound, emergencyAi, manageMember }: Props) {
  const purple = isPurpleThemeEnabled(themeState);

  const containerStyle: React.CSSProperties = purple
    ? {
        margin: '12px 16px 0',
        background: PURPLE_THEME.PRIMARY,
        borderRadius: 16,
        padding: 16,
        color: '#fff',
        boxShadow: '0 8px 24px rgba(91,108,255,0.25)',
      }
    : {
        margin: '12px 16px 0',
        background: '#fff',
        borderRadius: 16,
        padding: 16,
        border: `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
      };

  const titleStyle: React.CSSProperties = {
    fontSize: 15,
    fontWeight: 700,
    color: purple ? '#fff' : PURPLE_THEME.TEXT_DARK,
    marginBottom: 12,
  };

  const items: Array<{ key: string; label: string; pair: QuotaPair }> = [
    { key: 'ai_outbound', label: 'AI 外呼提醒', pair: aiOutbound },
    { key: 'emergency_ai', label: '紧急 AI 呼叫', pair: emergencyAi },
    { key: 'manage_member', label: '守护他人上限', pair: manageMember },
  ];

  return (
    <div data-testid="mc-monthly-quota" data-theme={purple ? 'purple' : 'unpaid'} style={containerStyle}>
      <div style={titleStyle}>本月配额</div>
      {items.map((it, idx) => {
        const percent = calcQuotaPercent(it.pair.used, it.pair.total);
        return (
          <div
            key={it.key}
            data-testid={`mc-quota-item-${it.key}`}
            style={{
              padding: idx === 0 ? '0 0 12px' : '12px 0',
              borderTop: idx === 0 ? 'none' : purple ? '1px solid rgba(255,255,255,0.16)' : `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 13, color: purple ? 'rgba(255,255,255,0.92)' : PURPLE_THEME.TEXT_MUTED }}>
                {it.label}
              </span>
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: purple ? '#fff' : PURPLE_THEME.PRIMARY,
                }}
                data-testid={`mc-quota-value-${it.key}`}
              >
                {rowText(it.pair)}
              </span>
            </div>
            <Bar
              percent={percent}
              trackColor={purple ? 'rgba(255,255,255,0.24)' : PURPLE_THEME.UNPAID_BG}
              fillColor={purple ? '#FFFFFF' : PURPLE_THEME.PRIMARY}
            />
          </div>
        );
      })}
    </div>
  );
}
