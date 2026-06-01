'use client';

/**
 * [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用问卷结果卡片（AI 侧）
 *
 * 接受后端通用卡片协议 `questionnaire_result_card.card` payload，
 * 在 AI 对话流中呈现 6 屏沉浸式详情页的入口卡。
 *
 * 视觉风格统一为「报告卡片化稿 2」：白底圆角 + 顶部色块 + 主结论 + 9 维迷你雷达。
 */

import React, { useEffect, useRef, useState } from 'react';
import api from '@/lib/api';

export interface UniversalCardPayload {
  questionnaire_code?: string | null;
  questionnaire_name?: string | null;
  subject_name?: string | null;
  // [BUG-HSC-FIX-V2 2026-05-21] B-2：区分本人/家人档案
  subject_kind?: 'self' | 'family' | string | null;
  subject_relation?: string | null;
  subject_label?: string | null;
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

  // [PRD-HSC-OPTIM-V3 2026-05-21] AI 解读状态：仅对健康自查（answer_id 存在）轮询
  const answerId = payload.answer_id || payload.result_id;
  const isHsc = (payload.questionnaire_code || '') === 'health_self_check';
  const [aiStatus, setAiStatus] = useState<'pending' | 'done' | 'failed' | 'unknown'>(
    isHsc ? 'pending' : 'done',
  );
  const pollRef = useRef<any>(null);
  const startedAtRef = useRef<number>(0);

  useEffect(() => {
    if (!isHsc || !answerId) {
      setAiStatus('done');
      return;
    }
    let cancelled = false;
    const stop = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    const poll = async () => {
      try {
        const st = await api.get<any>(`/api/questionnaire/answers/${answerId}/ai-status`);
        if (cancelled) return;
        const s = (st?.ai_status || 'done') as any;
        setAiStatus(s);
        if (s !== 'pending') stop();
        if (Date.now() - startedAtRef.current > 60000) {
          stop();
          if (s === 'pending') setAiStatus('failed');
        }
      } catch {
        // 静默忽略
      }
    };
    // 立即查一次，再以 3s 轮询
    startedAtRef.current = Date.now();
    poll();
    pollRef.current = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      stop();
    };
  }, [isHsc, answerId]);

  const handleRetry = async () => {
    if (!answerId) return;
    try {
      await api.post(`/api/questionnaire/answers/${answerId}/retry-ai`, {});
      setAiStatus('pending');
      // 重启轮询
      if (pollRef.current) clearInterval(pollRef.current);
      startedAtRef.current = Date.now();
      const poll = async () => {
        try {
          const st = await api.get<any>(`/api/questionnaire/answers/${answerId}/ai-status`);
          const s = (st?.ai_status || 'done') as any;
          setAiStatus(s);
          if (s !== 'pending' && pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        } catch {
          /* noop */
        }
      };
      pollRef.current = setInterval(poll, 3000);
    } catch {
      /* noop */
    }
  };

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
        {(() => {
          // [BUG-HSC-FIX-V2 2026-05-21] B-2：优先使用 subject_label（后端已计算好），
          // 否则按 subject_kind 兜底拼装 "姓名（关系）" / "本人"
          const label =
            payload.subject_label ||
            (payload.subject_kind === 'family' && payload.subject_name
              ? payload.subject_relation
                ? `${payload.subject_name}（${payload.subject_relation}）`
                : payload.subject_name
              : payload.subject_name || '');
          if (!label) return null;
          return (
            <div
              style={{ fontSize: 12, color: '#64748B', marginBottom: 6 }}
              data-testid="qn-card-subject-label"
            >
              被测人：{label}
            </div>
          );
        })()}
        {/* [PRD-TIZHI-OPTIM-V1] 优化点 1：主体质一行完整显示不换行，兼夹体质自动排到下一行 */}
        <div
          data-testid="qn-card-constitution-rows"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 4,
            marginTop: 4,
            marginBottom: 6,
          }}
        >
          <div
            data-testid="qn-card-main-type"
            style={{
              maxWidth: '100%',
              padding: '3px 12px',
              background: coverColor + '1A',
              color: coverColor,
              borderRadius: 999,
              fontSize: 14,
              fontWeight: 700,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            主：{mainType}
          </div>
          {secondary.length > 0 && (
            <div
              data-testid="qn-card-secondary-type"
              style={{
                fontSize: 12,
                color: '#64748B',
                lineHeight: 1.5,
                wordBreak: 'break-all',
              }}
            >
              兼：{secondary.join('、')}
            </div>
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
      {(() => {
        // [PRD-HSC-OPTIM-V3 2026-05-21] 按 ai_status 联动「查看详情」按钮：
        //  - pending → 灰色 + 文案「分析中...」+ 禁用
        //  - done    → 主题色 + 文案「查看详情」+ 可点
        //  - failed  → 红色 + 文案「重试解读」+ 可点
        if (aiStatus === 'pending') {
          return (
            <button
              type="button"
              data-testid="universal-qn-result-detail-btn"
              disabled
              style={{
                width: '100%',
                border: 'none',
                borderTop: '1px solid #EEF2F7',
                background: '#F1F5F9',
                color: '#94A3B8',
                padding: '10px 0',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'not-allowed',
              }}
            >
              分析中...
            </button>
          );
        }
        if (aiStatus === 'failed') {
          return (
            <button
              type="button"
              data-testid="universal-qn-result-detail-btn"
              onClick={handleRetry}
              style={{
                width: '100%',
                border: 'none',
                borderTop: '1px solid #EEF2F7',
                background: '#FEF2F2',
                color: '#DC2626',
                padding: '10px 0',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              重试解读
            </button>
          );
        }
        return (
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
        );
      })()}
    </div>
  );
}
