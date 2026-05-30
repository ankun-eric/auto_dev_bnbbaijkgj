'use client';

/**
 * [PRD-HEALTH-METRIC-CARD-UNIFY-V1 2026-05-31] 健康指标全部历史页（四指标通用）
 *
 * 路径：/health-metric/[type]/history?profileId=xxx
 *   type ∈ blood_pressure / blood_glucose / heart_rate / spo2
 *
 * PRD §五：支持 4 个筛选项 + 分页/无限滚动；点击改、左滑删（手工录入），设备同步只读。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Popup, Button } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import { formatDateTime } from '@/lib/datetime';

interface StatusInfo {
  key: string;
  label: string;
  color: string;
}

interface HistoryItem {
  id: number;
  profile_id: number;
  metric_type: string;
  value: Record<string, any>;
  source: string;
  scene?: string | null;
  note?: string;
  measured_at: string;
  created_at?: string;
  editable: boolean;
  status: StatusInfo;
}

interface HistoryResp {
  metric_type: string;
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  items: HistoryItem[];
  meta: {
    label: string;
    unit: string;
    principal: string;
    secondary?: string | null;
    scene_options: string[];
  };
}

const STATUS_OPTIONS_BY_TYPE: Record<string, { key: string; label: string }[]> = {
  blood_pressure: [
    { key: 'low', label: '偏低' },
    { key: 'normal', label: '正常' },
    { key: 'mild_high', label: '轻度偏高' },
    { key: 'mid_high', label: '中度偏高' },
    { key: 'severe_high', label: '严重偏高' },
  ],
  blood_glucose: [
    { key: 'low', label: '偏低' },
    { key: 'normal', label: '正常' },
    { key: 'mid_high', label: '偏高' },
    { key: 'severe_high', label: '严重偏高' },
  ],
  heart_rate: [
    { key: 'low', label: '偏低' },
    { key: 'normal', label: '正常' },
    { key: 'high', label: '偏高' },
  ],
  spo2: [
    { key: 'mild_low', label: '偏低' },
    { key: 'mid_low', label: '较低' },
    { key: 'severe_low', label: '严重偏低' },
    { key: 'normal', label: '正常' },
  ],
};

const DATE_RANGE_OPTIONS = [
  { key: '7d', label: '近 7 天' },
  { key: '30d', label: '近 30 天' },
  { key: '90d', label: '近 90 天' },
  { key: 'custom', label: '全部' },
];

const SOURCE_OPTIONS = [
  { key: 'all', label: '全部' },
  { key: 'manual', label: '手工录入' },
  { key: 'device', label: '智能设备同步' },
];

const STATUS_COLOR: Record<string, { bg: string; text: string }> = {
  blue: { bg: '#DBEAFE', text: '#1E40AF' },
  yellow: { bg: '#FEF3C7', text: '#92400E' },
  orange: { bg: '#FED7AA', text: '#9A3412' },
  red: { bg: '#FEE2E2', text: '#991B1B' },
  gray: { bg: '#F1F5F9', text: '#475569' },
};

function formatMetricValue(metricType: string, value: Record<string, any>, unit: string): string {
  if (metricType === 'blood_pressure') {
    return `${value?.systolic ?? '-'}/${value?.diastolic ?? '-'} ${unit}`;
  }
  return `${value?.value ?? '-'} ${unit}`;
}

function timeOnly(iso: string): string {
  const full = formatDateTime(iso) || '';
  return full.slice(11, 16) || full;
}

function dateOnly(iso: string): string {
  const full = formatDateTime(iso) || '';
  return full.slice(0, 10);
}

export default function HealthMetricHistoryPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const metricType = (params?.type as string) || 'blood_pressure';
  const profileId = Number(searchParams?.get('profileId') || 0);

  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [meta, setMeta] = useState<HistoryResp['meta'] | null>(null);

  // 筛选状态
  const [dateRange, setDateRange] = useState('7d');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sceneFilter, setSceneFilter] = useState<string>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');

  // 左滑状态
  const [swipedRowId, setSwipedRowId] = useState<number | null>(null);

  // 删除二次确认弹窗
  const [deletingItem, setDeletingItem] = useState<HistoryItem | null>(null);

  // 只读详情弹窗（设备同步记录）
  const [readOnlyItem, setReadOnlyItem] = useState<HistoryItem | null>(null);

  const PAGE_SIZE = 20;
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const fetchPage = useCallback(async (pg: number, replace: boolean) => {
    if (!profileId) return;
    setLoading(true);
    try {
      const res: any = await api.get(
        `/api/health-metric-v1/${profileId}/${metricType}/history`,
        {
          params: {
            page: pg,
            page_size: PAGE_SIZE,
            date_range: dateRange,
            status: statusFilter,
            scene: sceneFilter,
            source: sourceFilter,
          },
        }
      );
      const data: HistoryResp = res?.data?.data ?? res?.data ?? res;
      const newItems = data?.items || [];
      setMeta(data?.meta || null);
      setTotal(data?.total || 0);
      setHasMore(!!data?.has_more);
      setItems(prev => replace ? newItems : [...prev, ...newItems]);
      setPage(pg);
    } catch (e) {
      showToast('加载失败，请重试', 'fail');
    } finally {
      setLoading(false);
    }
  }, [profileId, metricType, dateRange, statusFilter, sceneFilter, sourceFilter]);

  useEffect(() => {
    fetchPage(1, true);
  }, [fetchPage]);

  // 无限滚动
  useEffect(() => {
    if (!sentinelRef.current) return;
    const el = sentinelRef.current;
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && !loading && hasMore) {
        fetchPage(page + 1, false);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [page, loading, hasMore, fetchPage]);

  const statusOptions = STATUS_OPTIONS_BY_TYPE[metricType] || [];

  const handleDelete = useCallback(async (item: HistoryItem) => {
    if (!profileId || !item.editable) return;
    try {
      await api.delete(`/api/health-profile-v3/${profileId}/metric/${metricType}/${item.id}`);
      showToast('已删除', 'success');
      setDeletingItem(null);
      setSwipedRowId(null);
      await fetchPage(1, true);
    } catch {
      showToast('删除失败', 'fail');
    }
  }, [profileId, metricType, fetchPage]);

  const navBarTitle = `${meta?.label || ''}全部历史`;

  return (
    <div data-testid="metric-history-page" style={{ background: '#F4F7FB', minHeight: '100vh', paddingBottom: 24 }}>
      <GreenNavBar>{navBarTitle}</GreenNavBar>

      {/* 筛选区 */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: 14, boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          <FilterRow
            label="📅 日期范围"
            value={dateRange}
            options={DATE_RANGE_OPTIONS}
            onChange={setDateRange}
            testIdPrefix="filter-date"
          />
          {statusOptions.length > 0 && (
            <FilterRow
              label="🩺 状态档位"
              value={statusFilter}
              options={[{ key: 'all', label: '全部' }, ...statusOptions]}
              onChange={setStatusFilter}
              testIdPrefix="filter-status"
            />
          )}
          {(meta?.scene_options || []).length > 0 && (
            <FilterRow
              label="📍 测量场景"
              value={sceneFilter}
              options={[
                { key: 'all', label: '全部' },
                ...(meta!.scene_options).map((s: string) => ({ key: s, label: s })),
              ]}
              onChange={setSceneFilter}
              testIdPrefix="filter-scene"
            />
          )}
          <FilterRow
            label="📡 数据来源"
            value={sourceFilter}
            options={SOURCE_OPTIONS}
            onChange={setSourceFilter}
            testIdPrefix="filter-source"
          />
        </div>
      </div>

      {/* 总条数 + 筛选状态 */}
      <div data-testid="metric-history-count" style={{ padding: '10px 16px 0', fontSize: 13, color: '#475569' }}>
        共 {total} 条
        {(dateRange !== '7d' || statusFilter !== 'all' || sceneFilter !== 'all' || sourceFilter !== 'all') && ' · 已筛选'}
      </div>

      {/* 列表 */}
      <div style={{ padding: '8px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: '4px 14px', boxShadow: '0 2px 10px rgba(14,165,233,0.06)' }}>
          {items.length === 0 && !loading ? (
            <div style={{ fontSize: 14, color: '#6B7280', textAlign: 'center', padding: '32px 0' }}>
              暂无记录，点击右上角「+录入」开始记录
            </div>
          ) : (
            items.map(item => (
              <HistoryRow
                key={item.id}
                item={item}
                metricType={metricType}
                unit={meta?.unit || ''}
                isSwiped={swipedRowId === item.id}
                onSwipe={(swiped) => setSwipedRowId(swiped ? item.id : null)}
                onClickRow={() => {
                  if (swipedRowId === item.id) {
                    setSwipedRowId(null);
                    return;
                  }
                  if (item.editable) {
                    // 跳回详情页编辑：本期简化，提示用户去详情页修改
                    showToast('请在详情页编辑该记录', 'success');
                  } else {
                    setReadOnlyItem(item);
                  }
                }}
                onClickDelete={() => setDeletingItem(item)}
              />
            ))
          )}
          {loading && (
            <div style={{ fontSize: 13, color: '#9CA3AF', textAlign: 'center', padding: '12px 0' }}>
              加载中…
            </div>
          )}
          {!hasMore && items.length > 0 && (
            <div style={{ fontSize: 12, color: '#9CA3AF', textAlign: 'center', padding: '12px 0' }}>
              — 已显示全部 {total} 条 —
            </div>
          )}
          <div ref={sentinelRef} style={{ height: 1 }} />
        </div>
      </div>

      {/* 删除二次确认弹窗 - 信息完整版 */}
      <Popup
        visible={!!deletingItem}
        onMaskClick={() => setDeletingItem(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        {deletingItem && (
          <div data-testid="metric-delete-confirm">
            <div style={{ fontSize: 17, fontWeight: 700, color: '#0C4A6E', marginBottom: 14 }}>
              确认删除这条记录？
            </div>
            <div style={{ background: '#F8FAFC', borderRadius: 12, padding: 14, marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#475569', marginBottom: 6 }}>
                📅 {formatDateTime(deletingItem.measured_at)}
              </div>
              <div style={{ fontSize: 14, color: '#0C4A6E', fontWeight: 600 }}>
                🩺 {meta?.label || ''} {formatMetricValue(metricType, deletingItem.value, meta?.unit || '')}
                <span style={{
                  marginLeft: 8, fontSize: 12, padding: '2px 8px', borderRadius: 999,
                  background: STATUS_COLOR[deletingItem.status?.color || 'gray'].bg,
                  color: STATUS_COLOR[deletingItem.status?.color || 'gray'].text,
                }}>
                  {deletingItem.status?.label || ''}
                </span>
              </div>
            </div>
            <div style={{ fontSize: 13, color: '#DC2626', marginBottom: 16 }}>
              ⚠️ 删除后无法恢复
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setDeletingItem(null)}
                style={{
                  flex: 1, padding: '10px 0', background: '#fff', color: '#475569',
                  border: '1px solid #CBD5E1', borderRadius: 12,
                  fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >取消</button>
              <button
                data-testid="metric-delete-confirm-btn"
                onClick={() => handleDelete(deletingItem)}
                style={{
                  flex: 1, padding: '10px 0', background: '#DC2626', color: '#fff',
                  border: 'none', borderRadius: 12,
                  fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >确认删除</button>
            </div>
          </div>
        )}
      </Popup>

      {/* 只读详情弹窗（设备同步记录） */}
      <Popup
        visible={!!readOnlyItem}
        onMaskClick={() => setReadOnlyItem(null)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 }}
      >
        {readOnlyItem && (
          <div data-testid="metric-readonly-popup">
            <div style={{ fontSize: 17, fontWeight: 700, color: '#0C4A6E', marginBottom: 14 }}>
              测量详情
            </div>
            <div style={{ background: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: 10, padding: 12, marginBottom: 14 }}>
              <div style={{ fontSize: 12, color: '#92400E' }}>
                🔒 该记录来自智能设备，数据已锁定。如需修正，请重新测量。
              </div>
            </div>
            <DetailRow k="测量时间" v={formatDateTime(readOnlyItem.measured_at)} />
            <DetailRow k={`${meta?.label || ''}数值`} v={formatMetricValue(metricType, readOnlyItem.value, meta?.unit || '')} />
            <DetailRow k="状态档位" v={readOnlyItem.status?.label || '-'} />
            {readOnlyItem.scene && <DetailRow k="测量场景" v={readOnlyItem.scene} />}
            <DetailRow k="数据来源" v={readOnlyItem.source} />
            <Button
              block color="primary" onClick={() => setReadOnlyItem(null)}
              style={{ '--background-color': '#0EA5E9', '--border-radius': '12px', height: 40, fontSize: 14, marginTop: 12 } as any}
            >知道了</Button>
          </div>
        )}
      </Popup>
    </div>
  );
}

function FilterRow({ label, value, options, onChange, testIdPrefix }: {
  label: string;
  value: string;
  options: { key: string; label: string }[];
  onChange: (v: string) => void;
  testIdPrefix?: string;
}) {
  return (
    <div style={{ padding: '8px 0', borderBottom: '1px solid #F1F5F9' }}>
      <div style={{ fontSize: 13, color: '#475569', marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {options.map(opt => (
          <button
            key={opt.key}
            data-testid={`${testIdPrefix}-${opt.key}`}
            onClick={() => onChange(opt.key)}
            style={{
              padding: '5px 12px',
              background: value === opt.key ? '#0EA5E9' : '#F1F5F9',
              color: value === opt.key ? '#fff' : '#475569',
              border: 'none', borderRadius: 999,
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}
          >{opt.label}</button>
        ))}
      </div>
    </div>
  );
}

function HistoryRow({
  item, metricType, unit, isSwiped, onSwipe, onClickRow, onClickDelete,
}: {
  item: HistoryItem;
  metricType: string;
  unit: string;
  isSwiped: boolean;
  onSwipe: (swiped: boolean) => void;
  onClickRow: () => void;
  onClickDelete: () => void;
}) {
  const statusColor = STATUS_COLOR[item.status?.color || 'gray'];
  const time = timeOnly(item.measured_at);
  const sourceLabel = (item.source || 'manual') === 'manual' ? '手工录入' : '设备同步';

  return (
    <div
      data-testid={`metric-history-row-${item.id}`}
      style={{ position: 'relative', overflow: 'hidden', borderBottom: '1px solid #F1F5F9' }}
      onTouchStart={(e) => { (e.currentTarget as any)._sx = e.touches[0].clientX; }}
      onTouchEnd={(e) => {
        if (!item.editable) return;
        const sx = (e.currentTarget as any)._sx;
        const dx = sx ? sx - e.changedTouches[0].clientX : 0;
        if (dx > 40) onSwipe(true);
        else if (dx < -40) onSwipe(false);
      }}
    >
      <div
        onClick={onClickRow}
        style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '12px 0', cursor: 'pointer',
          transform: isSwiped ? 'translateX(-72px)' : 'translateX(0)',
          transition: 'transform 0.2s',
          background: '#fff',
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0C4A6E' }}>
            {time}　{formatMetricValue(metricType, item.value, unit)}
          </div>
          <div style={{ fontSize: 11, color: '#6B7280', marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {item.scene && (
              <span style={{ padding: '1px 8px', background: '#F1F5F9', color: '#475569', borderRadius: 999 }}>
                {item.scene}
              </span>
            )}
            <span style={{
              padding: '1px 8px',
              background: item.editable ? '#F1F5F9' : '#DBEAFE',
              color: item.editable ? '#475569' : '#1E40AF',
              borderRadius: 999,
            }}>
              {sourceLabel}
            </span>
            <span style={{ color: '#9CA3AF' }}>{dateOnly(item.measured_at)}</span>
          </div>
        </div>
        {item.status && (
          <span style={{
            fontSize: 11, fontWeight: 700,
            padding: '3px 10px', borderRadius: 999,
            background: statusColor.bg, color: statusColor.text,
          }}>
            {item.status.label}
          </span>
        )}
      </div>
      {item.editable && (
        <button
          data-testid={`metric-row-delete-${item.id}`}
          onClick={(e) => { e.stopPropagation(); onClickDelete(); }}
          style={{
            position: 'absolute', top: 0, right: 0, bottom: 0, width: 64,
            background: '#DC2626', color: '#fff', border: 'none', cursor: 'pointer',
            fontSize: 13, fontWeight: 600,
            transform: isSwiped ? 'translateX(0)' : 'translateX(64px)',
            transition: 'transform 0.2s',
          }}
        >删除</button>
      )}
    </div>
  );
}

function DetailRow({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #F1F5F9' }}>
      <span style={{ fontSize: 13, color: '#6B7280' }}>{k}</span>
      <span style={{ fontSize: 14, color: '#0C4A6E', fontWeight: 600 }}>{v}</span>
    </div>
  );
}
