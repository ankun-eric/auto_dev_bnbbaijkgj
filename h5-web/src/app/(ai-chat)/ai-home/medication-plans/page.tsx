'use client';

/**
 * [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划列表页（三 Tab）
 *
 * 路由：/ai-home/medication-plans
 *
 * 三 Tab：服药中 / 未开始 / 已结束
 * 默认 in_progress；点击单条 → /ai-home/medication-plans/:id
 * 右下浮动 + → /ai-home/medication-plans/new
 * ← 返回 → /health-profile?focus=medication
 *
 * 数据源：GET /api/health-plan/medications/list?tab=in_progress|not_started|finished
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast } from 'antd-mobile';
import api from '@/lib/api';

type TabKey = 'in_progress' | 'not_started' | 'finished';

interface PlanItem {
  id: number;
  medicine_name: string;
  drug_name?: string;
  dosage?: string;
  frequency?: string;
  frequency_per_day?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: string;
  long_term?: boolean;
  schedule?: string[];
  guidance?: string | null;
  dosage_value?: string | null;
  dosage_unit?: string | null;
}

const TABS: { id: TabKey; label: string }[] = [
  { id: 'in_progress', label: '服药中' },
  { id: 'not_started', label: '未开始' },
  { id: 'finished', label: '已结束' },
];

const BLUE = '#4A9EE0';
const GREEN = '#22c55e';
const TEXT = '#111827';
const SUB = '#6B7280';

export default function MedicationPlansListPage() {
  const router = useRouter();
  const sp = useSearchParams();
  const initialTab = (sp?.get('tab') as TabKey) || 'in_progress';
  const highlightId = sp?.get('highlight');
  const [tab, setTab] = useState<TabKey>(
    TABS.some((t) => t.id === initialTab) ? initialTab : 'in_progress',
  );
  const [items, setItems] = useState<PlanItem[]>([]);
  const [counts, setCounts] = useState<Record<TabKey, number>>({
    in_progress: 0,
    not_started: 0,
    finished: 0,
  });
  const [loading, setLoading] = useState(false);

  const loadTab = useCallback(async (t: TabKey) => {
    setLoading(true);
    try {
      const res: any = await api.get(`/api/health-plan/medications/list?tab=${t}`);
      const body = res.data || res;
      const list: PlanItem[] = Array.isArray(body.items) ? body.items : [];
      setItems(list);
    } catch (e) {
      Toast.show({ content: '加载失败', icon: 'fail' });
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCounts = useCallback(async () => {
    try {
      const results = await Promise.all(
        TABS.map((t) =>
          api.get(`/api/health-plan/medications/list?tab=${t.id}`).then((r: any) => {
            const body = r.data || r;
            return [t.id, Array.isArray(body.items) ? body.items.length : 0] as [TabKey, number];
          }),
        ),
      );
      const c: Record<TabKey, number> = { in_progress: 0, not_started: 0, finished: 0 };
      results.forEach(([k, v]) => (c[k] = v));
      setCounts(c);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadTab(tab);
  }, [tab, loadTab]);

  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  useEffect(() => {
    if (highlightId) {
      const el = document.querySelector(`[data-plan-id="${highlightId}"]`);
      if (el && (el as HTMLElement).scrollIntoView) {
        (el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [items, highlightId]);

  const goBack = () => router.push('/health-profile?focus=medication');

  const renderItem = (it: PlanItem) => {
    const isHighlighted = highlightId && String(highlightId) === String(it.id);
    const dosage = it.dosage_value && it.dosage_unit ? `${it.dosage_value} ${it.dosage_unit}` : it.dosage || '';
    const freq = it.frequency || `每日 ${it.frequency_per_day || (it.schedule?.length ?? 1)} 次`;
    const timing = it.guidance || '';
    const range =
      it.long_term
        ? '长期服用'
        : `${it.start_date || '—'} ~ ${it.end_date || '—'}`;
    const statusBadge =
      tab === 'in_progress' ? { text: '服用中', color: GREEN } :
      tab === 'not_started' ? { text: '未开始', color: BLUE } :
      { text: '已结束', color: '#9CA3AF' };

    return (
      <div
        key={it.id}
        data-plan-id={it.id}
        data-testid={`med-plan-item-${it.id}`}
        onClick={() => router.push(`/ai-home/medication-plans/${it.id}`)}
        style={{
          background: '#fff',
          padding: 14,
          borderRadius: 12,
          boxShadow: isHighlighted
            ? '0 0 0 2px rgba(74,158,224,0.6)'
            : '0 1px 2px rgba(0,0,0,0.04)',
          cursor: 'pointer',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: TEXT }}>
            💊 {it.medicine_name || it.drug_name}
          </span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: statusBadge.color,
              background: '#F3F4F6',
              padding: '2px 8px',
              borderRadius: 10,
            }}
          >
            {statusBadge.text}
          </span>
        </div>
        <div style={{ fontSize: 13, color: SUB, marginTop: 6 }}>
          {dosage && <span>{dosage} · </span>}
          <span>{freq}</span>
          {timing && <span> · {timing}</span>}
        </div>
        <div style={{ fontSize: 12, color: SUB, marginTop: 4 }}>{range}</div>
      </div>
    );
  };

  return (
    <div data-testid="med-plans-list" style={{ minHeight: '100vh', background: '#F4F6F9', paddingBottom: 100 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        <span
          onClick={goBack}
          style={{ fontSize: 24, color: TEXT, cursor: 'pointer', padding: 4 }}
          data-testid="med-plans-back"
        >
          ←
        </span>
        <span style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: 600 }}>用药计划</span>
        <span style={{ width: 32 }} />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', background: '#fff', padding: '0 8px' }}>
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`med-tab-${t.id}`}
              style={{
                flex: 1,
                padding: '12px 0',
                background: 'transparent',
                border: 'none',
                borderBottom: active ? `2px solid ${BLUE}` : '2px solid transparent',
                color: active ? BLUE : SUB,
                fontWeight: active ? 700 : 500,
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              {t.label}（{counts[t.id]}）
            </button>
          );
        })}
      </div>

      <div style={{ padding: '12px 16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: SUB, padding: 24 }}>加载中…</div>
        ) : items.length === 0 ? (
          <div
            style={{
              background: '#fff',
              padding: 40,
              borderRadius: 12,
              textAlign: 'center',
              color: SUB,
              fontSize: 14,
            }}
          >
            暂无用药计划
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {items.map(renderItem)}
          </div>
        )}
      </div>

      <div
        onClick={() => router.push('/ai-home/medication-plans/new')}
        data-testid="med-plans-fab"
        style={{
          position: 'fixed',
          right: 20,
          bottom: 24,
          width: 56,
          height: 56,
          borderRadius: 28,
          background: BLUE,
          color: '#fff',
          fontSize: 28,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(74,158,224,0.4)',
          cursor: 'pointer',
        }}
      >
        +
      </div>
    </div>
  );
}
