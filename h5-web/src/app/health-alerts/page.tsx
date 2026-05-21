'use client';

/**
 * [PRD-HEALTH-ARCHIVE-V5-20260521] 健康预警列表页
 *
 * 路由：/health-alerts?member_id=xxx
 *
 * 功能：
 *   F12 双 Tab（未处理 / 已处理） + 类型筛选 + 时间倒序
 *   F13 合并规则（后端 _seed/24h 已实现，前端只展示 merged_count）
 *   F14 关联原始数据抽屉（点击预警条目）
 *   批量「全部标记已处理」
 */

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import {
  AlertItem,
  AlertType,
  fetchAlerts,
  resolveAlert,
  resolveAllAlerts,
} from '@/lib/api/health-archive-v5';

const TYPE_LABEL: Record<AlertType, string> = {
  checkup: '体检',
  medication: '用药',
  device: '设备',
  manual: '手动',
};
const TYPE_ICON: Record<AlertType, string> = {
  checkup: '📋',
  medication: '💊',
  device: '📟',
  manual: '✏️',
};
const SEVERITY_COLOR: Record<string, { bar: string; dot: string; label: string }> = {
  high: { bar: '#DC2626', dot: '🔴', label: '高' },
  medium: { bar: '#F97316', dot: '🟠', label: '中' },
  low: { bar: '#EAB308', dot: '🟡', label: '低' },
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const yyyy = d.getFullYear();
    const mm = `${d.getMonth() + 1}`.padStart(2, '0');
    const dd = `${d.getDate()}`.padStart(2, '0');
    const hh = `${d.getHours()}`.padStart(2, '0');
    const mi = `${d.getMinutes()}`.padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  } catch {
    return iso;
  }
}

function HealthAlertsInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const memberIdParam = sp.get('member_id');
  const memberId = memberIdParam ? Number(memberIdParam) : null;

  const [tab, setTab] = useState<'open' | 'done'>('open');
  const [typeFilter, setTypeFilter] = useState<AlertType | 'all'>('all');
  const [items, setItems] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [drawer, setDrawer] = useState<AlertItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchAlerts({
        memberId,
        status: tab,
        alertType: typeFilter === 'all' ? undefined : typeFilter,
      });
      setItems(res.items || []);
    } catch (e: any) {
      showToast('加载预警失败', 'fail');
    } finally {
      setLoading(false);
    }
  }, [memberId, tab, typeFilter]);

  useEffect(() => { load(); }, [load]);

  const handleResolve = useCallback(async (id: number) => {
    try {
      await resolveAlert(id);
      showToast('已标记已处理');
      await load();
    } catch {
      showToast('操作失败，请重试', 'fail');
    }
  }, [load]);

  const handleResolveAll = useCallback(async () => {
    try {
      await resolveAllAlerts(memberId);
      showToast('已全部标记已处理');
      await load();
    } catch {
      showToast('操作失败，请重试', 'fail');
    }
  }, [load, memberId]);

  const navTitle = '健康预警';

  return (
    <div style={{ background: '#F5F7FA', minHeight: '100vh', paddingBottom: 64 }}>
      <GreenNavBar back={() => router.back()}>{navTitle}</GreenNavBar>
      {/* Tab + 筛选 */}
      <div style={{ background: '#fff', padding: '10px 16px', boxShadow: '0 1px 0 rgba(0,0,0,0.04)' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['open', 'done'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                flex: 1,
                padding: '8px 0',
                borderRadius: 8,
                border: '1px solid ' + (tab === t ? '#FF6B35' : '#E5E7EB'),
                background: tab === t ? '#FFF1EA' : '#fff',
                color: tab === t ? '#FF6B35' : '#374151',
                fontWeight: tab === t ? 600 : 400,
              }}
            >
              {t === 'open' ? '未处理' : '已处理'}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 10, overflowX: 'auto' }}>
          {(['all', 'checkup', 'medication', 'device', 'manual'] as const).map((tp) => (
            <button
              key={tp}
              onClick={() => setTypeFilter(tp as any)}
              style={{
                whiteSpace: 'nowrap',
                padding: '4px 12px',
                borderRadius: 999,
                border: '1px solid ' + (typeFilter === tp ? '#FF6B35' : '#E5E7EB'),
                background: typeFilter === tp ? '#FFF1EA' : '#fff',
                color: typeFilter === tp ? '#FF6B35' : '#6B7280',
                fontSize: 12,
              }}
            >
              {tp === 'all' ? '全部' : TYPE_LABEL[tp as AlertType]}
            </button>
          ))}
        </div>
      </div>

      {tab === 'open' && items.length > 0 && (
        <div style={{ padding: '12px 16px 0' }}>
          <button
            onClick={handleResolveAll}
            style={{
              width: '100%',
              padding: '8px 0',
              borderRadius: 8,
              border: '1px solid #FF6B35',
              background: '#fff',
              color: '#FF6B35',
              fontWeight: 500,
            }}
          >
            全部标记已处理（共 {items.length} 条）
          </button>
        </div>
      )}

      <div style={{ padding: '12px 16px' }}>
        {loading && <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>加载中...</div>}
        {!loading && items.length === 0 && (
          <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF' }}>
            {tab === 'open' ? '暂无未处理预警 🎉' : '暂无已处理预警'}
          </div>
        )}
        {items.map((it) => {
          const sev = SEVERITY_COLOR[it.severity] || SEVERITY_COLOR.medium;
          return (
            <div
              key={it.id}
              onClick={() => setDrawer(it)}
              style={{
                background: '#fff',
                borderRadius: 12,
                padding: 12,
                marginBottom: 10,
                borderLeft: `4px solid ${sev.bar}`,
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 16 }}>{TYPE_ICON[it.alert_type]}</span>
                <span style={{ fontWeight: 600, color: '#111827', flex: 1 }}>
                  {sev.dot} {it.title}
                </span>
                <span style={{ fontSize: 11, color: sev.bar, padding: '2px 6px', background: sev.bar + '22', borderRadius: 4 }}>{sev.label}</span>
              </div>
              <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 6 }}>
                {formatTime(it.last_occurred_at)}
                {it.source_label ? ` · ${it.source_label}` : ''}
                {it.merged_count > 1 ? `（近24小时累计 ${it.merged_count} 次）` : ''}
              </div>
              {it.advice && (
                <div style={{ fontSize: 13, color: '#374151', background: '#F9FAFB', padding: 8, borderRadius: 6 }}>
                  💡 {it.advice}
                </div>
              )}
              {tab === 'open' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button
                    onClick={(e) => { e.stopPropagation(); setDrawer(it); }}
                    style={{ flex: 1, padding: '6px 0', borderRadius: 6, border: '1px solid #D1D5DB', background: '#fff', color: '#374151', fontSize: 13 }}
                  >查看关联原始数据</button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleResolve(it.id); }}
                    style={{ flex: 1, padding: '6px 0', borderRadius: 6, border: 'none', background: '#FF6B35', color: '#fff', fontSize: 13 }}
                  >标记已处理</button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 底部抽屉 */}
      {drawer && (
        <div
          onClick={() => setDrawer(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 50 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              position: 'absolute', left: 0, right: 0, bottom: 0,
              background: '#fff', borderRadius: '16px 16px 0 0',
              padding: 16, maxHeight: '70vh', overflowY: 'auto',
            }}
          >
            <div style={{ width: 36, height: 4, background: '#D1D5DB', borderRadius: 2, margin: '0 auto 12px' }} />
            <div style={{ fontWeight: 600, marginBottom: 8 }}>{drawer.title}</div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 12 }}>
              {TYPE_LABEL[drawer.alert_type]} · {drawer.source_label || '—'} · {formatTime(drawer.last_occurred_at)}
            </div>
            {drawer.detail && (
              <div style={{ background: '#F9FAFB', padding: 12, borderRadius: 8, marginBottom: 12, color: '#374151', fontSize: 14 }}>
                {drawer.detail}
              </div>
            )}
            {drawer.raw_payload && (
              <div style={{ background: '#F3F4F6', padding: 12, borderRadius: 8, marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>原始数据</div>
                <pre style={{ margin: 0, fontSize: 12, color: '#374151', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
{typeof drawer.raw_payload === 'string' ? drawer.raw_payload : JSON.stringify(drawer.raw_payload, null, 2)}
                </pre>
              </div>
            )}
            {drawer.advice && (
              <div style={{ background: '#FFF7ED', padding: 12, borderRadius: 8, marginBottom: 12, color: '#9A3412', fontSize: 14 }}>
                💡 {drawer.advice}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              {drawer.ref_record_id && (
                <button
                  onClick={() => { router.push(`/medical-records/${drawer.ref_record_id}`); setDrawer(null); }}
                  style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff' }}
                >查看完整资料</button>
              )}
              {drawer.ref_plan_id && (
                <button
                  onClick={() => { router.push(`/ai-home/medication-plans/${drawer.ref_plan_id}`); setDrawer(null); }}
                  style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff' }}
                >查看用药计划</button>
              )}
              {drawer.status === 'open' && (
                <button
                  onClick={async () => { await handleResolve(drawer.id); setDrawer(null); }}
                  style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: 'none', background: '#FF6B35', color: '#fff' }}
                >标记已处理</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function HealthAlertsPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>加载中...</div>}>
      <HealthAlertsInner />
    </Suspense>
  );
}
