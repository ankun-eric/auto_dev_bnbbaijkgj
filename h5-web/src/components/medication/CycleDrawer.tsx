'use client';

/**
 * [PRD-MED-PLAN-OPTIM-V1 2026-05-17] 服用周期抽屉
 *
 * - 顶部两个日期选择框并排：开始日期 / 结束日期
 * - 下方：长期服用 + Switch
 * - 长期态：结束日期框灰色禁用，显示"长期"
 * - 底部：共 N 天 / 长期服用，无固定结束日
 * - 校验保存：结束日期 ≥ 开始日期，否则提示
 *
 * 业务规则：
 *  - 开始日期允许过去 90 天内
 *  - 结束日期从开始日期起最远 3 年
 */

import { useEffect, useState } from 'react';
import { showToast } from '@/lib/toast-unified';

const PRIMARY = '#0EA5E9';

function toISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function parseISO(s: string | null | undefined): Date | null {
  if (!s) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  d.setHours(0, 0, 0, 0);
  return d;
}
function diffDays(a: Date, b: Date): number {
  const ms = b.getTime() - a.getTime();
  return Math.round(ms / 86400000) + 1;
}

export interface CycleValue {
  startDate: string;      // YYYY-MM-DD
  endDate: string | null; // null when isLongTerm
  isLongTerm: boolean;
}

export default function CycleDrawer({
  value,
  onConfirm,
  onCancel,
}: {
  value: CycleValue;
  onConfirm: (v: CycleValue) => void;
  onCancel: () => void;
}) {
  const [start, setStart] = useState<string>(value.startDate);
  const [end, setEnd] = useState<string>(value.endDate || '');
  const [longTerm, setLongTerm] = useState<boolean>(value.isLongTerm);

  useEffect(() => {
    if (longTerm) return;
    if (!end) {
      const s = parseISO(start);
      if (s) {
        const e = new Date(s.getTime());
        e.setDate(e.getDate() + 29);
        setEnd(toISO(e));
      }
    }
  }, [longTerm, start, end]);

  const minStart = (() => {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    return toISO(d);
  })();
  const maxEnd = (() => {
    const s = parseISO(start) || new Date();
    const d = new Date(s.getTime());
    d.setFullYear(d.getFullYear() + 3);
    return toISO(d);
  })();

  const total = (() => {
    const s = parseISO(start);
    const e = parseISO(end);
    if (longTerm || !s || !e) return null;
    return diffDays(s, e);
  })();

  const submit = () => {
    const s = parseISO(start);
    if (!s) {
      showToast('请选择开始日期');
      return;
    }
    if (longTerm) {
      onConfirm({ startDate: start, endDate: null, isLongTerm: true });
      return;
    }
    const e = parseISO(end);
    if (!e) {
      showToast('请选择结束日期');
      return;
    }
    if (e.getTime() < s.getTime()) {
      showToast('结束日期不能早于开始日期');
      return;
    }
    onConfirm({ startDate: start, endDate: end, isLongTerm: false });
  };

  return (
    <div
      onClick={onCancel}
      data-testid="cycle-drawer-mask"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          width: '100%',
          maxWidth: 600,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: 20,
        }}
      >
        <div style={{ textAlign: 'center', fontSize: 15, fontWeight: 600, color: '#111827', paddingBottom: 12, borderBottom: '1px solid #E5E7EB' }}>
          服用周期
        </div>

        <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 6 }}>开始日期</div>
            <input
              data-testid="cycle-start-input"
              type="date"
              value={start}
              min={minStart}
              onChange={(e) => setStart(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #D1D5DB',
                fontSize: 14,
                background: '#fff',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 6 }}>结束日期</div>
            {longTerm ? (
              <div
                data-testid="cycle-end-locked"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid #E5E7EB',
                  fontSize: 14,
                  background: '#F3F4F6',
                  color: '#9CA3AF',
                  boxSizing: 'border-box',
                }}
              >
                长期
              </div>
            ) : (
              <input
                data-testid="cycle-end-input"
                type="date"
                value={end}
                min={start || undefined}
                max={maxEnd}
                onChange={(e) => setEnd(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid #D1D5DB',
                  fontSize: 14,
                  background: '#fff',
                  boxSizing: 'border-box',
                }}
              />
            )}
          </div>
        </div>

        <div
          style={{
            marginTop: 16,
            padding: '12px 14px',
            background: '#F9FAFB',
            borderRadius: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: 14, color: '#111827' }}>长期服用</span>
          <button
            data-testid="cycle-longterm-switch"
            onClick={() => setLongTerm((v) => !v)}
            aria-pressed={longTerm}
            style={{
              width: 44,
              height: 24,
              borderRadius: 12,
              border: 'none',
              background: longTerm ? PRIMARY : '#E5E7EB',
              position: 'relative',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <span
              style={{
                position: 'absolute',
                top: 2,
                left: longTerm ? 22 : 2,
                width: 20,
                height: 20,
                borderRadius: 10,
                background: '#fff',
                transition: 'left 0.18s',
                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              }}
            />
          </button>
        </div>

        <div style={{ marginTop: 12, fontSize: 12, color: longTerm ? PRIMARY : '#6B7280', fontWeight: longTerm ? 500 : 400 }}>
          {longTerm ? '长期服用，无固定结束日' : total != null ? `共 ${total} 天` : '请选择起止日期'}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>
          <button
            data-testid="cycle-cancel"
            onClick={onCancel}
            style={{
              flex: 1,
              height: 40,
              borderRadius: 8,
              border: '1px solid #E5E7EB',
              background: '#fff',
              color: '#6B7280',
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            取消
          </button>
          <button
            data-testid="cycle-confirm"
            onClick={submit}
            style={{
              flex: 1,
              height: 40,
              borderRadius: 8,
              border: 'none',
              background: PRIMARY,
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            确定
          </button>
        </div>
      </div>
    </div>
  );
}
