'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, List, Badge, SwipeAction, Empty, Button, Toast, InfiniteScroll, PullToRefresh } from 'antd-mobile';
import dayjs from 'dayjs';
import api from '@/lib/api';

interface NotificationItem {
  id: number;
  message_type: string;
  title: string;
  content: string | null;
  is_read: boolean;
  click_action?: string | null;
  click_action_params?: Record<string, unknown> | null;
  sender_nickname?: string | null;
  created_at: string;
}

const typeConfig: Record<string, { icon: string; color: string }> = {
  system: { icon: '🔔', color: '#1890ff' },
  health_alert: { icon: '💚', color: '#52c41a' },
  family_invite: { icon: '👨‍👩‍👧', color: '#52c41a' },
  family_invite_accepted: { icon: '✅', color: '#52c41a' },
  family_invite_rejected: { icon: '❌', color: '#fa8c16' },
  family_auth_granted: { icon: '🔓', color: '#52c41a' },
  family_auth_rejected: { icon: '🔒', color: '#fa8c16' },
  medication_remind: { icon: '💊', color: '#1890ff' },
};

function formatTime(dateStr: string) {
  const d = dayjs(dateStr);
  const now = dayjs();
  if (now.diff(d, 'minute') < 1) return '刚刚';
  if (now.diff(d, 'hour') < 1) return `${now.diff(d, 'minute')}分钟前`;
  if (now.diff(d, 'hour') < 24) return `${now.diff(d, 'hour')}小时前`;
  if (now.diff(d, 'day') < 7) return `${now.diff(d, 'day')}天前`;
  return d.format('MM-DD HH:mm');
}

export default function MessagesPage() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const PAGE_SIZE = 20;

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res: any = await api.get('/api/messages/unread-count');
      const data = res.data || res;
      setUnreadCount(data.unread_count ?? 0);
    } catch { /* ignore */ }
  }, []);

  const fetchMessages = useCallback(async (pageNum: number, reset = false) => {
    try {
      const res: any = await api.get('/api/messages', {
        params: { page: pageNum, page_size: PAGE_SIZE },
      });
      const data = res.data || res;
      const list: NotificationItem[] = data.items || [];
      const t = data.total || 0;

      if (reset) {
        setItems(list);
      } else {
        setItems((prev) => [...prev, ...list]);
      }
      setTotal(t);
      setPage(pageNum);
      setHasMore(pageNum * PAGE_SIZE < t);
    } catch {
      Toast.show({ content: '加载消息失败', icon: 'fail' });
      setHasMore(false);
    }
  }, []);

  useEffect(() => {
    fetchMessages(1, true);
    fetchUnreadCount();
  }, [fetchMessages, fetchUnreadCount]);

  const loadMore = async () => {
    await fetchMessages(page + 1);
  };

  const handleRefresh = async () => {
    await fetchMessages(1, true);
  };

  const markRead = async (item: NotificationItem) => {
    if (!item.is_read) {
      try {
        await api.put(`/api/messages/${item.id}/read`);
        setItems((prev) =>
          prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)),
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch { /* ignore */ }
    }

    const msgType = item.message_type;

    if (msgType === 'family_invite_accepted' || msgType === 'family_auth_granted') {
      router.push('/family-bindlist');
      return;
    }

    if (msgType === 'family_invite_rejected' || msgType === 'family_auth_rejected') {
      Toast.show({
        content: item.content || '对方已拒绝邀请',
        duration: 3000,
      });
      return;
    }
  };

  const markAllRead = async () => {
    try {
      await api.put('/api/messages/read-all');
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
      Toast.show({ content: '已全部标记为已读', icon: 'success' });
    } catch {
      Toast.show({ content: '操作失败', icon: 'fail' });
    }
  };

  const handleReinvite = (item: NotificationItem) => {
    const params = item.click_action_params as Record<string, string> | undefined;
    const memberId = params?.member_id;
    if (memberId) {
      router.push(`/family-invite?member_id=${memberId}`);
    } else {
      router.push('/family-bindlist');
    }
  };

  const isRejectMessage = (item: NotificationItem) => {
    return item.message_type === 'family_invite_rejected' || item.message_type === 'family_auth_rejected';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar
        onBack={() => router.back()}
        right={
          unreadCount > 0 ? (
            <span
              className="text-xs cursor-pointer"
              style={{ color: '#52c41a' }}
              onClick={markAllRead}
            >
              全部已读
            </span>
          ) : undefined
        }
        style={{ background: '#fff' }}
      >
        消息中心
      </NavBar>

      <PullToRefresh onRefresh={handleRefresh}>
        <div className="px-4 pt-2 pb-20">
          {items.length === 0 && !hasMore ? (
            <Empty description="暂无消息" style={{ padding: '80px 0' }} />
          ) : (
            <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
              {items.map((n) => {
                const cfg = typeConfig[n.message_type] || typeConfig.system;
                return (
                  <SwipeAction
                    key={n.id}
                    rightActions={[
                      {
                        key: 'read',
                        text: n.is_read ? '已读' : '标已读',
                        color: 'primary',
                        onClick: () => {
                          if (!n.is_read) {
                            api.put(`/api/messages/${n.id}/read`);
                            setItems((prev) =>
                              prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)),
                            );
                            setUnreadCount((c) => Math.max(0, c - 1));
                          }
                        },
                      },
                    ]}
                  >
                    <List.Item
                      onClick={() => markRead(n)}
                      prefix={
                        <Badge content={n.is_read ? null : Badge.dot} style={{ '--color': '#52c41a' }}>
                          <div
                            className="w-10 h-10 rounded-full flex items-center justify-center text-xl"
                            style={{ background: `${cfg.color}15` }}
                          >
                            {cfg.icon}
                          </div>
                        </Badge>
                      }
                      description={
                        <div className="mt-1">
                          <div className="text-xs text-gray-400 truncate">{n.content || ''}</div>
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-xs text-gray-300">{formatTime(n.created_at)}</span>
                            {isRejectMessage(n) && (
                              <Button
                                size="mini"
                                style={{
                                  borderRadius: 12,
                                  fontSize: 10,
                                  color: '#52c41a',
                                  borderColor: '#52c41a',
                                  padding: '0 8px',
                                  height: 22,
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleReinvite(n);
                                }}
                              >
                                重新邀请
                              </Button>
                            )}
                          </div>
                        </div>
                      }
                      style={{
                        background: n.is_read ? 'transparent' : '#f6ffed',
                        borderRadius: 8,
                        marginBottom: 4,
                      }}
                    >
                      <span className={`text-sm ${n.is_read ? 'text-gray-500' : 'font-medium text-gray-800'}`}>
                        {n.title}
                      </span>
                    </List.Item>
                  </SwipeAction>
                );
              })}
            </List>
          )}
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        </div>
      </PullToRefresh>
    </div>
  );
}
