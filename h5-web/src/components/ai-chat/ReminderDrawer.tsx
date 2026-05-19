'use client';

/**
 * [PRD-BELL-UNIFIED-V1 2026-05-19] 铃铛红点统一计数抽屉
 *
 * 底部弹出抽屉，自适应高度（最高 80vh），两个区块：
 *   - 💊 用药提醒：今天计划要吃但未点"已服用"的条目（按"次"算）
 *   - 🛒 待处理订单：pending_payment / pending_appointment / appointed /
 *                   pending_use / partial_used / pending_receipt（6 状态合并）
 *
 * 交互：
 *   - 用药条目：点击右侧"✓ 已服用"按钮触发打卡（不支持撤销，与今日用药一致）；
 *     已过点未服用条目显示 ⚠ 已超时 标签
 *   - 订单条目：点击就地展开详情（手风琴，同时只展开一条）；主操作按钮按状态文案；
 *     展开后包含订单号/商品名/规格/金额/下单时间/门店等共用字段 + 类型差异化字段
 *   - 处理完毕的条目置灰，折叠到「已完成 (N) ▼」分组里默认折叠
 *
 * 兼容 PRD-439 旧调用方：保留旧 props（onGoMedicationManage / onGoOrderList / onChangeBadge / consultantId）。
 */

import { useEffect, useMemo, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { publishBellEvent } from '@/lib/bell-event-bus';

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
  // 扩展字段（PRD-BELL-UNIFIED-V1）
  status?: string | null;
  amount?: string | null;
  quantity?: number | null;
  spec?: string | null;
  created_at?: string | null;
  remaining_redeem_count?: number | null;
  total_redeem_count?: number | null;
  tracking_company?: string | null;
  tracking_number?: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onGoMedicationManage?: () => void;
  onGoOrderList?: () => void;
  onChangeBadge?: () => void;
  /** [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F11] 按咨询人 ID 筛选用药提醒，订单不参与筛选 */
  consultantId?: number | null;
}

// 6 个订单状态合并集
const ORDER_STATUSES_PARAM =
  'pending_payment,pending_appointment,appointed,pending_use,partial_used,pending_receipt';

// 状态码 → 主操作按钮文案
const ORDER_ACTION_TEXT: Record<string, string> = {
  pending_payment: '去支付',
  pending_appointment: '去预约',
  appointed: '查看核销码',
  pending_use: '查看核销码',
  partial_used: '继续预约',
  pending_receipt: '确认收货',
};

function nowHHMM(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function ReminderDrawer({
  open,
  onClose,
  onGoMedicationManage,
  onGoOrderList,
  onChangeBadge,
  consultantId,
}: Props) {
  const router = useRouter();
  const [meds, setMeds] = useState<MedicationItem[]>([]);
  const [appts, setAppts] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [expandedOrderId, setExpandedOrderId] = useState<number | null>(null);
  const [doneGroupOpen, setDoneGroupOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const medUrl =
        consultantId != null && consultantId > 0
          ? `/api/medication-reminder/today?consultant_id=${encodeURIComponent(consultantId)}`
          : '/api/medication-reminder/today';
      const apptUrl = `/api/medication-reminder/appointments?status_in=${encodeURIComponent(
        ORDER_STATUSES_PARAM,
      )}`;
      const [m, a] = await Promise.all([
        api.get<any>(medUrl),
        api.get<any>(apptUrl),
      ]);
      const medsArr = Array.isArray(m) ? m : (m as any)?.data ?? [];
      const apptArr = Array.isArray(a) ? a : (a as any)?.data ?? [];
      setMeds(medsArr as MedicationItem[]);
      setAppts(apptArr as AppointmentItem[]);
    } catch {
      setLoadError(true);
      setMeds([]);
      setAppts([]);
    } finally {
      setLoading(false);
    }
  }, [consultantId]);

  useEffect(() => {
    if (open) {
      fetchAll();
      setExpandedOrderId(null);
      setDoneGroupOpen(false);
    }
  }, [open, fetchAll]);

  const handleCheck = async (item: MedicationItem, idx: number) => {
    // PRD §3.5：已打卡条目不支持撤销
    if (item.checked) return;
    const oldList = meds.slice();
    const optimisticTime = nowHHMM();
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
      publishBellEvent('medication:checked', { plan_id: item.plan_id });
    } catch {
      setMeds(oldList);
      showToast('打卡失败，请重试');
    }
  };

  // 拆分：未完成 / 已完成
  const pendingMeds = useMemo(() => meds.filter((m) => !m.checked), [meds]);
  const doneMeds = useMemo(() => meds.filter((m) => m.checked), [meds]);

  const isOrderDone = (s?: string | null) => false; // 抽屉里只展示 6 个 active 状态，订单不会出现"已完成"

  const doneCount = doneMeds.length;

  const medCount = pendingMeds.length;
  const orderCount = appts.length;
  const totalCount = medCount + orderCount;

  // 跳转链接：用药"查看全部"→ 健康档案-今日用药；订单"查看全部"→ 订单列表
  const goMedAll = () => {
    if (onGoMedicationManage) {
      onGoMedicationManage();
    } else {
      try {
        router.push('/ai-home/medication-reminder');
      } catch {}
    }
  };
  const goOrderAll = () => {
    if (onGoOrderList) {
      onGoOrderList();
    } else {
      try {
        router.push('/unified-orders');
      } catch {}
    }
  };

  const handleOrderAction = (a: AppointmentItem) => {
    const s = (a.status || '').toLowerCase();
    // PRD §3.6.4：核销码就地展开（已实现）；待支付/待预约/确认收货 一期可降级为关抽屉跳转
    if (s === 'appointed' || s === 'pending_use' || s === 'partial_used') {
      // 已显示在展开区，直接确保展开
      setExpandedOrderId(a.order_id);
      return;
    }
    // 其他状态：关抽屉跳订单详情，让用户在原页完成支付/预约/收货
    try {
      onClose();
      router.push(`/unified-order/${a.order_id}`);
    } catch {}
  };

  if (!open) return null;

  return (
    <div
      data-testid="bell-unified-drawer"
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
        {/* 顶部标题栏：待办事项 (N) + 关闭按钮 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <h3 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
            待办事项{totalCount > 0 && <span style={{ color: '#6B7280', fontWeight: 500 }}> ({totalCount})</span>}
          </h3>
          <button
            data-testid="bell-drawer-close"
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

        {/* 加载失败兜底 */}
        {loadError && (
          <div
            data-testid="bell-drawer-error"
            onClick={fetchAll}
            style={{
              padding: '24px 0',
              textAlign: 'center',
              color: '#EF4444',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            加载失败，点击重试
          </div>
        )}

        {/* 两区块都为空：空状态 */}
        {!loadError && !loading && totalCount === 0 && doneCount === 0 && (
          <div
            data-testid="bell-drawer-empty"
            style={{ padding: '40px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}
          >
            <div style={{ fontSize: 40, marginBottom: 8 }}>✨</div>
            暂无待办事项，一切都很顺利
          </div>
        )}

        {!loadError && (totalCount > 0 || doneCount > 0 || loading) && (
          <>
            {/* ─── 区块 1：💊 用药提醒 ─── */}
            <SectionHeader
              icon="💊"
              title="用药提醒"
              count={medCount}
              actionText="查看全部 →"
              onAction={goMedAll}
              testid="bell-section-medication"
            />
            {loading ? (
              <div style={{ color: '#9CA3AF', padding: '8px 4px' }}>加载中…</div>
            ) : pendingMeds.length === 0 ? (
              <div
                style={{ color: '#10B981', padding: '8px 4px 16px', fontSize: 13 }}
                data-testid="bell-section-medication-empty"
              >
                今日用药已全部完成 ✅
              </div>
            ) : (
              <div style={{ marginBottom: 16 }}>
                {pendingMeds.map((m) => {
                  const idx = meds.findIndex(
                    (x) => x.plan_id === m.plan_id && x.scheduled_time === m.scheduled_time,
                  );
                  return (
                    <MedicationRow
                      key={`${m.plan_id}-${m.scheduled_time}`}
                      item={m}
                      overdue={!!m.scheduled_time && m.scheduled_time < nowHHMM()}
                      onClick={() => handleCheck(m, idx)}
                    />
                  );
                })}
              </div>
            )}

            {/* ─── 区块 2：🛒 待处理订单 ─── */}
            <SectionHeader
              icon="🛒"
              title="待处理订单"
              count={orderCount}
              actionText="查看全部 →"
              onAction={goOrderAll}
              testid="bell-section-order"
            />
            {loading ? (
              <div style={{ color: '#9CA3AF', padding: '8px 4px' }}>加载中…</div>
            ) : appts.length === 0 ? (
              <div
                style={{ color: '#9CA3AF', padding: '8px 4px 16px', fontSize: 13 }}
                data-testid="bell-section-order-empty"
              >
                暂无待处理订单
              </div>
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
                    onAction={() => handleOrderAction(a)}
                  />
                ))}
              </div>
            )}

            {/* ─── 已完成折叠分组 ─── */}
            {doneCount > 0 && (
              <div style={{ marginTop: 16 }} data-testid="bell-done-group">
                <button
                  onClick={() => setDoneGroupOpen((v) => !v)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: 'transparent',
                    border: 'none',
                    padding: '8px 0',
                    color: '#6B7280',
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  已完成 ({doneCount}) {doneGroupOpen ? '▲' : '▼'}
                </button>
                {doneGroupOpen && (
                  <div>
                    {doneMeds.map((m) => (
                      <MedicationRow
                        key={`done-${m.plan_id}-${m.scheduled_time}`}
                        item={m}
                        overdue={false}
                        onClick={() => {}}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
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
  icon,
  title,
  count,
  actionText,
  onAction,
  testid,
}: {
  icon: string;
  title: string;
  count: number;
  actionText: string;
  onAction: () => void;
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
        <span style={{ fontSize: 16, marginRight: 6 }}>{icon}</span>
        <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
        <span style={{ marginLeft: 6, color: '#6B7280', fontSize: 13 }}>({count})</span>
      </div>
      <button
        onClick={onAction}
        style={{
          background: 'transparent',
          border: 'none',
          color: '#3B82F6',
          fontSize: 13,
          cursor: 'pointer',
          padding: 4,
        }}
      >
        {actionText}
      </button>
    </div>
  );
}

function MedicationRow({
  item,
  overdue,
  onClick,
}: {
  item: MedicationItem;
  overdue: boolean;
  onClick: () => void;
}) {
  const checked = item.checked;
  return (
    <div
      data-testid="bell-med-row"
      data-checked={checked ? '1' : '0'}
      data-overdue={overdue ? '1' : '0'}
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
        <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
          <span>{item.scheduled_time}</span>
          <span>·</span>
          <span>{item.dosage}</span>
          {item.note ? (
            <>
              <span>·</span>
              <span>{item.note}</span>
            </>
          ) : null}
          {overdue && !checked && (
            <span
              style={{
                marginLeft: 4,
                padding: '1px 6px',
                background: '#FEF3C7',
                color: '#B45309',
                borderRadius: 4,
                fontSize: 11,
              }}
            >
              ⚠ 已超时
            </span>
          )}
        </div>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (!checked) onClick();
        }}
        disabled={checked}
        style={{
          marginLeft: 8,
          padding: '6px 10px',
          borderRadius: 6,
          border: '1px solid ' + (checked ? '#D1D5DB' : '#10B981'),
          background: checked ? '#F3F4F6' : '#10B981',
          color: checked ? '#6B7280' : '#fff',
          fontSize: 12,
          cursor: checked ? 'default' : 'pointer',
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
  onAction,
}: {
  item: AppointmentItem;
  expanded: boolean;
  onToggle: () => void;
  onAction: () => void;
}) {
  const status = (item.status || '').toLowerCase();
  const actionText = ORDER_ACTION_TEXT[status] || '查看详情';
  const statusBg = status === 'pending_payment' ? '#FEF3C7' : '#FFF7ED';
  const statusFg = status === 'pending_payment' ? '#B45309' : '#EA580C';
  const isAppointed = status === 'appointed' || status === 'pending_use' || status === 'partial_used';
  return (
    <div
      data-testid="bell-appt-row"
      data-status={status}
      data-expanded={expanded ? '1' : '0'}
      style={{
        padding: '10px 4px',
        borderBottom: '1px solid #F9FAFB',
      }}
    >
      <div
        style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
        onClick={onToggle}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{item.service_name}</div>
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <span
              style={{
                padding: '1px 6px',
                background: statusBg,
                color: statusFg,
                borderRadius: 4,
                fontSize: 11,
              }}
            >
              {item.status_text}
            </span>
            {item.amount && <span>¥{item.amount}</span>}
            {status === 'pending_appointment' && (
              <span style={{ color: '#EA580C' }}>⏰ 待您选时间</span>
            )}
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAction();
          }}
          data-testid="bell-appt-action"
          style={{
            marginLeft: 8,
            padding: '6px 10px',
            borderRadius: 6,
            border: '1px solid #3B82F6',
            background: '#3B82F6',
            color: '#fff',
            fontSize: 12,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {actionText}
        </button>
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
            lineHeight: 1.7,
          }}
        >
          <div>订单号：{item.order_no || `#${item.order_id}`}</div>
          <div>商品/服务：{item.service_name}</div>
          {item.spec && <div>规格：{item.spec}</div>}
          {typeof item.quantity === 'number' && <div>数量：{item.quantity}</div>}
          {item.amount && <div>金额：¥{item.amount}</div>}
          {item.created_at && <div>下单时间：{item.created_at}</div>}
          {item.location && <div>门店/地点：{item.location}</div>}

          {/* 状态差异化 */}
          {isAppointed && item.appointed_at && <div>预约时间：{item.appointed_at}</div>}
          {isAppointed && item.verification_code && (
            <div data-testid="bell-verify-code">
              核销码：<span style={{ fontWeight: 600, color: '#111827' }}>{item.verification_code}</span>
              <span style={{ marginLeft: 6, color: '#9CA3AF' }}>（到店出示）</span>
            </div>
          )}
          {status === 'partial_used' && (
            <div>
              剩余次数：
              {typeof item.remaining_redeem_count === 'number'
                ? `${item.remaining_redeem_count} / ${item.total_redeem_count ?? '-'}`
                : '—'}
            </div>
          )}
          {status === 'pending_receipt' && (item.tracking_company || item.tracking_number) && (
            <div>
              物流：{item.tracking_company || ''} {item.tracking_number || ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
