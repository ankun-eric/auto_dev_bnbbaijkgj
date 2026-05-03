'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, Image, Tag, Button, Steps, Divider, Toast, Dialog, SpinLoading, ProgressBar, Popup, DatePicker, Selector } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface OrderItem {
  id: number;
  product_id: number;
  product_name: string;
  product_image: string | null;
  product_price: number;
  quantity: number;
  subtotal: number;
  fulfillment_type: string;
  verification_code: string | null;
  verification_qrcode_token: string | null;
  total_redeem_count: number;
  used_redeem_count: number;
  appointment_data: any | null;
  appointment_time: string | null;
}

interface OrderDetail {
  id: number;
  order_no: string;
  total_amount: number;
  paid_amount: number;
  points_deduction: number;
  payment_method: string | null;
  coupon_discount: number;
  status: string;
  display_status?: string;
  refund_status: string;
  shipping_info: any;
  tracking_number: string | null;
  tracking_company: string | null;
  notes: string | null;
  items: OrderItem[];
  created_at: string;
  paid_at: string | null;
  shipped_at: string | null;
  received_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  store_name: string | null;
}

const STATUS_TEXT: Record<string, string> = {
  pending_payment: '待付款',
  pending_shipment: '待发货',
  pending_receipt: '待收货',
  pending_appointment: '待预约',
  appointed: '待核销',
  pending_use: '待核销',
  partial_used: '部分核销',
  pending_review: '待评价',
  completed: '已完成',
  expired: '已过期',
  refunding: '退款中',
  refunded: '已退款',
  cancelled: '已取消',
};

const STATUS_DESC: Record<string, string> = {
  pending_payment: '请尽快完成支付',
  pending_shipment: '商家正在处理您的订单',
  pending_receipt: '商品已发货，请注意查收',
  pending_appointment: '感谢下单！请选择您方便的服务时间',
  appointed: '请凭核销码到店使用，可随时修改预约时间',
  pending_use: '请凭核销码到店使用，可随时修改预约时间',
  pending_review: '服务已完成，期待您的评价',
  completed: '感谢您的支持',
  cancelled: '订单已取消',
};

// [先下单后预约 Bug 修复 v1.0] 默认时段（与商品时段一致或商品未配时段时使用）
const DEFAULT_TIME_SLOTS = [
  '09:00-10:00', '10:00-11:00', '11:00-12:00',
  '13:00-14:00', '14:00-15:00', '15:00-16:00',
  '16:00-17:00', '17:00-18:00',
];

export default function UnifiedOrderDetailPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params.id as string;
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  // [先下单后预约 Bug 修复 v1.0] 立即预约弹窗状态
  const [showAppointmentPopup, setShowAppointmentPopup] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [apptDate, setApptDate] = useState<Date | null>(null);
  const [apptSlot, setApptSlot] = useState<string>('');
  const [apptItemId, setApptItemId] = useState<number | null>(null);
  const [apptSubmitting, setApptSubmitting] = useState(false);

  const fetchOrder = () => {
    api.get(`/api/orders/unified/${orderId}`).then((res: any) => {
      setOrder(res.data || res);
    }).catch(() => {
      Toast.show({ content: '加载失败' });
    }).finally(() => setLoading(false));
  };

  useEffect(() => { fetchOrder(); }, [orderId]);

  const handlePay = async () => {
    try {
      await api.post(`/api/orders/unified/${orderId}/pay`, { payment_method: 'wechat' });
      Toast.show({ content: '支付成功' });
      fetchOrder();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '支付失败' });
    }
  };

  const handleCancel = () => {
    Dialog.confirm({
      content: '确认取消该订单？',
      onConfirm: async () => {
        try {
          await api.post(`/api/orders/unified/${orderId}/cancel`, {});
          Toast.show({ content: '已取消' });
          fetchOrder();
        } catch (err: any) {
          Toast.show({ content: err?.response?.data?.detail || '取消失败' });
        }
      },
    });
  };

  const handleConfirmReceipt = () => {
    Dialog.confirm({
      content: '确认已收到商品？',
      onConfirm: async () => {
        try {
          await api.post(`/api/orders/unified/${orderId}/confirm`);
          Toast.show({ content: '已确认收货' });
          fetchOrder();
        } catch (err: any) {
          Toast.show({ content: err?.response?.data?.detail || '操作失败' });
        }
      },
    });
  };

  const copyCode = (code: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code);
    }
    Toast.show({ content: '核销码已复制' });
  };

  // [先下单后预约 Bug 修复 v1.0] 打开"立即预约"弹窗
  const openAppointmentPopup = () => {
    if (!order) return;
    const firstInStoreItem = order.items.find((i) => i.fulfillment_type === 'in_store');
    if (!firstInStoreItem) {
      Toast.show({ content: '订单暂无可预约商品' });
      return;
    }
    setApptItemId(firstInStoreItem.id);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setApptDate(tomorrow);
    setApptSlot('');
    setShowAppointmentPopup(true);
  };

  // [先下单后预约 Bug 修复 v1.0] 提交预约
  const submitAppointment = async () => {
    if (!apptDate) {
      Toast.show({ content: '请选择预约日期' });
      return;
    }
    if (!apptSlot) {
      Toast.show({ content: '请选择预约时段' });
      return;
    }
    if (!apptItemId) {
      Toast.show({ content: '订单异常' });
      return;
    }
    setApptSubmitting(true);
    try {
      const y = apptDate.getFullYear();
      const m = String(apptDate.getMonth() + 1).padStart(2, '0');
      const d = String(apptDate.getDate()).padStart(2, '0');
      const dateStr = `${y}-${m}-${d}`;
      const startTime = apptSlot.split('-')[0];
      await api.post(`/api/orders/unified/${orderId}/appointment`, {
        item_id: apptItemId,
        appointment_time: `${dateStr}T${startTime}:00`,
        appointment_data: {
          date: dateStr,
          time_slot: apptSlot,
        },
      });
      Toast.show({ content: '预约成功' });
      setShowAppointmentPopup(false);
      fetchOrder();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '预约失败' });
    } finally {
      setApptSubmitting(false);
    }
  };

  const handleWithdrawRefund = () => {
    Dialog.confirm({
      content: '确认撤回退款申请？',
      onConfirm: async () => {
        try {
          await api.post(`/api/orders/unified/${orderId}/refund/withdraw`);
          Toast.show({ content: '退款已撤回' });
          fetchOrder();
        } catch (err: any) {
          Toast.show({ content: err?.response?.data?.detail || '撤回失败' });
        }
      },
    });
  };

  const getStepsCurrent = () => {
    const statusOrder = ['pending_payment', 'pending_shipment', 'pending_receipt', 'pending_use', 'pending_review', 'completed'];
    if (!order) return 0;
    if (order.status === 'cancelled') return -1;
    return statusOrder.indexOf(order.status);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>订单详情</GreenNavBar>
        <div className="flex items-center justify-center py-40"><SpinLoading color="primary" /></div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>订单详情</GreenNavBar>
        <div className="text-center text-gray-400 py-40">订单不存在</div>
      </div>
    );
  }

  const hasInStore = order.items.some((i) => i.fulfillment_type === 'in_store');
  const hasDelivery = order.items.some((i) => i.fulfillment_type === 'delivery');

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <GreenNavBar>
        订单详情
      </GreenNavBar>

      <div
        className="px-4 py-6 text-center"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="text-white text-lg font-bold">
          {order.refund_status !== 'none' ? '退款处理中' : (order.display_status || STATUS_TEXT[order.status] || order.status)}
        </div>
        <div className="text-white/70 text-xs mt-1">
          {order.refund_status !== 'none' ? '您的退款申请正在处理中' : (STATUS_DESC[order.status] || '')}
        </div>
      </div>

      {/* [先下单后预约 Bug 修复 v1.0] 待预约横幅 */}
      {order.status === 'pending_appointment' && order.refund_status === 'none' && (
        <div className="px-4 mt-2 mb-1">
          <div
            style={{
              background: 'linear-gradient(90deg, #fffbe6 0%, #fff7e6 100%)',
              border: '1px solid #ffd591',
              borderRadius: 8,
              padding: '12px 14px',
              fontSize: 13,
              color: '#d48806',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>🗓️ 您还未预约服务时间，请尽快选择您方便的时间</span>
            <Button
              size="small"
              onClick={openAppointmentPopup}
              style={{
                background: '#52c41a',
                color: '#fff',
                border: 'none',
                borderRadius: 14,
                fontSize: 12,
                marginLeft: 8,
                flexShrink: 0,
              }}
            >
              立即预约
            </Button>
          </div>
        </div>
      )}

      {order.refund_status !== 'none' && (
        <div className="px-4 mt-2 mb-1">
          {order.refund_status === 'applied' && (
            <div style={{ background: '#fff7e6', border: '1px solid #ffd591', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#d48806' }}>
              退款申请已提交，正在处理中...
            </div>
          )}
          {order.refund_status === 'reviewing' && (
            <div style={{ background: '#e6f7ff', border: '1px solid #91d5ff', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#096dd9' }}>
              退款审核中...
            </div>
          )}
          {order.refund_status === 'approved' && (
            <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#389e0d' }}>
              退款已批准，退款处理中...
            </div>
          )}
          {order.refund_status === 'returning' && (
            <div style={{ background: '#fff7e6', border: '1px solid #ffd591', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#d48806' }}>
              退款处理中，请耐心等待...
            </div>
          )}
          {order.refund_status === 'rejected' && (
            <div style={{ background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#cf1322' }}>
              退款申请已被拒绝
            </div>
          )}
          {order.refund_status === 'refund_success' && (
            <div style={{ background: '#fafafa', border: '1px solid #d9d9d9', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#8c8c8c' }}>
              退款成功
            </div>
          )}
        </div>
      )}

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          {order.items.map((item) => (
            <div key={item.id} className="flex items-center mb-3">
              <div className="w-16 h-16 rounded-lg flex-shrink-0 overflow-hidden">
                {item.product_image ? (
                  <Image src={item.product_image} width={64} height={64} fit="cover" style={{ borderRadius: 8 }} />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: '#f6ffed' }}>🛍️</div>
                )}
              </div>
              <div className="flex-1 ml-3">
                <div className="font-medium text-sm">{item.product_name}</div>
                <div className="text-xs text-gray-400 mt-1">x{item.quantity}</div>
              </div>
              <span className="font-bold text-sm">¥{item.subtotal}</span>
            </div>
          ))}
          <Divider />
          <div className="space-y-2 text-sm text-gray-500">
            <div className="flex justify-between">
              <span>订单编号</span><span>{order.order_no}</span>
            </div>
            <div className="flex justify-between">
              <span>下单时间</span><span>{new Date(order.created_at).toLocaleString('zh-CN')}</span>
            </div>
            {order.paid_at && (
              <div className="flex justify-between">
                <span>支付时间</span><span>{new Date(order.paid_at).toLocaleString('zh-CN')}</span>
              </div>
            )}
            {/* [支付配置 PRD v1.0] 优先显示具体支付通道文案 */}
            {((order as any).payment_method_text) ? (
              <div className="flex justify-between">
                <span>支付方式</span><span>{(order as any).payment_method_text}</span>
              </div>
            ) : order.payment_method ? (
              <div className="flex justify-between">
                <span>支付方式</span><span>{order.payment_method === 'wechat' ? '微信支付' : '支付宝'}</span>
              </div>
            ) : null}
            <Divider />
            <div className="flex justify-between">
              <span>商品总价</span><span>¥{order.total_amount}</span>
            </div>
            {order.coupon_discount > 0 && (
              <div className="flex justify-between">
                <span>优惠券抵扣</span><span className="text-red-500">-¥{order.coupon_discount}</span>
              </div>
            )}
            {order.points_deduction > 0 && (
              <div className="flex justify-between">
                <span>积分抵扣</span><span className="text-red-500">-¥{order.points_deduction / 100}</span>
              </div>
            )}
            <div className="flex justify-between font-bold text-base text-gray-800">
              <span>实付金额</span><span className="text-red-500">¥{order.paid_amount}</span>
            </div>
          </div>
        </Card>

        {order.items.some(item => item.appointment_time) && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="font-medium text-base mb-3">预约信息</div>
            {order.items.filter(item => item.appointment_time).map(item => {
              const apptDate = item.appointment_time ? new Date(item.appointment_time).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '-') : '';
              const timeSlot = item.appointment_data?.time_slot || '';
              return (
                <div key={`appt-${item.id}`} className="space-y-2">
                  <div className="flex items-center text-sm">
                    <span className="mr-2">📅</span>
                    <span className="text-gray-500 mr-2">预约时间</span>
                    <span style={{ color: '#1677ff', fontWeight: 500 }}>
                      {apptDate}{timeSlot ? ` ${timeSlot}` : ''}
                    </span>
                  </div>
                  {order.store_name && (
                    <div className="flex items-center text-sm">
                      <span className="mr-2">📍</span>
                      <span className="text-gray-500 mr-2">预约门店</span>
                      <span className="text-gray-800">{order.store_name}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </Card>
        )}

        {hasInStore && (order.status === 'pending_use' || order.status === 'appointed' || order.status === 'partial_used') && order.items.filter((i) => i.fulfillment_type === 'in_store').map((item) => {
          const isRefundProcessing = ['applied', 'reviewing', 'approved', 'returning'].includes(order.refund_status);
          const isRefundSuccess = order.refund_status === 'refund_success';
          const isRefundBlocked = isRefundProcessing || isRefundSuccess;

          return (
            <Card key={item.id} style={{ borderRadius: 12, marginBottom: 12, textAlign: 'center' }}>
              <div className="text-sm text-gray-500 mb-2">
                核销码
                {isRefundProcessing && (
                  <Tag color="warning" style={{ marginLeft: 8, verticalAlign: 'middle' }}>退款处理中</Tag>
                )}
                {isRefundSuccess && (
                  <Tag color="default" style={{ marginLeft: 8, verticalAlign: 'middle' }}>已退款</Tag>
                )}
              </div>
              {item.verification_qrcode_token && (
                <div className="flex justify-center mb-3" style={isRefundBlocked ? { opacity: 0.3 } : {}}>
                  <Image
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${item.verification_qrcode_token}`}
                    width={150}
                    height={150}
                    fit="contain"
                  />
                </div>
              )}
              {item.verification_code && !isRefundBlocked && (
                <>
                  <div className="text-2xl font-bold tracking-widest text-primary mb-2">
                    {item.verification_code}
                  </div>
                  <Button
                    size="small"
                    onClick={() => copyCode(item.verification_code!)}
                    style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16, fontSize: 12 }}
                  >
                    复制核销码
                  </Button>
                </>
              )}
              {item.verification_code && isRefundBlocked && (
                <div className="text-2xl font-bold tracking-widest mb-2" style={{ color: '#ccc' }}>
                  {item.verification_code}
                </div>
              )}
              {isRefundProcessing && (
                <div className="text-xs mt-2" style={{ color: '#faad14' }}>
                  退款处理中，核销码暂时不可用
                </div>
              )}
              {isRefundSuccess && (
                <div className="text-xs mt-2" style={{ color: '#999' }}>
                  该订单已退款，核销码已失效
                </div>
              )}
              {item.total_redeem_count > 1 && (
                <div className="mt-3">
                  <div className="text-xs text-gray-400 mb-1">
                    使用进度：{item.used_redeem_count}/{item.total_redeem_count}次
                  </div>
                  <ProgressBar
                    percent={(item.used_redeem_count / item.total_redeem_count) * 100}
                    style={{ '--fill-color': '#52c41a', '--track-width': '6px' }}
                  />
                </div>
              )}
            </Card>
          );
        })}

        {hasDelivery && order.tracking_number && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }} title="物流信息">
            <div className="text-sm text-gray-600">
              <p>物流公司：{order.tracking_company || '-'}</p>
              <p className="mt-1">物流单号：{order.tracking_number}</p>
            </div>
          </Card>
        )}

        {order.notes && (
          <Card style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="text-sm text-gray-500">
              <span className="font-medium text-gray-700">备注：</span>{order.notes}
            </div>
          </Card>
        )}

        <Card style={{ borderRadius: 12, marginBottom: 20 }} title="订单进度">
          <Steps
            current={getStepsCurrent()}
            direction="vertical"
            style={{ '--title-font-size': '13px', '--description-font-size': '11px' }}
          >
            <Steps.Step title="下单成功" description={new Date(order.created_at).toLocaleString('zh-CN')} />
            {order.paid_at && (
              <Steps.Step title="支付完成" description={new Date(order.paid_at).toLocaleString('zh-CN')} />
            )}
            {order.shipped_at && (
              <Steps.Step title="已发货" description={new Date(order.shipped_at).toLocaleString('zh-CN')} />
            )}
            {order.received_at && (
              <Steps.Step title="已收货" description={new Date(order.received_at).toLocaleString('zh-CN')} />
            )}
            {order.completed_at && (
              <Steps.Step title="已完成" description={new Date(order.completed_at).toLocaleString('zh-CN')} />
            )}
            {order.cancelled_at && (
              <Steps.Step title="已取消" description={`${new Date(order.cancelled_at).toLocaleString('zh-CN')}${order.cancel_reason ? ` (${order.cancel_reason})` : ''}`} />
            )}
          </Steps>
        </Card>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3 flex justify-end gap-2"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        {order.status === 'pending_payment' && (
          <>
            <Button onClick={handleCancel} style={{ borderRadius: 20, height: 40, fontSize: 14 }}>
              取消订单
            </Button>
            <Button
              onClick={handlePay}
              style={{ borderRadius: 20, height: 40, fontSize: 14, background: '#52c41a', color: '#fff', border: 'none' }}
            >
              立即支付
            </Button>
          </>
        )}
        {/* [先下单后预约 Bug 修复 v1.0] 待预约状态：底部立即预约按钮 */}
        {order.status === 'pending_appointment' && order.refund_status === 'none' && (
          <Button
            onClick={openAppointmentPopup}
            style={{ borderRadius: 20, height: 40, fontSize: 14, background: '#52c41a', color: '#fff', border: 'none' }}
          >
            立即预约
          </Button>
        )}
        {order.status === 'pending_receipt' && (
          <Button
            onClick={handleConfirmReceipt}
            style={{ borderRadius: 20, height: 40, fontSize: 14, background: '#52c41a', color: '#fff', border: 'none' }}
          >
            确认收货
          </Button>
        )}
        {order.status === 'pending_review' && (
          <Button
            onClick={() => router.push(`/review/${order.id}`)}
            style={{ borderRadius: 20, height: 40, fontSize: 14, color: '#52c41a', borderColor: '#52c41a' }}
          >
            去评价
          </Button>
        )}
        {(order.status === 'pending_use' || order.status === 'appointed') && order.refund_status === 'none' && (
          <Button
            onClick={() => router.push(`/unified-order/${order.id}?action=appointment`)}
            style={{ borderRadius: 20, height: 40, fontSize: 14 }}
          >
            修改预约时间
          </Button>
        )}
        {['pending_shipment', 'pending_receipt', 'pending_use', 'appointed'].includes(order.status) && (order.refund_status === 'none' || order.refund_status === 'rejected') && (
          <Button
            onClick={() => router.push(`/refund/${order.id}`)}
            style={{ borderRadius: 20, height: 40, fontSize: 14 }}
          >
            申请退款
          </Button>
        )}
        {['pending_shipment', 'pending_receipt', 'pending_use', 'appointed'].includes(order.status) && order.refund_status === 'applied' && (
          <Button
            onClick={handleWithdrawRefund}
            style={{ borderRadius: 20, height: 40, fontSize: 14, color: '#faad14', borderColor: '#faad14' }}
          >
            撤回退款
          </Button>
        )}
      </div>

      {/* [先下单后预约 Bug 修复 v1.0] 立即预约弹窗 */}
      <Popup
        visible={showAppointmentPopup}
        onMaskClick={() => setShowAppointmentPopup(false)}
        onClose={() => setShowAppointmentPopup(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: '20px 16px 24px' }}
      >
        <div className="text-base font-bold text-center mb-3">选择预约时间</div>
        <div className="mb-4">
          <div className="text-sm text-gray-500 mb-1">预约日期</div>
          <Button
            block
            onClick={() => setShowDatePicker(true)}
            style={{ height: 44, fontSize: 14, textAlign: 'left', borderRadius: 8 }}
          >
            {apptDate
              ? `${apptDate.getFullYear()}-${String(apptDate.getMonth() + 1).padStart(2, '0')}-${String(apptDate.getDate()).padStart(2, '0')}`
              : '请选择日期'}
          </Button>
        </div>
        <div className="mb-4">
          <div className="text-sm text-gray-500 mb-2">预约时段</div>
          <Selector
            options={DEFAULT_TIME_SLOTS.map((s) => ({ label: s, value: s }))}
            value={apptSlot ? [apptSlot] : []}
            onChange={(arr) => setApptSlot(arr[0] || '')}
            columns={3}
            style={{ '--padding': '8px 0', '--border-radius': '6px' }}
          />
        </div>
        <Button
          block
          loading={apptSubmitting}
          onClick={submitAppointment}
          style={{ background: '#52c41a', color: '#fff', border: 'none', borderRadius: 22, height: 44, fontSize: 15 }}
        >
          确认预约
        </Button>
      </Popup>

      <DatePicker
        visible={showDatePicker}
        onClose={() => setShowDatePicker(false)}
        min={new Date()}
        max={(() => { const d = new Date(); d.setDate(d.getDate() + 90); return d; })()}
        precision="day"
        value={apptDate || undefined}
        onConfirm={(d) => { setApptDate(d); setShowDatePicker(false); }}
      />
    </div>
  );
}
