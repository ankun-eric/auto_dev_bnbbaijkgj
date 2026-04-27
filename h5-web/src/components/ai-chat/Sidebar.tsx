'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Avatar, Badge } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';

interface ChatHistoryItem {
  id: string;
  title: string;
  time: string;
  pinned?: boolean;
}

interface SidebarProps {
  visible: boolean;
  onClose: () => void;
}

interface OrderCounts {
  pending_payment: number;
  pending_use: number;
  pending_review: number;
  refund: number;
}

export default function Sidebar({ visible, onClose }: SidebarProps) {
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

              {/* Quick entries */}
              <div className="flex gap-6 mt-4">
                <div className="flex items-center gap-1 cursor-pointer" onClick={() => navigateTo('/notifications')}>
                  <Badge content={msgCount > 0 ? msgCount : null}>
                    <span className="text-lg">💬</span>
                  </Badge>
                  <span className="text-xs" style={{ color: THEME.textSecondary }}>消息</span>
                </div>
                <div className="flex items-center gap-1 cursor-pointer" onClick={() => navigateTo('/coupons')}>
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

            {/* Chat histories */}
            <div className="flex-1 overflow-y-auto px-3 py-3">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold" style={{ color: THEME.textSecondary }}>历史对话</span>
              </div>

              {pinned.length > 0 && (
                <div className="mb-3">
                  {pinned.map(item => (
                    <div
                      key={item.id}
                      className="flex items-center gap-2 px-3 py-2.5 rounded-xl mb-1 cursor-pointer"
                      style={{ background: THEME.primaryLight }}
                      onClick={() => navigateTo(`/chat/${item.id}`)}
                    >
                      <span className="text-xs">📌</span>
                      <span className="text-sm flex-1 truncate" style={{ color: THEME.textPrimary }}>{item.title}</span>
                    </div>
                  ))}
                </div>
              )}

              {grouped.map(group => (
                <div key={group.label} className="mb-3">
                  <div className="text-xs px-1 mb-1.5" style={{ color: THEME.textSecondary }}>{group.label}</div>
                  {group.items.map(item => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between px-3 py-2.5 rounded-xl mb-1 cursor-pointer hover:bg-gray-50"
                      onClick={() => navigateTo(`/chat/${item.id}`)}
                    >
                      <span className="text-sm flex-1 truncate" style={{ color: THEME.textPrimary }}>{item.title}</span>
                      <span className="text-xs flex-shrink-0 ml-2" style={{ color: THEME.textSecondary }}>
                        {new Date(item.time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  ))}
                </div>
              ))}

              {histories.length === 0 && (
                <div className="text-center py-8 text-sm" style={{ color: THEME.textSecondary }}>
                  暂无历史对话
                </div>
              )}
            </div>

            {/* Bottom */}
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
