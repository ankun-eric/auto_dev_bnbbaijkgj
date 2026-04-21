'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Tag, Image, Empty, SpinLoading, InfiniteScroll, PullToRefresh } from 'antd-mobile';
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
  refund_amount?: number;
  items: OrderItem[];
  created_at: string;
}

const REFUND_STATUS_TEXT: Record<string, string> = {
  applied: '退款申请中',
  processing: '退款处理中',
  reviewing: '退款处理中',
  returning: '退款处理中',
  refund_success: '退款成功',
  approved: '退款成功',
  refund_failed: '退款失败',
  rejected: '退款被拒绝',
};

const REFUND_STATUS_COLOR: Record<string, string> = {
  applied: '#fa8c16',
  processing: '#1890ff',
  reviewing: '#1890ff',
  returning: '#1890ff',
  refund_success: '#52c41a',
  approved: '#52c41a',
  refund_failed: '#f5222d',
  rejected: '#8c8c8c',
};

const REFUND_TABS: { key: string; label: string; filter: string }[] = [
  { key: 'all', label: '全部', filter: 'all_refund' },
  { key: 'applied', label: '申请中', filter: 'applied' },
  { key: 'reviewing', label: '处理中', filter: 'reviewing,returning' },
  { key: 'refund_success', label: '已退款', filter: 'refund_success,approved' },
  { key: 'rejected', label: '已拒绝', filter: 'rejected' },
];

export default function RefundListPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('all');

  const fetchOrders = useCallback(async (pageNum: number, reset = false) => {
    try {
      const filter = REFUND_TABS.find((t) => t.key === activeTab)?.filter || 'all_refund';
      const params: Record<string, any> = {
        page: pageNum,
        page_size: 20,
        refund_status: filter,
      };
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

  const handleRefresh = async () => {
    setLoading(true);
    setPage(1);
    await fetchOrders(1, true);
  };

  const handleTabChange = (key: string) => {
    if (key === activeTab) return;
    setActiveTab(key);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        退款/售后
      </NavBar>

      <div
        className="flex overflow-x-auto no-scrollbar border-b border-gray-100"
        style={{ background: '#fff' }}
      >
        {REFUND_TABS.map((tab) => {
          const active = tab.key === activeTab;
          return (
            <div
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className="flex-shrink-0 px-4 py-3 text-sm cursor-pointer relative"
              style={{
                color: active ? '#52c41a' : '#4b5563',
                fontWeight: active ? 600 : 400,
              }}
            >
              {tab.label}
              {active && (
                <span
                  style={{
                    position: 'absolute',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    bottom: 4,
                    width: 20,
                    height: 2,
                    background: '#52c41a',
                    borderRadius: 1,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      <PullToRefresh onRefresh={handleRefresh}>
        <div className="px-4 pt-3">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <SpinLoading color="primary" />
            </div>
          ) : orders.length === 0 ? (
            <Empty description="暂无退款/售后订单" style={{ padding: '80px 0' }} />
          ) : (
            orders.map((order) => {
              const refundText = REFUND_STATUS_TEXT[order.refund_status] || order.refund_status;
              const refundColor = REFUND_STATUS_COLOR[order.refund_status] || '#8c8c8c';
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
                        '--background-color': `${refundColor}15`,
                        '--text-color': refundColor,
                        '--border-color': 'transparent',
                        fontSize: 10,
                      }}
                    >
                      {refundText}
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
                      退款金额 <span className="font-bold text-red-500">¥{(order.refund_amount ?? order.paid_amount).toFixed(2)}</span>
                    </span>
                  </div>
                </Card>
              );
            })
          )}
          {!loading && orders.length > 0 && (
            <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
          )}
        </div>
      </PullToRefresh>
    </div>
  );
}
