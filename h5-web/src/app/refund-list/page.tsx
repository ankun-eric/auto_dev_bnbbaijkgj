'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Tag, Image, Empty, SpinLoading, InfiniteScroll, PullToRefresh } from 'antd-mobile';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

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
  aftersales_logical_status?: string;
  aftersales_logical_label?: string;
}

// PRD「我的订单与售后状态体系优化」F-06/F-07：
// 退款/售后独立列表与「全部订单 - 退货/售后」Tab 数据范围、文案、二级筛选完全一致
// 4 个统一逻辑状态 + 全部
const AFTERSALES_LABEL: Record<string, string> = {
  pending: '待审核',
  processing: '处理中',
  completed: '已完成',
  rejected: '已驳回',
  none: '无',
};

const AFTERSALES_COLOR: Record<string, string> = {
  pending: '#fa8c16',
  processing: '#1890ff',
  completed: '#52c41a',
  rejected: '#8c8c8c',
  none: '#8c8c8c',
};

const REFUND_TABS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'processing', label: '处理中' },
  { key: 'completed', label: '已完成' },
  { key: 'rejected', label: '已驳回' },
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
      // PRD F-06/F-07：使用与 unified-orders「退货/售后」Tab 完全相同的接口参数
      // tab=refund_aftersales + sub_tab=（待审核/处理中/已完成/已驳回）
      const params: Record<string, any> = {
        page: pageNum,
        page_size: 20,
        tab: 'refund_aftersales',
        sub_tab: activeTab,
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
              const logicalKey = order.aftersales_logical_status || 'none';
              const refundText = order.aftersales_logical_label || AFTERSALES_LABEL[logicalKey] || '无';
              const refundColor = AFTERSALES_COLOR[logicalKey] || '#8c8c8c';
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
                          <Image src={resolveAssetUrl(item.product_image)} width={64} height={64} fit="cover" style={{ borderRadius: 8 }} />
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
                      <span className="font-bold text-sm">¥{item.subtotal}</span>
                    </div>
                  ))}
                  <div className="flex items-center justify-between pt-2 border-t border-gray-50">
                    <span className="text-xs text-gray-400">
                      {new Date(order.created_at).toLocaleString('zh-CN')}
                    </span>
                    <span className="text-sm">
                      退款金额 <span className="font-bold text-red-500">¥{order.refund_amount ?? order.paid_amount}</span>
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
