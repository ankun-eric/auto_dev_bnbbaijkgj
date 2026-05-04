'use client';

/**
 * 预约日历「当日订单」底部抽屉（H5 移动端） — PRD「当日订单弹窗」v1.0
 *
 * 触发：H5 日历点击订单数 ≥ 1 的日期单元格
 * 形态：底部抽屉（最高 85vh，可上下滚动）
 *   - 顶部：拖动条 + 日期标题 + ✕ 关闭
 *   - Tab：固定在抽屉顶部，横向滚动；列表在 Tab 下方独立滚动
 *   - 卡片：时段 / 状态徽标 / 客户 / 服务项目 / 服务地点 / 操作按钮
 *   - 卡片就地展开详情（与 PC 相同字段）
 *   - 关闭：✕ + 下拉关闭手势
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { Toast, DotLoading, Empty } from 'antd-mobile';
import api from '@/lib/api';

export type DailyOrderStatus = 'pending' | 'verified' | 'cancelled' | 'refunded' | 'other';

export interface DailyOrder {
  order_id: number;
  order_item_id: number;
  order_no?: string;
  time_slot?: string;
  appointment_time?: string;
  customer_nickname?: string;
  customer_phone?: string;
  service_name?: string;
  service_location?: string;
  status: DailyOrderStatus;
  remark?: string;
  verify_time?: string;
  verify_code?: string;
  cancel_time?: string;
  cancel_reason?: string;
  refund_time?: string;
  refund_reason?: string;
}

interface DailyOrdersResponseData {
  date: string;
  total: number;
  by_status: { pending: number; verified: number; cancelled: number; refunded: number };
  orders: DailyOrder[];
}

const STATUS_TAG: Record<DailyOrderStatus, { text: string; color: string; bg: string }> = {
  pending: { text: '待核销', color: '#fa8c16', bg: '#fff7e6' },
  verified: { text: '已核销', color: '#52c41a', bg: '#f6ffed' },
  cancelled: { text: '已取消', color: '#ff4d4f', bg: '#fff1f0' },
  refunded: { text: '已退款', color: '#c41d7f', bg: '#fff0f6' },
  other: { text: '其它', color: '#8c8c8c', bg: '#f5f5f5' },
};

const WEEKDAY_CN = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

function formatDateTitle(date: string | null, total: number): string {
  if (!date) return '当日订单';
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!m) return `${date} · 共 ${total} 单`;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return `${m[1]}年${Number(m[2])}月${Number(m[3])}日 ${WEEKDAY_CN[d.getDay()]} · 共 ${total} 单`;
}

function formatDateTimeStr(s?: string | null): string {
  if (!s) return '—';
  // 简单格式化 ISO 字符串
  try {
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return s;
  }
}

function formatPhone(p?: string): string {
  if (!p) return '—';
  const digits = p.replace(/\D/g, '');
  if (digits.length === 11) return `${digits.slice(0, 3)} ${digits.slice(3, 7)} ${digits.slice(7)}`;
  return p;
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

interface DailyOrdersDrawerProps {
  open: boolean;
  date: string | null;
  storeId?: number | null;
  onClose: () => void;
  onViewFullOrder?: (orderId: number) => void;
}

export default function DailyOrdersDrawer({ open, date, storeId, onClose, onViewFullOrder }: DailyOrdersDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DailyOrdersResponseData | null>(null);
  const [activeTab, setActiveTab] = useState<DailyOrderStatus | 'all'>('all');
  const [expandedKey, setExpandedKey] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    if (!open || !date) return;
    setLoading(true);
    try {
      const params: Record<string, unknown> = { date };
      if (storeId) params.store_id = storeId;
      const res = await api.get('/api/merchant/calendar/daily-orders', { params });
      const payload = (res?.data ?? res) as DailyOrdersResponseData;
      setData(payload);
    } catch {
      setData(null);
      Toast.show({ icon: 'fail', content: '加载失败' });
    } finally {
      setLoading(false);
    }
  }, [open, date, storeId]);

  useEffect(() => {
    if (open) {
      setActiveTab('all');
      setExpandedKey(null);
      loadData();
    } else {
      setData(null);
      setExpandedKey(null);
    }
  }, [open, loadData]);

  // 锁定 body 滚动（避免抽屉滚动穿透）
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const filteredOrders = useMemo(() => {
    if (!data) return [];
    if (activeTab === 'all') return data.orders;
    return data.orders.filter((o) => o.status === activeTab);
  }, [data, activeTab]);

  const total = data?.total ?? 0;
  const counts = data?.by_status ?? { pending: 0, verified: 0, cancelled: 0, refunded: 0 };

  const handlePhoneCall = (phone?: string, orderNo?: string) => {
    if (!phone) return;
    try {
      // eslint-disable-next-line no-console
      console.info('[track] calendar_daily_phone_call', { order_no: orderNo, terminal: 'h5' });
    } catch {}
    const digits = phone.replace(/\D/g, '');
    window.location.href = `tel:${digits}`;
  };

  const handleCopyPhone = async (phone?: string, orderNo?: string) => {
    if (!phone) return;
    const ok = await copyToClipboard(phone.replace(/\D/g, ''));
    if (ok) {
      Toast.show({ icon: 'success', content: '已复制到剪贴板' });
      try {
        // eslint-disable-next-line no-console
        console.info('[track] calendar_daily_phone_copy', { order_no: orderNo, terminal: 'h5' });
      } catch {}
    } else {
      Toast.show({ icon: 'fail', content: '复制失败，请手动选取' });
    }
  };

  const handleExpandToggle = (orderItemId: number) => {
    setExpandedKey((cur) => (cur === orderItemId ? null : orderItemId));
  };

  if (!open) return null;

  const tabItems: { key: DailyOrderStatus | 'all'; label: string }[] = [
    { key: 'all', label: `全部(${total})` },
    { key: 'pending', label: `待核销(${counts.pending})` },
    { key: 'verified', label: `已核销(${counts.verified})` },
    { key: 'cancelled', label: `已取消(${counts.cancelled})` },
    { key: 'refunded', label: `已退款(${counts.refunded})` },
  ];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1100,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
      }}
    >
      {/* 遮罩 */}
      <div
        onClick={onClose}
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 0 }}
      />

      {/* 抽屉主体 */}
      <div
        role="dialog"
        aria-label="当日订单"
        style={{
          position: 'relative',
          zIndex: 1,
          background: '#f7f8fa',
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 -4px 16px rgba(0,0,0,0.1)',
        }}
      >
        {/* 拖动条 */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0 4px' }}>
          <div style={{ width: 36, height: 4, borderRadius: 2, background: '#d9d9d9' }} />
        </div>

        {/* 标题栏 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 16px 10px',
            borderBottom: '1px solid #f0f0f0',
            background: '#fff',
          }}
        >
          <span style={{ fontSize: 15, fontWeight: 600, color: '#1f1f1f' }}>{formatDateTitle(date, total)}</span>
          <span
            onClick={onClose}
            style={{ fontSize: 22, color: '#8c8c8c', cursor: 'pointer', padding: '0 4px' }}
            aria-label="关闭"
          >
            ✕
          </span>
        </div>

        {/* Tab 区（固定） */}
        <div
          style={{
            display: 'flex',
            gap: 6,
            overflowX: 'auto',
            padding: '10px 12px',
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
            WebkitOverflowScrolling: 'touch',
          }}
        >
          {tabItems.map((t) => {
            const active = t.key === activeTab;
            return (
              <span
                key={t.key}
                onClick={() => {
                  setActiveTab(t.key);
                  setExpandedKey(null);
                }}
                style={{
                  flex: '0 0 auto',
                  padding: '6px 14px',
                  borderRadius: 16,
                  fontSize: 13,
                  background: active ? '#52c41a' : '#f5f5f5',
                  color: active ? '#fff' : '#595959',
                  fontWeight: active ? 600 : 400,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {t.label}
              </span>
            );
          })}
        </div>

        {/* 列表区（独立滚动） */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, WebkitOverflowScrolling: 'touch' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 32, color: '#999' }}>
              <DotLoading color="primary" />
            </div>
          ) : filteredOrders.length === 0 ? (
            <Empty description="该状态下暂无记录" style={{ padding: 32 }} />
          ) : (
            filteredOrders.map((order) => {
              const cfg = STATUS_TAG[order.status] || STATUS_TAG.other;
              const expanded = expandedKey === order.order_item_id;
              const isVerified = order.status === 'verified';
              const isCancelled = order.status === 'cancelled';
              const isRefunded = order.status === 'refunded';

              return (
                <div
                  key={order.order_item_id}
                  style={{
                    background: '#fff',
                    borderRadius: 10,
                    padding: '12px 14px',
                    marginBottom: 10,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                  }}
                >
                  <div
                    onClick={() => handleExpandToggle(order.order_item_id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 6,
                      }}
                    >
                      <span style={{ fontSize: 14, fontWeight: 600, color: '#1f1f1f' }}>
                        {order.time_slot || '—'}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 10,
                          background: cfg.bg,
                          color: cfg.color,
                          fontWeight: 500,
                        }}
                      >
                        {cfg.text}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 13,
                        color: '#595959',
                        marginBottom: 4,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {order.customer_nickname || '—'} · {order.service_name || '—'}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: '#8c8c8c',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      📍 {order.service_location || '—'}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: '#52c41a',
                        marginTop: 6,
                        textAlign: 'right',
                      }}
                    >
                      {expanded ? '收起 ▲' : '展开详情 ▼'}
                    </div>
                  </div>

                  {expanded && (
                    <div
                      style={{
                        marginTop: 10,
                        padding: 12,
                        background: '#fafbfc',
                        borderRadius: 8,
                        border: '1px solid #f0f0f0',
                      }}
                    >
                      <DetailLine label="客户备注" value={order.remark || '—'} />
                      <DetailLine label="服务地点" value={order.service_location || '—'} />
                      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                        <span style={{ fontSize: 13, color: '#8c8c8c', minWidth: 70 }}>客户手机号</span>
                        <span style={{ fontSize: 13, fontFamily: 'Menlo, Consolas, monospace', color: '#1f1f1f' }}>
                          {formatPhone(order.customer_phone)}
                        </span>
                        <button
                          onClick={() => handlePhoneCall(order.customer_phone, order.order_no)}
                          disabled={!order.customer_phone}
                          style={btnStyle(false, '#52c41a')}
                        >
                          📞 拨打
                        </button>
                        <button
                          onClick={() => handleCopyPhone(order.customer_phone, order.order_no)}
                          disabled={!order.customer_phone}
                          style={btnStyle(false, '#1677ff')}
                        >
                          📋 复制
                        </button>
                      </div>
                      <DetailLine label="核销状态" value={cfg.text} valueColor={cfg.color} />
                      <DetailLine label="核销时间" value={isVerified ? formatDateTimeStr(order.verify_time) : '—'} />
                      <DetailLine
                        label="核销码"
                        value={isVerified ? (order.verify_code || '—') : '—'}
                        mono={isVerified}
                      />
                      {isCancelled && (
                        <>
                          <DetailLine label="取消时间" value={formatDateTimeStr(order.cancel_time)} />
                          {order.cancel_reason && <DetailLine label="取消原因" value={order.cancel_reason} />}
                        </>
                      )}
                      {isRefunded && (
                        <>
                          <DetailLine label="退款时间" value={formatDateTimeStr(order.refund_time)} />
                          {order.refund_reason && <DetailLine label="退款原因" value={order.refund_reason} />}
                        </>
                      )}
                      <button
                        onClick={() => {
                          try {
                            // eslint-disable-next-line no-console
                            console.info('[track] calendar_daily_view_full_order', { order_no: order.order_no, terminal: 'h5' });
                          } catch {}
                          if (onViewFullOrder) onViewFullOrder(order.order_id);
                        }}
                        style={{
                          width: '100%',
                          marginTop: 10,
                          padding: '10px 0',
                          background: '#52c41a',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 8,
                          fontSize: 14,
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        查看完整订单
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

function DetailLine({ label, value, valueColor, mono }: { label: string; value: string; valueColor?: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 8, fontSize: 13 }}>
      <span style={{ color: '#8c8c8c', minWidth: 70, flex: '0 0 70px' }}>{label}</span>
      <span
        style={{
          color: valueColor || '#1f1f1f',
          flex: 1,
          wordBreak: 'break-all',
          fontFamily: mono ? 'Menlo, Consolas, monospace' : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}

function btnStyle(disabled: boolean, color: string): React.CSSProperties {
  return {
    fontSize: 12,
    padding: '4px 10px',
    border: `1px solid ${disabled ? '#d9d9d9' : color}`,
    borderRadius: 14,
    background: '#fff',
    color: disabled ? '#bfbfbf' : color,
    cursor: disabled ? 'not-allowed' : 'pointer',
  };
}
