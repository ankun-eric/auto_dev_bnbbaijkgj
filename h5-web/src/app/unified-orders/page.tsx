'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  NavBar,
  Tabs,
  Card,
  Tag,
  Image,
  Button,
  Empty,
  SpinLoading,
  InfiniteScroll,
  Toast,
  Dialog,
} from 'antd-mobile';
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
}

interface Order {
  id: number;
  order_no: string;
  total_amount: number;
  paid_amount: number;
  status: string;
  refund_status: string;
  items: OrderItem[];
  created_at: string;
}

const STATUS_TABS: Record<string, string> = {
  all: '全部',
  pending_payment: '待付款',
  pending_shipment: '待发货',
  pending_receipt: '待收货',
  pending_use: '待使用',
  pending_review: '待评价',
  refund: '退款售后',
};

const STATUS_TEXT: Record<string, string> = {
  pending_payment: '待付款',
  pending_shipment: '待发货',
  pending_receipt: '待收货',
  pending_use: '待使用',
  pending_review: '待评价',
  completed: '已完成',
  cancelled: '已取消',
};

const STATUS_COLOR: Record<string, string> = {
  pending_payment: '#fa8c16',
  pending_shipment: '#1890ff',
  pending_receipt: '#722ed1',
  pending_use: '#13c2c2',
  pending_review: '#eb2f96',
  completed: '#52c41a',
  cancelled: '#8c8c8c',
};

export default function UnifiedOrdersWrapper() {
  return (
    <Suspense fallback={<div />}>
      <UnifiedOrdersPage />
    </Suspense>
  );
}

function UnifiedOrdersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'all';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const fetchOrders = useCallback(async (pageNum: number, reset = false) => {
    try {
      const params: Record<string, any> = { page: pageNum, page_size: 20 };
      if (activeTab !== 'all') params.status = activeTab;
      const res: any = await api.get('/api/orders/unified', { params });
      const data = res.data || res;
      const items = data.items || [];
      if (reset) {
        setOrders(items);
      } else {
        setOrders((prev) => [...prev, ...items]);
      }
      setHasMore(pageNum * 20 < (data.total || 0));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    fetchOrders(1, true);
  }, [fetchOrders]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await fetchOrders(next);
  };

  const handlePay = async (orderId: number) => {
    try {
      await api.post(`/api/orders/unified/${orderId}/pay`, { payment_method: 'wechat' });
      Toast.show({ content: '支付成功' });
      setLoading(true);
      setPage(1);
      fetchOrders(1, true);
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '支付失败' });
    }
  };

  const handleCancel = async (orderId: number) => {
    Dialog.confirm({
      content: '确认取消该订单？',
      confirmText: '确认',
      cancelText: '再想想',
      onConfirm: async () => {
        try {
          await api.post(`/api/orders/unified/${orderId}/cancel`, {});
          Toast.show({ content: '已取消' });
          setLoading(true);
          setPage(1);
          fetchOrders(1, true);
        } catch (err: any) {
          Toast.show({ content: err?.response?.data?.detail || '取消失败' });
        }
      },
    });
  };

  const getStatusDisplay = (order: Order) => {
    if (order.refund_status && order.refund_status !== 'none') {
      return { text: '退款中', color: '#f5222d' };
    }
    return {
      text: STATUS_TEXT[order.status] || order.status,
      color: STATUS_COLOR[order.status] || '#8c8c8c',
    };
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        我的订单
      </NavBar>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          background: '#fff',
        }}
      >
        {Object.entries(STATUS_TABS).map(([key, title]) => (
          <Tabs.Tab key={key} title={title} />
        ))}
      </Tabs>

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : orders.length === 0 ? (
          <Empty description="暂无订单" style={{ padding: '80px 0' }} />
        ) : (
          orders.map((order) => {
            const statusInfo = getStatusDisplay(order);
            return (
              <Card
                key={order.id}
                onClick={() => router.push(`/unified-order/${order.id}`)}
                style={{ marginBottom: 12, borderRadius: 12 }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-gray-400">订单号：{order.order_no}</span>
                  <Tag
                    style={{
                      '--background-color': `${statusInfo.color}15`,
                      '--text-color': statusInfo.color,
                      '--border-color': 'transparent',
                      fontSize: 10,
                    }}
                  >
                    {statusInfo.text}
                  </Tag>
                </div>
                {order.items.map((item) => (
                  <div key={item.id} className="flex items-center mb-2">
                    <div className="w-16 h-16 rounded-lg flex-shrink-0 overflow-hidden">
                      {item.product_image ? (
                        <Image src={item.product_image} width={64} height={64} fit="cover" style={{ borderRadius: 8 }} />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: '#f6ffed' }}>
                          🛍️
                        </div>
                      )}
                    </div>
                    <div className="flex-1 ml-3 min-w-0">
                      <div className="font-medium text-sm truncate">{item.product_name}</div>
                      <div className="text-xs text-gray-400 mt-1">x{item.quantity}</div>
                    </div>
                    <span className="font-bold text-sm">¥{item.subtotal.toFixed(2)}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between pt-2 border-t border-gray-50">
                  <span className="text-xs text-gray-400">
                    {new Date(order.created_at).toLocaleString('zh-CN')}
                  </span>
                  <span className="text-sm">
                    实付 <span className="font-bold text-red-500">¥{order.paid_amount.toFixed(2)}</span>
                  </span>
                </div>
                {(order.status === 'pending_payment' || order.status === 'pending_receipt' || order.status === 'pending_review') && (
                  <div className="flex justify-end gap-2 mt-3 pt-3 border-t border-gray-50">
                    {order.status === 'pending_payment' && (
                      <>
                        <Button
                          size="mini"
                          onClick={(e) => { e.stopPropagation(); handleCancel(order.id); }}
                          style={{ borderRadius: 16, fontSize: 12 }}
                        >
                          取消订单
                        </Button>
                        <Button
                          size="mini"
                          onClick={(e) => { e.stopPropagation(); handlePay(order.id); }}
                          style={{ borderRadius: 16, fontSize: 12, background: '#52c41a', color: '#fff', border: 'none' }}
                        >
                          去支付
                        </Button>
                      </>
                    )}
                    {order.status === 'pending_receipt' && (
                      <Button
                        size="mini"
                        onClick={(e) => {
                          e.stopPropagation();
                          api.post(`/api/orders/unified/${order.id}/confirm`).then(() => {
                            Toast.show({ content: '已确认收货' });
                            setLoading(true);
                            setPage(1);
                            fetchOrders(1, true);
                          }).catch(() => Toast.show({ content: '操作失败' }));
                        }}
                        style={{ borderRadius: 16, fontSize: 12, background: '#52c41a', color: '#fff', border: 'none' }}
                      >
                        确认收货
                      </Button>
                    )}
                    {order.status === 'pending_review' && (
                      <Button
                        size="mini"
                        onClick={(e) => { e.stopPropagation(); router.push(`/review/${order.id}`); }}
                        style={{ borderRadius: 16, fontSize: 12, color: '#52c41a', borderColor: '#52c41a' }}
                      >
                        去评价
                      </Button>
                    )}
                  </div>
                )}
              </Card>
            );
          })
        )}
        {!loading && orders.length > 0 && (
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        )}
      </div>
    </div>
  );
}
