'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, Card, Tag, Button, Empty } from 'antd-mobile';

import GreenNavBar from '@/components/GreenNavBar';
const tabMap: Record<string, string> = {
  all: '全部',
  pending: '待付款',
  unused: '待核销',
  done: '已完成',
};

const mockOrders = [
  {
    id: 'ORD20240315001',
    title: '基础体检套餐',
    price: 298,
    status: 'pending',
    statusText: '待付款',
    time: '2024-03-15 14:30',
    type: 'checkup',
  },
  {
    id: 'ORD20240310002',
    title: '超声波洁牙',
    price: 128,
    status: 'unused',
    statusText: '待核销',
    time: '2024-03-10 09:20',
    type: 'dental',
  },
  {
    id: 'ORD20240301003',
    title: '有机五谷杂粮礼盒',
    price: 168,
    status: 'done',
    statusText: '已完成',
    time: '2024-03-01 16:45',
    type: 'food',
  },
  {
    id: 'ORD20240220004',
    title: '中医专家视频问诊',
    price: 198,
    status: 'done',
    statusText: '已完成',
    time: '2024-02-20 10:00',
    type: 'expert',
  },
];

export default function OrdersPageWrapper() {
  return (
    <Suspense fallback={<div />}>
      <OrdersPage />
    </Suspense>
  );
}

function OrdersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'all';
  const [activeTab, setActiveTab] = useState(initialTab);

  const filtered = activeTab === 'all' ? mockOrders : mockOrders.filter((o) => o.status === activeTab);

  const statusColor = (status: string) => {
    if (status === 'pending') return '#fa8c16';
    if (status === 'unused') return '#1890ff';
    return '#52c41a';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar>
        我的订单
      </GreenNavBar>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        className="green-bold-tabs"
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          '--active-line-height': '2px',
          background: '#fff',
        } as React.CSSProperties}
      >
        {Object.entries(tabMap).map(([key, title]) => (
          <Tabs.Tab key={key} title={title} />
        ))}
      </Tabs>

      <div className="px-4 pt-3">
        {filtered.length === 0 ? (
          <Empty description="暂无订单" style={{ padding: '80px 0' }} />
        ) : (
          filtered.map((order) => (
            <Card
              key={order.id}
              onClick={() => router.push(`/order/${order.id}`)}
              style={{ marginBottom: 12, borderRadius: 12 }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-400">订单号：{order.id}</span>
                <Tag
                  style={{
                    '--background-color': `${statusColor(order.status)}15`,
                    '--text-color': statusColor(order.status),
                    '--border-color': 'transparent',
                    fontSize: 10,
                  }}
                >
                  {order.statusText}
                </Tag>
              </div>
              <div className="flex items-center">
                <div
                  className="w-16 h-16 rounded-lg flex items-center justify-center text-2xl flex-shrink-0"
                  style={{ background: '#f6ffed' }}
                >
                  🏥
                </div>
                <div className="flex-1 ml-3">
                  <div className="font-medium text-sm">{order.title}</div>
                  <div className="text-xs text-gray-400 mt-1">{order.time}</div>
                </div>
                <span className="font-bold text-sm">¥{order.price}</span>
              </div>
              {order.status === 'pending' && (
                <div className="flex justify-end gap-2 mt-3 pt-3 border-t border-gray-50">
                  <Button size="mini" style={{ borderRadius: 16, fontSize: 12 }}>
                    取消订单
                  </Button>
                  <Button
                    size="mini"
                    style={{
                      borderRadius: 16,
                      fontSize: 12,
                      background: '#52c41a',
                      color: '#fff',
                      border: 'none',
                    }}
                  >
                    去支付
                  </Button>
                </div>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
