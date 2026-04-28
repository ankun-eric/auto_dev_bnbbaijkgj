'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, Image, Tag, Button, Steps, Divider, Toast, Dialog, SpinLoading, ProgressBar } from 'antd-mobile';
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
}

const STATUS_TEXT: Record<string, string> = {
  pending_payment: '待付款',
  pending_shipment: '待发货',
  pending_receipt: '待收货',
  pending_use: '待使用',
  pending_review: '待评价',
  completed: '已完成',
  cancelled: '已取消',
};

const STATUS_DESC: Record<string, string> = {
  pending_payment: '请尽快完成支付',
  pending_shipment: '商家正在处理您的订单',
  pending_receipt: '商品已发货，请注意查收',
  pending_use: '请凭核销码到店使用',
  pending_review: '服务已完成，期待您的评价',
  completed: '感谢您的支持',
  cancelled: '订单已取消',
};

export default function UnifiedOrderDetailPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params.id as string;
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);

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
          {order.refund_status !== 'none' ? '退款处理中' : (STATUS_TEXT[order.status] || order.status)}
        </div>
        <div className="text-white/70 text-xs mt-1">
          {order.refund_status !== 'none' ? '您的退款申请正在处理中' : (STATUS_DESC[order.status] || '')}
        </div>
      </div>

      <div className="px-4 -mt-3">
        {hasInStore && order.status === 'pending_use' && order.items.filter((i) => i.fulfillment_type === 'in_store').map((item) => (
          <Card key={item.id} style={{ borderRadius: 12, marginBottom: 12, textAlign: 'center' }}>
            <div className="text-sm text-gray-500 mb-2">核销码</div>
            {item.verification_qrcode_token && (
              <div className="flex justify-center mb-3">
                <Image
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${item.verification_qrcode_token}`}
                  width={150}
                  height={150}
                  fit="contain"
                />
              </div>
            )}
            {item.verification_code && (
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
        ))}

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
            {order.payment_method && (
              <div className="flex justify-between">
                <span>支付方式</span><span>{order.payment_method === 'wechat' ? '微信支付' : '支付宝'}</span>
              </div>
            )}
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
        {['pending_shipment', 'pending_receipt', 'pending_use'].includes(order.status) && order.refund_status === 'none' && (
          <Button
            onClick={() => router.push(`/refund/${order.id}`)}
            style={{ borderRadius: 20, height: 40, fontSize: 14 }}
          >
            申请退款
          </Button>
        )}
      </div>
    </div>
  );
}
