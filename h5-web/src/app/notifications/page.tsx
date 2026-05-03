'use client';

/**
 * [订单系统增强 PRD v1.0 F7/F8] H5 站内消息中心。
 *
 * 对接后端：
 * - GET /api/notifications：消息列表
 * - GET /api/notifications/unread-count：红点
 * - POST /api/notifications/mark-read-by-order：按订单清除红点
 * - PUT /api/notifications/read-all：全部已读
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { List, Empty, PullToRefresh, Toast, Tag } from 'antd-mobile';
import api from '@/lib/api';
import GreenNavBar from '@/components/GreenNavBar';

interface NotificationItem {
  id: number;
  user_id: number;
  order_id: number | null;
  event_type: string | null;
  title: string;
  content: string | null;
  type: string;
  is_read: boolean;
  extra_data?: any;
  created_at: string;
}

const EVENT_LABELS: Record<string, { label: string; color: string }> = {
  order_status_changed: { label: '状态变更', color: 'primary' },
  order_attachment_added: { label: '附件', color: 'success' },
  order_upcoming: { label: '即将开始', color: 'warning' },
  order_created: { label: '下单', color: 'default' },
  order_paid: { label: '付款', color: 'default' },
  order_cancelled: { label: '取消', color: 'default' },
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = (now - d.getTime()) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`;
    return d.toLocaleDateString('zh-CN');
  } catch {
    return iso;
  }
}

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/api/notifications', { params: { page: 1, page_size: 50 } });
      setItems(resp.data.items || []);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const markAllRead = async () => {
    try {
      await api.put('/api/notifications/read-all');
      Toast.show({ content: '已全部标记为已读' });
      await load();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '操作失败' });
    }
  };

  const handleClick = async (n: NotificationItem) => {
    // 按订单清除红点
    if (n.order_id) {
      try {
        await api.post('/api/notifications/mark-read-by-order', { order_id: n.order_id });
      } catch {}
      router.push(`/unified-order/${n.order_id}`);
    } else {
      try {
        await api.put(`/api/notifications/${n.id}/read`);
      } catch {}
      await load();
    }
  };

  const unreadCount = items.filter((n) => !n.is_read).length;

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar
        right={
          unreadCount > 0 ? (
            <span className="text-white text-sm" onClick={markAllRead}>
              全部已读
            </span>
          ) : undefined
        }
      >
        消息通知
      </GreenNavBar>

      <PullToRefresh onRefresh={load}>
        <div className="px-4 pt-2 pb-6">
          {!loading && items.length === 0 ? (
            <Empty description="暂无消息" style={{ padding: '80px 0' }} />
          ) : (
            <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
              {items.map((n) => {
                const evt = n.event_type ? EVENT_LABELS[n.event_type] : null;
                return (
                  <List.Item
                    key={n.id}
                    onClick={() => handleClick(n)}
                    description={
                      <div className="flex items-center mt-1 text-xs text-gray-500">
                        <span>{formatTime(n.created_at)}</span>
                        {evt && (
                          <Tag color={evt.color} fill="outline" className="ml-2">
                            {evt.label}
                          </Tag>
                        )}
                        {n.order_id && (
                          <span className="ml-2 text-blue-500">#订单 {n.order_id}</span>
                        )}
                      </div>
                    }
                    className={`mb-2 rounded-lg shadow-sm bg-white ${!n.is_read ? 'border-l-4 border-green-500' : ''}`}
                  >
                    <div className="font-medium text-gray-900">
                      {!n.is_read && <span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-2 align-middle" />}
                      {n.title}
                    </div>
                    {n.content && <div className="text-sm text-gray-600 mt-1">{n.content}</div>}
                  </List.Item>
                );
              })}
            </List>
          )}
        </div>
      </PullToRefresh>
    </div>
  );
}
