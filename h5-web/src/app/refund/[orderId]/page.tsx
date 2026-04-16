'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  NavBar,
  Card,
  Button,
  TextArea,
  Radio,
  Space,
  Toast,
  SpinLoading,
} from 'antd-mobile';
import api from '@/lib/api';

interface OrderDetail {
  id: number;
  order_no: string;
  paid_amount: number;
  items: Array<{
    id: number;
    product_name: string;
    product_price: number;
    quantity: number;
    subtotal: number;
  }>;
}

const REFUND_REASONS = [
  '不想要了',
  '商品信息描述不符',
  '质量问题',
  '收到商品损坏',
  '发货太慢',
  '其他原因',
];

export default function RefundPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params.orderId as string;
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState('');
  const [customReason, setCustomReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/api/orders/unified/${orderId}`).then((res: any) => {
      setOrder(res.data || res);
    }).catch(() => {
      Toast.show({ content: '加载失败' });
    }).finally(() => setLoading(false));
  }, [orderId]);

  const handleSubmit = async () => {
    const finalReason = reason === '其他原因' ? (customReason || '其他原因') : reason;
    if (!finalReason) {
      Toast.show({ content: '请选择退款原因' });
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/api/orders/unified/${orderId}/refund`, {
        reason: finalReason,
        refund_amount: order?.paid_amount,
      });
      Toast.show({ content: '退款申请已提交', icon: 'success' });
      router.back();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '申请失败' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>申请退款</NavBar>
        <div className="flex items-center justify-center py-40"><SpinLoading color="primary" /></div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>申请退款</NavBar>
        <div className="text-center text-gray-400 py-40">订单不存在</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        申请退款
      </NavBar>

      <div className="px-4 pt-4">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">退款金额</span>
            <span className="text-xl font-bold text-red-500">¥{order.paid_amount.toFixed(2)}</span>
          </div>
          <div className="text-xs text-gray-400 mt-1">
            订单号：{order.order_no}
          </div>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="text-sm font-medium mb-3">退款原因</div>
          <Radio.Group value={reason} onChange={(val) => setReason(val as string)}>
            <Space direction="vertical" block>
              {REFUND_REASONS.map((r) => (
                <Radio key={r} value={r} style={{ '--icon-size': '18px', '--font-size': '14px' }}>
                  {r}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
          {reason === '其他原因' && (
            <TextArea
              placeholder="请描述退款原因"
              value={customReason}
              onChange={setCustomReason}
              maxLength={200}
              showCount
              rows={3}
              style={{ marginTop: 12 }}
            />
          )}
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="text-sm font-medium mb-2">商品信息</div>
          {order.items.map((item) => (
            <div key={item.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-none">
              <div>
                <div className="text-sm">{item.product_name}</div>
                <div className="text-xs text-gray-400">x{item.quantity}</div>
              </div>
              <span className="text-sm">¥{item.subtotal.toFixed(2)}</span>
            </div>
          ))}
        </Card>

        <div className="text-xs text-gray-400 px-2">
          <p>* 退款申请提交后，将在1-3个工作日内处理</p>
          <p className="mt-1">* 审核通过后，退款将原路返回</p>
        </div>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        <Button
          block
          loading={submitting}
          onClick={handleSubmit}
          style={{
            borderRadius: 24,
            height: 44,
            background: 'linear-gradient(135deg, #f5222d, #fa541c)',
            color: '#fff',
            border: 'none',
          }}
        >
          提交退款申请
        </Button>
      </div>
    </div>
  );
}
