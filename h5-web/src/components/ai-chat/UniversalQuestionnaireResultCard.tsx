'use client';

/**
 * [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用问卷结果卡片（AI 侧）
 *
 * 接受后端通用卡片协议 `questionnaire_result_card.card` payload，
 * 在 AI 对话流中呈现 6 屏沉浸式详情页的入口卡。
 *
 * 视觉风格统一为「报告卡片化稿 2」：白底圆角 + 顶部色块 + 主结论 + 9 维迷你雷达。
 */

import React from 'react';

export interface UniversalCardPayload {
  questionnaire_code?: string | null;
  questionnaire_name?: string | null;
  subject_name?: string | null;
  completed_at?: string | null;
  answer_id?: number;
  result_id?: number;
  template_id?: number;
  main_type?: string | null;
  main_type_desc?: string | null;
  secondary_types?: string[] | null;
  classification_name?: string | null;
  classification_code?: string | null;
  scores?: Record<string, number> | null;
  summary_text?: string | null;
  fields?: Array<{ key: string; label: string; value: string }>;
  icon?: string;
  detail_target?: {
    kind?: string;
    result_id?: number;
    route_h5?: string | null;
    mp_path?: string | null;
  };
  cover_style?: string;
  cover_color?: string;
}

interface Props {
  payload: UniversalCardPayload;
  onClickDetail?: (target: UniversalCardPayload['detail_target']) => void;
}

/** 9 项体质转换分迷你雷达（零依赖 SVG） */
function MiniRadar({ scores, color }: { scores: Record<string, number>; color: string }) {
  const labels = Object.keys(scores);
  if (labels.length === 0) return null;
  const size = 180;
  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.38;
  const max = 100;
  const angleStep = (Math.PI * 2) / labels.length;
  const points = labels
    .map((k, i) => {
      const v = Math.min(max, Math.max(0, Number(scores[k]) || 0));
      const r = (v / max) * radius;
      const a = -Math.PI / 2 + i * angleStep;
      return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
    })
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');
  // 背景同心三圈
  const rings = [0.33, 0.66, 1].map((p) => p * radius);
  // 轴线
  const axes = labels.map((_, i) => {
    const a = -Math.PI / 2 + i * angleStep;
    return [cx + Math.cos(a) * radius, cy + Math.sin(a) * radius];
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label="9 体质雷达图">
      {rings.map((r, idx) => (
        <circle key={idx} cx={cx} cy={cy} r={r} fill="none" stroke="#E5E7EB" strokeWidth={1} />
      ))}
      {axes.map(([x, y], idx) => (
        <line key={idx} x1={cx} y1={cy} x2={x} y2={y} stroke="#E5E7EB" strokeWidth={1} />
      ))}
      <polygon points={points} fill={color + '33'} stroke={color} strokeWidth={1.5} />
      {labels.map((lab, i) => {
        const a = -Math.PI / 2 + i * angleStep;
        const lx = cx + Math.cos(a) * (radius + 14);
        const ly = cy + Math.sin(a) * (radius + 14);
        return (
          <text
            key={lab}
            x={lx}
            y={ly}
            fontSize={9}
            fill="#666"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {lab}
          </text>
        );
      })}
    </svg>
  );
}

export default function UniversalQuestionnaireResultCard({ payload, onClickDetail }: Props) {
  const coverColor = payload.cover_color || '#0EA5E9';
  const mainType =
    payload.main_type || payload.classification_name || payload.questionnaire_name || '结果';
  const secondary = (payload.secondary_types || []).filter(Boolean);
  const completed = payload.completed_at
    ? new Date(payload.completed_at).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';
  const hasScores =
    payload.scores && typeof payload.scores === 'object' && Object.keys(payload.scores).length > 0;
  return (
    <div
      data-testid="universal-qn-result-card"
      style={{
        background: '#FFFFFF',
        borderRadius: 14,
        width: '100%',
        maxWidth: 360,
        overflow: 'hidden',
        boxShadow: '0 2px 12px rgba(15, 23, 42, 0.06)',
        border: '1px solid #EEF2F7',
      }}
    >
      <div
        style={{
          height: 6,
          background: `linear-gradient(90deg, ${coverColor} 0%, ${coverColor}88 100%)`,
        }}
      />
      <div style={{ padding: '12px 14px 8px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: 4,
          }}
        >
          <div style={{ fontSize: 12, color: '#94A3B8' }}>
            {payload.icon ? payload.icon + ' ' : ''}
            {payload.questionnaire_name || '测评结果'}
          </div>
          <div style={{ fontSize: 11, color: '#94A3B8' }}>{completed}</div>
        </div>
        {payload.subject_name && (
          <div style={{ fontSize: 12, color: '#64748B', marginBottom: 6 }}>
            被测人：{payload.subject_name}
          </div>
        )}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginTop: 4,
            marginBottom: 6,
          }}
        >
          <div
            style={{
              padding: '3px 10px',
              background: coverColor + '1A',
              color: coverColor,
              borderRadius: 999,
              fontSize: 14,
              fontWeight: 700,
            }}
          >
            主：{mainType}
          </div>
          {secondary.length > 0 && (
            <div style={{ fontSize: 12, color: '#64748B' }}>兼：{secondary.join('、')}</div>
          )}
        </div>
        {payload.main_type_desc && (
          <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.6, marginBottom: 6 }}>
            {payload.main_type_desc}
          </div>
        )}
        {hasScores && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              padding: '4px 0 0',
            }}
          >
            <MiniRadar scores={payload.scores as Record<string, number>} color={coverColor} />
          </div>
        )}
        {!hasScores && payload.fields && payload.fields.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
            {payload.fields.slice(0, 4).map((f) => (
              <div key={f.key} style={{ fontSize: 12, color: '#475569' }}>
                <span style={{ color: '#94A3B8' }}>{f.label}：</span>
                {f.value || '—'}
              </div>
            ))}
          </div>
        )}
      </div>
      <button
        type="button"
        data-testid="universal-qn-result-detail-btn"
        onClick={() => onClickDetail && onClickDetail(payload.detail_target || {})}
        style={{
          width: '100%',
          border: 'none',
          borderTop: '1px solid #EEF2F7',
          background: '#F8FAFC',
          color: coverColor,
          padding: '10px 0',
          fontSize: 13,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        查看详情 ›
      </button>
    </div>
  );
}
