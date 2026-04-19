'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { List, Badge, SwipeAction, Empty, Button, Toast } from 'antd-mobile';

import GreenNavBar from '@/components/GreenNavBar';
interface Notification {
  id: number;
  title: string;
  content: string;
  time: string;
  read: boolean;
  type: 'system' | 'health' | 'order' | 'activity';
}

const mockNotifications: Notification[] = [
  { id: 1, title: '健康提醒', content: '您今天的步数目标尚未完成，距离8000步还差3200步', time: '10分钟前', read: false, type: 'health' },
  { id: 2, title: '订单通知', content: '您的体检套餐订单已确认，请按预约时间前往', time: '1小时前', read: false, type: 'order' },
  { id: 3, title: '系统通知', content: '宾尼小康V2.0版本更新，新增中医养生功能', time: '昨天', read: false, type: 'system' },
  { id: 4, title: '活动通知', content: '签到7天赢取100积分活动开始啦！', time: '2天前', read: true, type: 'activity' },
  { id: 5, title: '健康报告', content: '您的3月健康报告已生成，点击查看', time: '3天前', read: true, type: 'health' },
];

const typeIcon: Record<string, string> = {
  system: '🔔',
  health: '💚',
  order: '📦',
  activity: '🎉',
};

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>(mockNotifications);

  const markRead = (id: number) => {
    setNotifications(notifications.map((n) => (n.id === id ? { ...n, read: true } : n)));
  };

  const markAllRead = () => {
    setNotifications(notifications.map((n) => ({ ...n, read: true })));
    Toast.show({ content: '已全部标记为已读' });
  };

  const deleteNotification = (id: number) => {
    setNotifications(notifications.filter((n) => n.id !== id));
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar
        right={
          notifications.length > 0 ? (
            <span className="text-white text-sm" onClick={markAllRead}>全部已读</span>
          ) : undefined
        }
      >
        消息通知
      </GreenNavBar>

      <div className="px-4 pt-2">
        {notifications.length === 0 ? (
          <Empty description="暂无消息" style={{ padding: '80px 0' }} />
        ) : (
          <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
            {notifications.map((n) => (
              <SwipeAction
                key={n.id}
                rightActions={[
                  {
                    key: 'delete',
                    text: '删除',
                    color: 'danger',
                    onClick: () => deleteNotification(n.id),
                  },
                ]}
              >
                <List.Item
                  onClick={() => markRead(n.id)}
                  prefix={
                    <Badge content={n.read ? null : Badge.dot} style={{ '--color': '#52c41a' }}>
                      <div className="w-10 h-10 rounded-full bg-gray-50 flex items-center justify-center text-xl">
                        {typeIcon[n.type]}
                      </div>
                    </Badge>
                  }
                  description={
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs text-gray-400 truncate mr-2">{n.content}</span>
                      <span className="text-xs text-gray-300 whitespace-nowrap">{n.time}</span>
                    </div>
                  }
                  style={{ background: n.read ? 'transparent' : '#f6ffed' }}
                >
                  <span className={`text-sm ${n.read ? 'text-gray-500' : 'font-medium'}`}>{n.title}</span>
                </List.Item>
              </SwipeAction>
            ))}
          </List>
        )}
      </div>
    </div>
  );
}
