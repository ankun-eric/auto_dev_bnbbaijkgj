'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { NavBar, Toast, Button, Dialog, TextArea, Empty, DotLoading, Tag, Popup, DatePicker, Selector } from 'antd-mobile';
import { useRouter, useParams } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId, statusMap } from '../../mobile-lib';
import { parseServerTime, formatDateTime } from '@/lib/datetime';
// [BUG-FIX-MERCHANT-RESCHEDULE-V1 2026-05-07] 商家 H5 端「调整预约时间」抽屉化改造
// 复用客户端服务器时间工具，按服务器时间过滤已过去的整段时段
import {
  initServerTime,
  getServerNow,
  isSameDayAsServer,
  filterPastSlots,
  isServerTimeUnreliable,
} from '@/lib/server-time';

// [BUG-FIX-MERCHANT-RESCHEDULE-V1] 改期固定 9 段时段（来自 PRD-01 §2.3，与客户端 RESCHEDULE_TIME_SLOTS_9 完全一致）
const RESCHEDULE_TIME_SLOTS_9 = [
  '06:00-08:00', '08:00-10:00', '10:00-12:00',
  '12:00-14:00', '14:00-16:00', '16:00-18:00',
  '18:00-20:00', '20:00-22:00', '22:00-24:00',
];

// [PRD-04 §F-04-5 / §2.7] 改期通知状态
interface RescheduleNotifyChannel {
  name: string;
  ok: boolean;
  detail?: string;
}
interface RescheduleNotifyDetail {
  status: 'none' | 'ok' | 'all_failed';
  display: string;
  channels: RescheduleNotifyChannel[];
  created_at?: string | null;
  wechat_work_alert?: { ok: boolean; detail: string } | null;
}

interface OrderDetail {
  order_id: number;
  order_no: string;
  product_name: string;
  product_id?: number;
  amount: number;
  status: string;
  created_at: string;
  user_display: string;
  appointment_time?: string;
  // [BUGFIX-UO-20260507-001] 预约时段相关字段
  appointment_date?: string;
  time_slot?: string;
  store_name?: string;
  is_appointment?: boolean;
  // [BUG-FIX-MERCHANT-RESCHEDULE-V1] 商品预约模式：none / date / time_slot / custom_form
  appointment_mode?: 'none' | 'date' | 'time_slot' | 'custom_form' | null;
  // [BUGFIX-UO-20260507-001] 支付方式相关字段
  payment_method?: string;
  payment_method_text?: string;
  payment_channel_code?: string;
  payment_display_name?: string;
  // [PRD-04] 改期通知状态（none / ok / all_failed）
  last_reschedule_notify_status?: 'none' | 'ok' | 'all_failed';
  last_reschedule_notify?: RescheduleNotifyDetail | null;
}

interface OrderNote {
  id: number;
  content: string;
  created_at: string;
  staff_name?: string;
}

// PRD「商家 PC 后台优化 v1.1」F1+F2：补齐 14 态映射 + 文案对齐用户端
const STATUS_CONFIG: Record<string, { text: string; color: string; bg: string }> = {
  pending_payment: { text: '待付款', color: '#fa8c16', bg: '#fff7e6' },
  pending_shipment: { text: '待发货', color: '#1890ff', bg: '#e6f4ff' },
  pending_receipt: { text: '待收货', color: '#38BDF8', bg: '#e6fffb' },
  pending_appointment: { text: '待预约', color: '#722ed1', bg: '#f9f0ff' },
  appointed: { text: '待核销', color: '#38BDF8', bg: '#e6fffb' },
  pending_use: { text: '待核销', color: '#38BDF8', bg: '#e6fffb' },
  partial_used: { text: '部分核销', color: '#faad14', bg: '#fffbe6' },
  pending_review: { text: '待评价', color: '#eb2f96', bg: '#fff0f6' },
  completed: { text: '已完成', color: '#0EA5E9', bg: '#F0F9FF' },
  expired: { text: '已过期', color: '#8c8c8c', bg: '#f5f5f5' },
  refunding: { text: '退款中', color: '#f5222d', bg: '#fff1f0' },
  refunded: { text: '已退款', color: '#8c8c8c', bg: '#f5f5f5' },
  cancelled: { text: '已取消', color: '#8c8c8c', bg: '#f5f5f5' },
  // 历史遗留兼容（防御性映射，不在筛选器中暴露）
  redeemed: { text: '已完成', color: '#0EA5E9', bg: '#F0F9FF' },
  paid: { text: '待核销', color: '#1677ff', bg: '#e6f4ff' },
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

  // [BUG-FIX-MERCHANT-RESCHEDULE-V1] 调整预约时间抽屉相关状态
  const [showApptPopup, setShowApptPopup] = useState(false);
  const [showApptDatePicker, setShowApptDatePicker] = useState(false);
  const [apptDate, setApptDate] = useState<Date | null>(null);
  const [apptSlot, setApptSlot] = useState<string>('');
  const [apptSubmitting, setApptSubmitting] = useState(false);

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

  // [BUG-FIX-MERCHANT-RESCHEDULE-V1 2026-05-07] 商家 H5 端「调整预约时间」抽屉化改造
  // 与客户端「改约」抽屉完全对齐：
  //  - 按订单对应商品 appointment_mode 分支：date 模式仅日期；time_slot 模式日期+9段时段网格
  //  - 按服务器时间过滤已过去的整段时段（与 BUG-FIX-RESCHEDULE-V2 一致）
  //  - 默认选中订单当前预约日期/时段（方便商家在原时间附近做微调）
  //  - 不允许选择已过去的日期；保存条件按模式校验
  const openAdjustTimePopup = () => {
    if (!order) return;
    // 默认日期：优先用订单当前预约日期；否则明天
    let defaultDate: Date;
    if (order.appointment_date) {
      defaultDate = new Date(`${order.appointment_date}T00:00:00`);
    } else if (order.appointment_time) {
      try {
        defaultDate = parseServerTime(order.appointment_time) || new Date();
      } catch {
        defaultDate = new Date();
        defaultDate.setDate(defaultDate.getDate() + 1);
      }
    } else {
      defaultDate = new Date();
      defaultDate.setDate(defaultDate.getDate() + 1);
    }
    setApptDate(defaultDate);
    // 默认时段：订单当前 time_slot；空则保持空（time_slot 模式必须用户主动选择）
    setApptSlot(order.time_slot || '');
    // 弹窗打开时拉服务器时间，保证 9 段过滤准确
    initServerTime().catch(() => {});
    setShowApptPopup(true);
  };

  const submitAdjustTime = async () => {
    if (!order || !apptDate) {
      Toast.show({ content: '请选择预约日期' });
      return;
    }
    const mode = order.appointment_mode || 'time_slot';
    const isTimeSlotMode = mode === 'time_slot';
    if (isTimeSlotMode && !apptSlot) {
      Toast.show({ content: '请选择预约时段' });
      return;
    }
    setApptSubmitting(true);
    try {
      const y = apptDate.getFullYear();
      const m = String(apptDate.getMonth() + 1).padStart(2, '0');
      const d = String(apptDate.getDate()).padStart(2, '0');
      const dateStr = `${y}-${m}-${d}`;
      const adjustSid = getCurrentStoreId();
      const adjustParams: any = {};
      if (adjustSid) adjustParams.store_id = adjustSid;
      const payload: any = { new_date: dateStr };
      if (isTimeSlotMode) {
        payload.new_time_slot = apptSlot;
      }
      await api.put(`/api/merchant/orders/${orderId}/appointment-time`, payload, { params: adjustParams });
      Toast.show({ icon: 'success', content: '改约成功' });
      setShowApptPopup(false);
      loadOrder();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || '改约失败');
      Toast.show({ icon: 'fail', content: msg });
    } finally {
      setApptSubmitting(false);
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
  const canConfirm = order.is_appointment && ['pending', 'paid', 'pending_appointment', 'pending_payment'].includes(order.status);
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
          <div>下单: <span style={{ color: '#333' }}>{order.created_at ? formatDateTime(order.created_at) : '—'}</span></div>
          {(order.appointment_time || order.time_slot) && (
            <div style={{ gridColumn: '1 / -1' }}>
              预约时间: <span style={{ color: '#1677ff', fontWeight: 500 }}>
                {/* [BUGFIX-UO-20260507-001] 优先显示 appointment_date + time_slot，
                    与客户端"2026-05-08 14:00-15:00"保持一致；缺失时回退到 appointment_time。 */}
                {order.appointment_date && order.time_slot
                  ? `${order.appointment_date} ${order.time_slot}`
                  : order.time_slot
                    ? order.time_slot
                    : (order.appointment_time ? formatDateTime(order.appointment_time) : '—')}
              </span>
            </div>
          )}
          {/* [BUGFIX-UO-20260507-001] 商家移动端详情新增「支付方式」行 */}
          {(order.payment_method_text || order.payment_method) && (
            <div style={{ gridColumn: '1 / -1' }}>
              支付方式: <span style={{ color: '#333' }}>
                {order.payment_method_text || order.payment_method}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* [PRD-04 §F-04-5 / §2.7] 改期通知状态卡片：仅在曾下发过改期通知时展示 */}
      {order.last_reschedule_notify && order.last_reschedule_notify_status !== 'none' && (
        <div
          style={{
            margin: '0 12px 12px',
            background: order.last_reschedule_notify_status === 'all_failed' ? '#fff1f0' : '#F0F9FF',
            border:
              order.last_reschedule_notify_status === 'all_failed'
                ? '1px solid #ffa39e'
                : '1px solid #BAE6FD',
            borderRadius: 12,
            padding: 14,
          }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              marginBottom: 6,
              color: order.last_reschedule_notify_status === 'all_failed' ? '#cf1322' : '#0369A1',
            }}
          >
            改期通知状态：{order.last_reschedule_notify.display}
          </div>
          <div style={{ fontSize: 12, color: '#666', lineHeight: 1.7 }}>
            {(order.last_reschedule_notify.channels || []).map((c) => (
              <div key={c.name}>
                <span style={{ display: 'inline-block', minWidth: 110 }}>
                  {c.name === 'wechat_subscribe' && '微信订阅消息'}
                  {c.name === 'app_push' && 'APP push'}
                  {c.name === 'sms' && '短信'}
                  {!['wechat_subscribe', 'app_push', 'sms'].includes(c.name) && c.name}
                </span>
                <span style={{ color: c.ok ? '#0EA5E9' : '#fa541c', fontWeight: 500 }}>
                  {c.ok ? '✓ 成功' : '✗ 失败'}
                </span>
                {c.detail && <span style={{ marginLeft: 8, color: '#999' }}>（{c.detail}）</span>}
              </div>
            ))}
            {order.last_reschedule_notify.created_at && (
              <div style={{ marginTop: 4, color: '#999' }}>
                通知时间：{formatDateTime(order.last_reschedule_notify.created_at)}
              </div>
            )}
            {order.last_reschedule_notify_status === 'all_failed' && (
              <div style={{ marginTop: 6, color: '#cf1322' }}>
                ⚠ 三通道全部失败，运营已收到企业微信告警，请人工电话联系客户兜底。
              </div>
            )}
          </div>
        </div>
      )}

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
              onClick={openAdjustTimePopup}
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
                  <span>{n.created_at ? formatDateTime(n.created_at) : ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* [BUG-FIX-MERCHANT-RESCHEDULE-V1 2026-05-07] 调整预约时间抽屉
          - 完全对齐客户端「改约」抽屉：
            · 从底部弹出
            · 横向日期选择 + 时段网格（time_slot 模式才有时段网格）
            · 按服务器时间过滤已过去的整段时段
            · date 模式仅显示日期；time_slot 模式按 9 段固定切片
       */}
      {(() => {
        const mode = order?.appointment_mode || 'time_slot';
        const isTimeSlotMode = mode === 'time_slot';
        const slotOptions = filterPastSlots(apptDate, RESCHEDULE_TIME_SLOTS_9);
        const isToday = !!apptDate && isSameDayAsServer(apptDate);
        const todayHasNoSlot = isTimeSlotMode && isToday && slotOptions.length === 0;
        const serverTimeUnreliable = isServerTimeUnreliable();
        const goTomorrow = () => {
          const tomorrow = new Date(getServerNow());
          tomorrow.setDate(tomorrow.getDate() + 1);
          tomorrow.setHours(0, 0, 0, 0);
          setApptDate(tomorrow);
          setApptSlot('');
        };
        const submitDisabled =
          apptSubmitting ||
          !apptDate ||
          (isTimeSlotMode && (!apptSlot || todayHasNoSlot));

        return (
          <Popup
            visible={showApptPopup}
            onMaskClick={() => setShowApptPopup(false)}
            onClose={() => setShowApptPopup(false)}
            bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: '20px 16px 24px' }}
          >
            <div style={{ fontSize: 16, fontWeight: 600, textAlign: 'center', marginBottom: 12 }}>
              调整预约时间
            </div>
            {serverTimeUnreliable && (
              <div
                style={{
                  background: '#fff2f0',
                  border: '1px solid #ffccc7',
                  color: '#cf1322',
                  padding: '6px 10px',
                  borderRadius: 6,
                  marginBottom: 12,
                  fontSize: 12,
                  lineHeight: 1.5,
                }}
              >
                网络异常，时段以服务器为准；如改约失败请重试
              </div>
            )}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>预约日期</div>
              <Button
                block
                onClick={() => setShowApptDatePicker(true)}
                style={{ height: 44, fontSize: 14, textAlign: 'left', borderRadius: 8 }}
              >
                {apptDate
                  ? `${apptDate.getFullYear()}-${String(apptDate.getMonth() + 1).padStart(2, '0')}-${String(apptDate.getDate()).padStart(2, '0')}`
                  : '请选择日期'}
              </Button>
            </div>
            {isTimeSlotMode && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>预约时段</div>
                {todayHasNoSlot ? (
                  <div
                    style={{
                      background: '#fafafa',
                      border: '1px dashed #d9d9d9',
                      borderRadius: 6,
                      padding: '16px 12px',
                      textAlign: 'center',
                      color: '#8c8c8c',
                      fontSize: 13,
                    }}
                  >
                    <div style={{ marginBottom: 10 }}>今日剩余时段已过，请选择明天起的日期</div>
                    <Button size="small" color="primary" onClick={goTomorrow}>
                      一键切到明天
                    </Button>
                  </div>
                ) : (
                  <Selector
                    options={slotOptions.map((s) => ({ label: s, value: s }))}
                    value={apptSlot ? [apptSlot] : []}
                    onChange={(arr) => setApptSlot(arr[0] || '')}
                    columns={3}
                    style={{ '--padding': '8px 0', '--border-radius': '6px' } as any}
                  />
                )}
              </div>
            )}
            <Button
              block
              loading={apptSubmitting}
              onClick={submitAdjustTime}
              disabled={submitDisabled}
              style={{
                background: submitDisabled ? '#d9d9d9' : '#1677ff',
                color: '#fff',
                border: 'none',
                borderRadius: 22,
                height: 44,
                fontSize: 15,
              }}
            >
              确认改约
            </Button>
          </Popup>
        );
      })()}

      <DatePicker
        visible={showApptDatePicker}
        onClose={() => setShowApptDatePicker(false)}
        min={(() => {
          // 不允许选择已过去的日期
          const d = new Date(getServerNow());
          d.setHours(0, 0, 0, 0);
          return d;
        })()}
        max={(() => {
          const d = new Date(getServerNow());
          d.setDate(d.getDate() + 90);
          return d;
        })()}
        precision="day"
        value={apptDate || undefined}
        onConfirm={(d) => {
          setApptDate(d);
          // 切换日期时清空时段，避免选了今天又切回明天的旧时段误提交
          if (apptDate && d.getTime() !== apptDate.getTime()) {
            // 仅当跨日时清空，避免重选同一天误清
            const sameDay =
              d.getFullYear() === apptDate.getFullYear() &&
              d.getMonth() === apptDate.getMonth() &&
              d.getDate() === apptDate.getDate();
            if (!sameDay) setApptSlot('');
          }
          setShowApptDatePicker(false);
        }}
      />
    </div>
  );
}
