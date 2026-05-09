'use client';

/**
 * [PRD-439 F-04/F-05/F-06] 今日待办抽屉
 *
 * 底部弹出，无 Tab，上下两段：
 * - 用药提醒：含 ✓ 已服用 / 撤销，乐观更新
 * - 预约提醒：来源于 GET /api/medication-reminder/appointments
 *   单条点击就地展开订单详情（手风琴式，仅一条同时展开）
 */

import { useEffect, useState, useCallback } from 'react';
import api from '@/lib/api';

export interface MedicationItem {
  plan_id: number;
  drug_name: string;
  dosage: string;
  scheduled_time: string;
  note?: string | null;
  checked: boolean;
  checked_at?: string | null;
  log_id?: number | null;
}

export interface AppointmentItem {
  order_id: number;
  order_no?: string | null;
  service_name: string;
  appointed_at?: string | null;
  location?: string | null;
  status_text: string;
  qrcode_url?: string | null;
  verification_code?: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onGoMedicationManage?: () => void;
  onGoOrderList?: () => void;
  onChangeBadge?: () => void;
}

export default function ReminderDrawer({
  open,
  onClose,
  onGoMedicationManage,
  onGoOrderList,
  onChangeBadge,
}: Props) {
  const [meds, setMeds] = useState<MedicationItem[]>([]);
  const [appts, setAppts] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedOrderId, setExpandedOrderId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [m, a] = await Promise.all([
        api.get<any>('/api/medication-reminder/today').catch(() => []),
        api.get<any>('/api/medication-reminder/appointments').catch(() => []),
      ]);
      const medsArr = Array.isArray(m) ? m : (m as any)?.data ?? [];
      const apptArr = Array.isArray(a) ? a : (a as any)?.data ?? [];
      setMeds(medsArr as MedicationItem[]);
      setAppts(apptArr as AppointmentItem[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchAll();
      setExpandedOrderId(null);
    }
  }, [open, fetchAll]);

  const handleCheck = async (item: MedicationItem, idx: number) => {
    if (item.checked) {
      // 撤销
      const oldList = meds.slice();
      const next = meds.slice();
      next[idx] = { ...item, checked: false, checked_at: null, log_id: null };
      setMeds(next);
      try {
        if (item.log_id) await api.post('/api/medication-reminder/uncheck', { log_id: item.log_id });
        onChangeBadge?.();
      } catch {
        setMeds(oldList);
        showToast('取消失败，请重试');
      }
      return;
    }
    const oldList = meds.slice();
    const optimisticTime = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
    const next = meds.slice();
    next[idx] = { ...item, checked: true, checked_at: optimisticTime, log_id: -1 };
    setMeds(next);
    try {
      const res = await api.post<any>('/api/medication-reminder/check', {
        plan_id: item.plan_id,
        scheduled_time: item.scheduled_time,
      });
      const log_id = (res as any)?.log_id ?? (res as any)?.data?.log_id;
      const checked_at = (res as any)?.checked_at ?? (res as any)?.data?.checked_at ?? optimisticTime;
      const next2 = meds.slice();
      next2[idx] = { ...item, checked: true, checked_at, log_id: log_id ?? -1 };
      setMeds(next2);
      onChangeBadge?.();
    } catch {
      setMeds(oldList);
      showToast('打卡失败，请重试');
    }
  };

  const medUnchecked = meds.filter((m) => !m.checked).length;
  const apptCount = appts.length;

  if (!open) return null;

  return (
    <div
      data-testid="prd439-reminder-drawer"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 750,
          maxHeight: '80vh',
          background: '#fff',
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: '14px 16px 24px',
          overflowY: 'auto',
          color: '#1F2937',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>今日待办</h3>
          <button
            onClick={onClose}
            aria-label="关闭"
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: 20,
              color: '#6B7280',
              cursor: 'pointer',
              padding: 4,
            }}
          >
            ✕
          </button>
        </div>

        {/* ─── 用药提醒 ─── */}
        <SectionHeader
          title="用药提醒"
          badge={medUnchecked}
          onSetting={onGoMedicationManage}
          testid="prd439-section-medication"
        />
        {loading ? (
          <div style={{ color: '#9CA3AF', padding: '8px 0' }}>加载中…</div>
        ) : meds.length === 0 ? (
          <EmptyHint text="暂无用药提醒" />
        ) : (
          <div style={{ marginBottom: 16 }}>
            {meds.map((m, idx) => (
              <MedicationRow
                key={`${m.plan_id}-${m.scheduled_time}`}
                item={m}
                onClick={() => handleCheck(m, idx)}
              />
            ))}
          </div>
        )}

        {/* ─── 预约提醒 ─── */}
        <SectionHeader
          title="预约提醒"
          badge={apptCount}
          onSetting={onGoOrderList}
          testid="prd439-section-appointment"
        />
        {loading ? (
          <div style={{ color: '#9CA3AF', padding: '8px 0' }}>加载中…</div>
        ) : appts.length === 0 ? (
          <EmptyHint text="暂无预约提醒" />
        ) : (
          <div>
            {appts.map((a) => (
              <AppointmentRow
                key={a.order_id}
                item={a}
                expanded={expandedOrderId === a.order_id}
                onToggle={() =>
                  setExpandedOrderId(expandedOrderId === a.order_id ? null : a.order_id)
                }
              />
            ))}
          </div>
        )}

        {toast && (
          <div
            style={{
              position: 'fixed',
              bottom: 80,
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(0,0,0,0.75)',
              color: '#fff',
              padding: '8px 14px',
              borderRadius: 8,
              fontSize: 13,
              zIndex: 250,
            }}
          >
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}

function SectionHeader({
  title,
  badge,
  onSetting,
  testid,
}: {
  title: string;
  badge: number;
  onSetting?: () => void;
  testid?: string;
}) {
  return (
    <div
      data-testid={testid}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 0',
        borderBottom: '1px solid #F3F4F6',
        marginBottom: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
        {badge > 0 && (
          <span
            style={{
              marginLeft: 8,
              minWidth: 18,
              height: 18,
              padding: '0 5px',
              background: '#FF3B30',
              color: '#fff',
              borderRadius: 9999,
              fontSize: 11,
              fontWeight: 600,
              lineHeight: '18px',
              textAlign: 'center',
            }}
          >
            {badge > 9 ? '9+' : badge}
          </span>
        )}
      </div>
      {onSetting && (
        <button
          onClick={onSetting}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#3B82F6',
            fontSize: 13,
            cursor: 'pointer',
            padding: 4,
          }}
        >
          ⚙ 设置
        </button>
      )}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div style={{ color: '#9CA3AF', fontSize: 13, padding: '12px 0', textAlign: 'center' }}>
      {text}
    </div>
  );
}

function MedicationRow({ item, onClick }: { item: MedicationItem; onClick: () => void }) {
  const checked = item.checked;
  return (
    <div
      data-testid="prd439-med-row"
      data-checked={checked ? '1' : '0'}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '10px 4px',
        borderBottom: '1px solid #F9FAFB',
        opacity: checked ? 0.6 : 1,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: '#111827' }}>{item.drug_name}</div>
        <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
          {item.scheduled_time} · {item.dosage}
          {item.note ? ` · ${item.note}` : ''}
        </div>
      </div>
      <button
        onClick={onClick}
        style={{
          marginLeft: 8,
          padding: '6px 10px',
          borderRadius: 6,
          border: '1px solid ' + (checked ? '#D1D5DB' : '#10B981'),
          background: checked ? '#F3F4F6' : '#10B981',
          color: checked ? '#6B7280' : '#fff',
          fontSize: 12,
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        {checked ? `已服用 ${item.checked_at || ''}` : '✓ 已服用'}
      </button>
    </div>
  );
}

function AppointmentRow({
  item,
  expanded,
  onToggle,
}: {
  item: AppointmentItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      data-testid="prd439-appt-row"
      data-expanded={expanded ? '1' : '0'}
      style={{
        padding: '10px 4px',
        borderBottom: '1px solid #F9FAFB',
        cursor: 'pointer',
      }}
      onClick={onToggle}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{item.service_name}</div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
            {item.appointed_at || '未设预约时间'}
            {item.location ? ` · ${item.location}` : ''}
          </div>
        </div>
        <span
          style={{
            marginLeft: 8,
            padding: '3px 8px',
            borderRadius: 4,
            background: '#FFF7ED',
            color: '#EA580C',
            fontSize: 11,
            whiteSpace: 'nowrap',
          }}
        >
          {item.status_text}
        </span>
      </div>
      {expanded && (
        <div
          style={{
            marginTop: 10,
            padding: 10,
            background: '#F9FAFB',
            borderRadius: 6,
            fontSize: 12,
            color: '#374151',
            lineHeight: 1.6,
          }}
        >
          <div>订单号：{item.order_no || `#${item.order_id}`}</div>
          <div>服务：{item.service_name}</div>
          <div>预约时间：{item.appointed_at || '未设置'}</div>
          {item.location && <div>地点：{item.location}</div>}
          {item.verification_code && <div>核销码：{item.verification_code}</div>}
        </div>
      )}
    </div>
  );
}
