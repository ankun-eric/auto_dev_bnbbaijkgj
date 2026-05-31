'use client';

/**
 * [PRD-MEMBER-CENTER-OPTIM-V1 2026-05-31] 本月配额三独立卡片改造
 *
 * 改造前：1 个大卡片，3 项配额堆叠
 * 改造后：横向一行 3 个独立卡片，宽度均分
 *   - 卡片 1 📞 AI 外呼     X/Y 次 + 进度条 + 说明
 *   - 卡片 2 🚨 紧急呼叫   X/Y 次 + 进度条 + 说明
 *   - 卡片 3 👥 家庭成员   X/Y 人 + 进度条 + 说明（含本人）
 *
 * 状态规范：
 *   - 正常：进度条主题色（紫）
 *   - 不限档（total = -1 或 >=9999）：中部显示「不限」，不显示进度条
 *   - 已用完（used >= total）：进度条变红 + 「已用完」红色标签
 *
 * 命名变更：原"守护他人"→"家庭成员"（PRD R3 全局命名统一）
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

const RED_DANGER = '#EF4444';

function isUnlimited(total: number | null): boolean {
  return total === -1 || (typeof total === 'number' && total >= 9999);
}

function isExhausted(p: QuotaPair): boolean {
  if (isUnlimited(p.total)) return false;
  if (p.used === null || p.total === null) return false;
  return p.used >= p.total && p.total > 0;
}

interface CardSpec {
  key: string;
  icon: string;
  title: string;
  unit: string; // 次 / 人
  pair: QuotaPair;
  desc: (used: number | null, total: number | null) => string;
}

const QuotaSingleCard: React.FC<{
  purple: boolean;
  spec: CardSpec;
}> = ({ purple, spec }) => {
  const unlim = isUnlimited(spec.pair.total);
  const exhausted = isExhausted(spec.pair);
  const percent = calcQuotaPercent(spec.pair.used, spec.pair.total);

  // 卡片背景：付费态深色卡用半透明白底以承接外层蓝紫；未付费用白底
  const cardBg = purple ? 'rgba(255,255,255,0.14)' : '#FFFFFF';
  const cardBorder = purple ? '1px solid rgba(255,255,255,0.22)' : `1px solid ${PURPLE_THEME.BORDER_LIGHT}`;
  const titleColor = purple ? 'rgba(255,255,255,0.92)' : PURPLE_THEME.TEXT_MUTED;
  const numberColor = purple ? '#FFFFFF' : PURPLE_THEME.PRIMARY;
  const descColor = purple ? 'rgba(255,255,255,0.72)' : PURPLE_THEME.TEXT_MUTED;
  const trackColor = purple ? 'rgba(255,255,255,0.24)' : PURPLE_THEME.UNPAID_BG;
  const fillColorNormal = purple ? '#FFFFFF' : PURPLE_THEME.PRIMARY;

  return (
    <div
      data-testid={`mc-quota-item-${spec.key}`}
      data-state={unlim ? 'unlimited' : exhausted ? 'exhausted' : 'normal'}
      style={{
        flex: 1,
        minWidth: 0,
        background: cardBg,
        border: cardBorder,
        borderRadius: 14,
        padding: '12px 10px',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 顶部：图标 + 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6 }}>
        <span style={{ fontSize: 14 }} aria-hidden>{spec.icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: titleColor, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {spec.title}
        </span>
      </div>

      {/* 中部：大数字 X/Y 单位（或「不限」） */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 4,
          flexWrap: 'wrap',
        }}
      >
        {unlim ? (
          <span
            data-testid={`mc-quota-value-${spec.key}`}
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: numberColor,
              lineHeight: 1.2,
            }}
          >
            不限
          </span>
        ) : (
          <>
            <span
              data-testid={`mc-quota-value-${spec.key}`}
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: numberColor,
                lineHeight: 1.2,
              }}
            >
              {spec.pair.used ?? 0}/{spec.pair.total ?? 0}
            </span>
            <span style={{ fontSize: 11, color: descColor }}>{spec.unit}</span>
            {exhausted && (
              <span
                data-testid={`mc-quota-exhausted-${spec.key}`}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: RED_DANGER,
                  marginLeft: 2,
                }}
              >
                已用完
              </span>
            )}
          </>
        )}
      </div>

      {/* 下部：进度条（不限档不展示） */}
      {!unlim && percent !== null && (
        <div
          data-testid={`mc-quota-bar-track-${spec.key}`}
          style={{
            height: 5,
            background: trackColor,
            borderRadius: 999,
            overflow: 'hidden',
            marginTop: 8,
          }}
        >
          <div
            data-testid={`mc-quota-bar-fill-${spec.key}`}
            style={{
              width: `${percent}%`,
              height: '100%',
              background: exhausted ? RED_DANGER : fillColorNormal,
              borderRadius: 999,
              transition: 'width 200ms ease',
            }}
          />
        </div>
      )}

      {/* 底部：说明文案 */}
      <div
        data-testid={`mc-quota-desc-${spec.key}`}
        style={{
          fontSize: 11,
          color: descColor,
          marginTop: 6,
          lineHeight: 1.3,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {spec.desc(spec.pair.used, spec.pair.total)}
      </div>
    </div>
  );
};

export default function MonthlyQuotaCard({ themeState, aiOutbound, emergencyAi, manageMember }: Props) {
  const purple = isPurpleThemeEnabled(themeState);

  // 外层容器：付费态承接蓝紫渐变背景，未付费态使用页面浅灰底
  const wrapperStyle: React.CSSProperties = purple
    ? {
        margin: '12px 16px 0',
        background: PURPLE_THEME.PRIMARY,
        borderRadius: 16,
        padding: '14px 12px 12px',
        color: '#fff',
        boxShadow: '0 8px 24px rgba(91,108,255,0.25)',
      }
    : {
        margin: '12px 16px 0',
      };

  const titleStyle: React.CSSProperties = purple
    ? {
        fontSize: 14,
        fontWeight: 700,
        color: '#fff',
        marginBottom: 10,
        padding: '0 2px',
      }
    : {
        fontSize: 14,
        fontWeight: 700,
        color: PURPLE_THEME.TEXT_DARK,
        marginBottom: 10,
        padding: '0 6px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      };

  const cards: CardSpec[] = [
    {
      key: 'ai_outbound',
      icon: '📞',
      title: 'AI 外呼',
      unit: '次',
      pair: aiOutbound,
      desc: (used, total) => {
        if (isUnlimited(total)) return '不限次数';
        return `本月已用 ${used ?? 0} 次`;
      },
    },
    {
      key: 'emergency_ai',
      icon: '🚨',
      title: '紧急呼叫',
      unit: '次',
      pair: emergencyAi,
      desc: (used, total) => {
        if (isUnlimited(total)) return '不限次数';
        return `本月已用 ${used ?? 0} 次`;
      },
    },
    {
      key: 'manage_member',
      icon: '👥',
      title: '家庭成员',
      unit: '人',
      pair: manageMember,
      desc: (used, total) => {
        // [PRD-MEMBER-COUNT-CONSISTENCY-V1 2026-05-31] 文案改为"已管理 X 人"
        // 与蓝卡片「已管理 X / 上限 Y」口径与措辞统一（含本人）。
        if (isUnlimited(total)) return '不限人数';
        return `已管理 ${used ?? 0} 人`;
      },
    },
  ];

  return (
    <div data-testid="mc-monthly-quota" data-theme={purple ? 'purple' : 'unpaid'} style={wrapperStyle}>
      <div style={titleStyle}>
        {!purple && (
          <span
            aria-hidden
            style={{
              display: 'inline-block',
              width: 4,
              height: 14,
              background: PURPLE_THEME.PRIMARY,
              borderRadius: 2,
            }}
          />
        )}
        本月配额
      </div>
      <div
        data-testid="mc-quota-row"
        style={{
          display: 'flex',
          flexDirection: 'row',
          gap: 8,
          alignItems: 'stretch',
        }}
      >
        {cards.map((c) => (
          <QuotaSingleCard key={c.key} purple={purple} spec={c} />
        ))}
      </div>
    </div>
  );
}
