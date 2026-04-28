'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { NavBar, Toast, Button, Dialog, TextArea, Empty, DotLoading, Tag } from 'antd-mobile';
import { useRouter, useParams } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId, statusMap } from '../../mobile-lib';

interface OrderDetail {
  order_id: number;
  order_no: string;
  product_name: string;
  amount: number;
  status: string;
  created_at: string;
  user_display: string;
  appointment_time?: string;
  store_name?: string;
  is_appointment?: boolean;
}

interface OrderNote {
  id: number;
  content: string;
  created_at: string;
  staff_name?: string;
}

const STATUS_CONFIG: Record<string, { text: string; color: string; bg: string }> = {
  pending_payment: { text: '待支付', color: '#faad14', bg: '#fffbe6' },
  paid: { text: '待核销', color: '#1677ff', bg: '#e6f4ff' },
  pending: { text: '待确认', color: '#faad14', bg: '#fffbe6' },
  confirmed: { text: '已确认', color: '#1677ff', bg: '#e6f4ff' },
  redeemed: { text: '已核销', color: '#52c41a', bg: '#f6ffed' },
  completed: { text: '已完成', color: '#52c41a', bg: '#f6ffed' },
  cancelled: { text: '已取消', color: '#8c8c8c', bg: '#f5f5f5' },
  refunded: { text: '已退款', color: '#ff4d4f', bg: '#fff2f0' },
};

export default function OrderDetailMobilePage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params?.id as string;

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [notes, setNotes] = useState<OrderNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [noteText, setNoteText] = useState('');
  const [submittingNote, setSubmittingNote] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const loadOrder = useCallback(async () => {
    try {
      const params: any = {};
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      const res: any = await api.get(`/api/merchant/orders/${orderId}/detail`, { params });
      setOrder(res);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: '订单加载失败' });
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  const loadNotes = useCallback(async () => {
    try {
      const noteSid = getCurrentStoreId();
      const noteP: any = {};
      if (noteSid) noteP.store_id = noteSid;
      const res: any = await api.get(`/api/merchant/orders/${orderId}/notes`, { params: noteP });
      setNotes(res?.items || res || []);
    } catch {
      setNotes([]);
    }
  }, [orderId]);

  useEffect(() => {
    if (orderId) {
      loadOrder();
      loadNotes();
    }
  }, [orderId, loadOrder, loadNotes]);

  const handleConfirmOrder = async () => {
    setConfirming(true);
    try {
      const sid = getCurrentStoreId();
      const confirmParams: any = {};
      if (sid) confirmParams.store_id = sid;
      await api.post(`/api/merchant/orders/${orderId}/confirm`, null, { params: confirmParams });
      Toast.show({ icon: 'success', content: '已确认接单' });
      loadOrder();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '确认失败' });
    } finally {
      setConfirming(false);
    }
  };

  const handleAdjustTime = async () => {
    const dateStr = await new Promise<string | null>((resolve) => {
      let inputVal = order?.appointment_time?.split('T')[0] || '';
      Dialog.confirm({
        title: '调整预约日期',
        content: (
          <div style={{ padding: '12px 0' }}>
            <input
              type="date"
              defaultValue={inputVal}
              onChange={(e) => { inputVal = e.target.value; }}
              style={{ width: '100%', padding: 8, fontSize: 16, border: '1px solid #ddd', borderRadius: 6 }}
            />
          </div>
        ),
        onConfirm: () => resolve(inputVal),
        onCancel: () => resolve(null),
      });
    });
    if (!dateStr) return;

    const slotResult = await Dialog.show({
      title: '选择时段',
      closeOnAction: true,
      actions: [
        [
          { key: 'morning', text: '上午 (9:00-12:00)' },
          { key: 'afternoon', text: '下午 (13:00-17:00)' },
          { key: 'evening', text: '晚间 (18:00-21:00)' },
        ],
        [{ key: 'cancel', text: '取消' }],
      ],
    });

    const slot = slotResult as unknown as string;
    if (!slot || slot === 'cancel') return;

    const slotTimeMap: Record<string, string> = {
      morning: '09:00',
      afternoon: '13:00',
      evening: '18:00',
    };

    try {
      const adjustSid = getCurrentStoreId();
      const adjustParams: any = {};
      if (adjustSid) adjustParams.store_id = adjustSid;
      await api.put(`/api/merchant/orders/${orderId}/appointment-time`, {
        new_date: dateStr,
        new_time_slot: slotTimeMap[slot] || '09:00',
      }, { params: adjustParams });
      Toast.show({ icon: 'success', content: '预约时间已调整' });
      loadOrder();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '调整失败' });
    }
  };

  const handleSubmitNote = async () => {
    if (!noteText.trim()) {
      Toast.show({ content: '请输入备注内容' });
      return;
    }
    setSubmittingNote(true);
    try {
      const noteSid = getCurrentStoreId();
      const noteParams: any = {};
      if (noteSid) noteParams.store_id = noteSid;
      await api.post(`/api/merchant/orders/${orderId}/notes`, { content: noteText.trim() }, { params: noteParams });
      Toast.show({ icon: 'success', content: '备注已添加' });
      setNoteText('');
      loadNotes();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '添加备注失败' });
    } finally {
      setSubmittingNote(false);
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
        <NavBar onBack={() => router.back()}>订单详情</NavBar>
        <div style={{ textAlign: 'center', padding: 64 }}><DotLoading color="primary" /></div>
      </div>
    );
  }

  if (!order) {
    return (
      <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
        <NavBar onBack={() => router.back()}>订单详情</NavBar>
        <Empty description="订单不存在" style={{ padding: 64 }} />
      </div>
    );
  }

  const st = STATUS_CONFIG[order.status] || { text: order.status, color: '#999', bg: '#f5f5f5' };
  const canConfirm = order.is_appointment && ['pending', 'paid'].includes(order.status);
  const canAdjustTime = order.is_appointment && !['cancelled', 'refunded', 'completed'].includes(order.status);

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: 24 }}>
      <NavBar onBack={() => router.back()}>订单详情</NavBar>

      {/* Order info card */}
      <div style={{ margin: 12, background: '#fff', borderRadius: 12, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div style={{ flex: 1, marginRight: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{order.product_name || '—'}</div>
            <div style={{ fontSize: 12, color: '#999' }}>订单号: {order.order_no}</div>
          </div>
          <span style={{
            fontSize: 12, padding: '3px 10px', borderRadius: 12,
            background: st.bg, color: st.color,
          }}>
            {st.text}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px', fontSize: 13, color: '#666' }}>
          <div>客户: <span style={{ color: '#333' }}>{order.user_display || '—'}</span></div>
          <div>金额: <span style={{ color: '#fa541c', fontWeight: 600 }}>¥{order.amount}</span></div>
          <div>门店: <span style={{ color: '#333' }}>{order.store_name || '—'}</span></div>
          <div>下单: <span style={{ color: '#333' }}>{order.created_at ? new Date(order.created_at).toLocaleString('zh-CN') : '—'}</span></div>
          {order.appointment_time && (
            <div style={{ gridColumn: '1 / -1' }}>
              预约时间: <span style={{ color: '#1677ff', fontWeight: 500 }}>{new Date(order.appointment_time).toLocaleString('zh-CN')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      {(canConfirm || canAdjustTime) && (
        <div style={{ margin: '0 12px 12px', display: 'flex', gap: 10 }}>
          {canConfirm && (
            <Button
              color="primary"
              fill="solid"
              style={{ flex: 1 }}
              loading={confirming}
              onClick={handleConfirmOrder}
            >
              确认接单
            </Button>
          )}
          {canAdjustTime && (
            <Button
              color="primary"
              fill="outline"
              style={{ flex: 1 }}
              onClick={handleAdjustTime}
            >
              调整预约时间
            </Button>
          )}
        </div>
      )}

      {/* Store notes */}
      <div style={{ margin: '0 12px 12px', background: '#fff', borderRadius: 12, padding: 16 }}>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>门店备注</div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <TextArea
            placeholder="输入备注内容..."
            value={noteText}
            onChange={setNoteText}
            rows={2}
            style={{ flex: 1, '--font-size': '14px' } as any}
          />
          <Button
            color="primary"
            size="small"
            style={{ alignSelf: 'flex-end', height: 36 }}
            loading={submittingNote}
            onClick={handleSubmitNote}
          >
            提交
          </Button>
        </div>

        {notes.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#999', fontSize: 13, padding: '12px 0' }}>暂无备注</div>
        ) : (
          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
            {notes.map((n) => (
              <div key={n.id} style={{ padding: '10px 0', borderTop: '1px solid #f0f0f0' }}>
                <div style={{ fontSize: 13, color: '#333', lineHeight: 1.5 }}>{n.content}</div>
                <div style={{ fontSize: 11, color: '#999', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
                  <span>{n.staff_name || ''}</span>
                  <span>{n.created_at ? new Date(n.created_at).toLocaleString('zh-CN') : ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
