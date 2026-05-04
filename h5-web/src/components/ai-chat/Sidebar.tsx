'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Avatar, Badge, Dialog, Toast } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';

interface ChatHistoryItem {
  id: string;
  title: string;
  time: string;
  pinned?: boolean;
  lastMessage?: string;
}

interface SidebarProps {
  visible: boolean;
  onClose: () => void;
  activeSessionId?: string | null;
  onSelectSession?: (sessionId: string) => void;
  onNewConversation?: () => void;
}

interface OrderCounts {
  pending_payment: number;
  pending_use: number;
  pending_review: number;
  refund: number;
}

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const t = new Date(iso).getTime();
  const diff = now - t;
  if (diff < 60 * 1000) return '刚刚';
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / 3600000)}小时前`;
  return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

export default function Sidebar({ visible, onClose, activeSessionId, onSelectSession, onNewConversation }: SidebarProps) {
  const router = useRouter();
  const { user } = useAuth();
  const [histories, setHistories] = useState<ChatHistoryItem[]>([]);
  const [orderCounts, setOrderCounts] = useState<OrderCounts>({ pending_payment: 0, pending_use: 0, pending_review: 0, refund: 0 });
  const [msgCount, setMsgCount] = useState(0);
  const [couponCount, setCouponCount] = useState(0);

  useEffect(() => {
    if (!visible) return;
    api.get('/api/chat-sessions').then((res: any) => {
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      setHistories(list.map((s: any) => ({
        id: String(s.id),
        title: s.title || '新对话',
        time: s.updated_at || s.created_at || '',
        pinned: s.is_pinned || false,
        lastMessage: s.last_message || s.preview || '',
      })));
    }).catch(() => {});

    api.get('/api/h5/order-counts').then((res: any) => {
      const data = res.data || res;
      setOrderCounts({
        pending_payment: data.pending_payment || 0,
        pending_use: data.pending_use || 0,
        pending_review: data.pending_review || 0,
        refund: data.refund || 0,
      });
    }).catch(() => {});

    api.get('/api/h5/unread-count').then((res: any) => {
      const data = res.data || res;
      setMsgCount(data.message_count || 0);
      setCouponCount(data.coupon_count || 0);
    }).catch(() => {});
  }, [visible]);

  const groupByTime = (items: ChatHistoryItem[]) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 86400000;
    const week = today - 7 * 86400000;
    const groups: { label: string; items: ChatHistoryItem[] }[] = [
      { label: '今天', items: [] },
      { label: '昨天', items: [] },
      { label: '近7天', items: [] },
      { label: '更早', items: [] },
    ];
    items.forEach(item => {
      const t = new Date(item.time).getTime();
      if (t >= today) groups[0].items.push(item);
      else if (t >= yesterday) groups[1].items.push(item);
      else if (t >= week) groups[2].items.push(item);
      else groups[3].items.push(item);
    });
    return groups.filter(g => g.items.length > 0);
  };

  const navigateTo = (path: string) => {
    onClose();
    router.push(path);
  };

  const handleSelectSession = (id: string) => {
    if (onSelectSession) {
      onSelectSession(id);
    } else {
      navigateTo(`/chat/${id}`);
    }
  };

  const handleNewConversation = () => {
    if (onNewConversation) {
      onNewConversation();
      onClose();
    }
  };

  const handleClearAll = async () => {
    const confirmed = await Dialog.confirm({
      content: '确定清空全部对话记录吗？此操作不可撤销。',
      confirmText: '清空',
      cancelText: '取消',
    });
    if (confirmed) {
      try {
        await api.delete('/api/chat/sessions');
        setHistories([]);
        if (onNewConversation) onNewConversation();
        Toast.show({ content: '已清空全部对话', icon: 'success' });
      } catch {
        Toast.show({ content: '清空失败，请重试' });
      }
    }
  };

  const pinned = histories.filter(h => h.pinned);
  const unpinned = histories.filter(h => !h.pinned);
  const grouped = groupByTime(unpinned);

  return (
    <>
      {visible && (
        <div className="fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={onClose}
          />
          <div
            className="relative h-full overflow-y-auto flex flex-col"
            style={{
              width: '70%',
              maxWidth: 320,
              background: THEME.cardBg,
              animation: 'slideInLeft 0.25s ease-out',
            }}
          >
            {/* User Info */}
            <div className="p-5 pb-3" style={{ background: THEME.primaryLight }}>
              <div className="flex items-center gap-3">
                <Avatar
                  src={user?.avatar || ''}
                  style={{ '--size': '48px', '--border-radius': '50%', background: THEME.primary, color: '#fff', fontSize: 20 }}
                />
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-base truncate" style={{ color: THEME.textPrimary }}>
                    {user?.nickname || '未登录'}
                  </div>
                  {user?.user_no && (
                    <div className="text-xs mt-0.5" style={{ color: THEME.textSecondary }}>
                      VIP会员 {user.user_no}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex gap-6 mt-4">
                <div className="flex items-center gap-1 cursor-pointer" onClick={() => navigateTo('/notifications')}>
                  <Badge content={msgCount > 0 ? msgCount : null}>
                    <span className="text-lg">💬</span>
                  </Badge>
                  <span className="text-xs" style={{ color: THEME.textSecondary }}>消息</span>
                </div>
                <div className="flex items-center gap-1 cursor-pointer" onClick={() => navigateTo('/my-coupons')}>
                  <Badge content={couponCount > 0 ? couponCount : null}>
                    <span className="text-lg">🎫</span>
                  </Badge>
                  <span className="text-xs" style={{ color: THEME.textSecondary }}>优惠券</span>
                </div>
              </div>
            </div>

            {/* Order status bar */}
            <div className="flex justify-around py-3 border-b" style={{ borderColor: THEME.divider }}>
              {[
                { label: '待付款', count: orderCounts.pending_payment, path: '/unified-orders?tab=pending' },
                { label: '待使用', count: orderCounts.pending_use, path: '/unified-orders?tab=paid' },
                { label: '待评价', count: orderCounts.pending_review, path: '/unified-orders?tab=review' },
                { label: '退款', count: orderCounts.refund, path: '/unified-orders?tab=refund' },
              ].map(item => (
                <div
                  key={item.label}
                  className="flex flex-col items-center cursor-pointer"
                  onClick={() => navigateTo(item.path)}
                >
                  <span className="text-base font-bold" style={{ color: item.count > 0 ? THEME.primary : THEME.textSecondary }}>
                    {item.count}
                  </span>
                  <span className="text-xs mt-0.5" style={{ color: THEME.textSecondary }}>{item.label}</span>
                </div>
              ))}
            </div>

            {/* New conversation button */}
            <div className="px-3 pt-3">
              <button
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium active:opacity-80"
                style={{ background: THEME.primary, color: '#fff' }}
                onClick={handleNewConversation}
              >
                <span>＋</span>
                <span>新建对话</span>
              </button>
            </div>

            {/* Chat histories */}
            <div className="flex-1 overflow-y-auto px-3 py-3">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold" style={{ color: THEME.textSecondary }}>历史对话</span>
              </div>

              {pinned.length > 0 && (
                <div className="mb-3">
                  {pinned.map(item => {
                    const isActive = activeSessionId === item.id;
                    return (
                      <div
                        key={item.id}
                        className="flex items-center gap-2 px-3 py-2.5 rounded-xl mb-1 cursor-pointer relative overflow-hidden"
                        style={{ background: isActive ? THEME.primaryLight : THEME.primaryLight }}
                        onClick={() => handleSelectSession(item.id)}
                      >
                        {isActive && (
                          <div className="absolute left-0 top-1 bottom-1 w-1 rounded-r-full" style={{ background: THEME.primary }} />
                        )}
                        <span className="text-xs">📌</span>
                        <div className="flex-1 min-w-0">
                          <span className="text-sm truncate block" style={{ color: THEME.textPrimary }}>
                            {item.title.slice(0, 20)}
                          </span>
                          {item.lastMessage && (
                            <span className="text-xs truncate block mt-0.5" style={{ color: THEME.textSecondary }}>
                              {item.lastMessage.slice(0, 30)}
                            </span>
                          )}
                        </div>
                        <span className="text-xs flex-shrink-0 ml-1" style={{ color: THEME.textSecondary }}>
                          {formatRelativeTime(item.time)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

              {grouped.map(group => (
                <div key={group.label} className="mb-3">
                  <div className="text-xs px-1 mb-1.5" style={{ color: THEME.textSecondary }}>{group.label}</div>
                  {group.items.map(item => {
                    const isActive = activeSessionId === item.id;
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between px-3 py-2.5 rounded-xl mb-1 cursor-pointer hover:bg-gray-50 relative overflow-hidden"
                        style={{ background: isActive ? THEME.primaryLight : 'transparent' }}
                        onClick={() => handleSelectSession(item.id)}
                      >
                        {isActive && (
                          <div className="absolute left-0 top-1 bottom-1 w-1 rounded-r-full" style={{ background: THEME.primary }} />
                        )}
                        <div className="flex-1 min-w-0 pr-2">
                          <span className="text-sm truncate block" style={{ color: THEME.textPrimary }}>
                            {item.title.slice(0, 20)}
                          </span>
                          {item.lastMessage && (
                            <span className="text-xs truncate block mt-0.5" style={{ color: THEME.textSecondary }}>
                              {item.lastMessage.slice(0, 30)}
                            </span>
                          )}
                        </div>
                        <span className="text-xs flex-shrink-0" style={{ color: THEME.textSecondary }}>
                          {formatRelativeTime(item.time)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ))}

              {histories.length === 0 && (
                <div className="text-center py-8 text-sm" style={{ color: THEME.textSecondary }}>
                  暂无历史对话
                </div>
              )}
            </div>

            {/* Bottom */}
            <div className="px-3 pb-2">
              {histories.length > 0 && (
                <button
                  className="w-full flex items-center justify-center gap-1 py-2 rounded-xl text-xs mb-2 active:opacity-70"
                  style={{ background: '#FFF0F0', color: '#FF4D4F' }}
                  onClick={handleClearAll}
                >
                  🗑️ 清空全部对话
                </button>
              )}
            </div>
            <div className="flex items-center justify-between px-4 py-3 border-t" style={{ borderColor: THEME.divider }}>
              <div className="flex items-center gap-1.5 cursor-pointer" onClick={() => navigateTo('/ai-settings')}>
                <span>⚙️</span>
                <span className="text-sm" style={{ color: THEME.textSecondary }}>设置</span>
              </div>
              <div
                className="text-sm cursor-pointer"
                style={{ color: THEME.primary }}
                onClick={() => navigateTo('/chat-history')}
              >
                管理
              </div>
            </div>
          </div>
        </div>
      )}

      <style jsx global>{`
        @keyframes slideInLeft {
          from { transform: translateX(-100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}
