'use client';

import { useRouter } from 'next/navigation';
import { List, Grid, Badge, Avatar, Tag, Toast } from 'antd-mobile';
import {
  RightOutline,
  SetOutline,
  MessageOutline,
  TeamOutline,
  EnvironmentOutline,
} from 'antd-mobile-icons';
import { useAuth } from '@/lib/auth';

const orderQuickTabs = [
  { icon: '💳', title: '待付款', path: '/unified-orders?tab=pending_payment' },
  { icon: '📦', title: '待收货', path: '/unified-orders?tab=pending_receipt' },
  { icon: '🎫', title: '待使用', path: '/unified-orders?tab=pending_use' },
  { icon: '⭐', title: '待评价', path: '/unified-orders?tab=pending_review' },
  { icon: '↩️', title: '退款售后', path: '/unified-orders?tab=refund' },
];

export default function ProfilePage() {
  const router = useRouter();
  const { user } = useAuth();

  const menuItems = [
    { icon: <TeamOutline />, title: '家庭关联', path: '/family-bindlist', color: '#52c41a' },
    { icon: <EnvironmentOutline />, title: '我的地址', path: '/my-addresses', color: '#1890ff' },
    { icon: <MessageOutline />, title: '在线客服', path: '/customer-service', color: '#13c2c2' },
    { icon: <span>🎁</span>, title: '邀请好友', path: '/invite', color: '#fa541c' },
    { icon: <SetOutline />, title: '设置', path: '/settings', color: '#8c8c8c' },
  ];

  return (
    <div className="pb-20">
      <div
        className="px-4 pt-12 pb-6"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="flex items-center">
          <div onClick={() => user ? undefined : router.push('/login')}>
            <Avatar
              src={user?.avatar || ''}
              style={{
                '--size': '60px',
                '--border-radius': '50%',
                border: '2px solid rgba(255,255,255,0.5)',
              }}
            />
          </div>
          <div className="ml-4 flex-1 text-white" onClick={() => user ? undefined : router.push('/login')}>
            <div className="text-lg font-bold">{user?.nickname || '点击登录'}</div>
            {user?.memberLevel && (
              <Tag
                style={{
                  '--background-color': 'rgba(255,255,255,0.2)',
                  '--text-color': '#fff',
                  '--border-color': 'transparent',
                  fontSize: 10,
                  marginTop: 4,
                }}
              >
                {user.memberLevel}
              </Tag>
            )}
          </div>
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center bg-white/20 cursor-pointer"
            onClick={() => router.push('/member-card')}
          >
            <span className="text-white text-lg">📇</span>
          </div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <div className="card">
          <Grid columns={3} gap={0}>
            <Grid.Item onClick={() => router.push('/points')}>
              <div className="text-center py-2">
                <div className="text-lg font-bold" style={{ color: '#52c41a' }}>{user?.points || 0}</div>
                <div className="text-xs text-gray-500 mt-1">积分</div>
              </div>
            </Grid.Item>
            <Grid.Item onClick={() => router.push('/my-coupons')}>
              <div className="text-center py-2">
                <div className="text-lg font-bold" style={{ color: '#fa8c16' }}>-</div>
                <div className="text-xs text-gray-500 mt-1">优惠券</div>
              </div>
            </Grid.Item>
            <Grid.Item onClick={() => router.push('/my-favorites')}>
              <div className="text-center py-2">
                <div className="text-lg font-bold" style={{ color: '#f5222d' }}>-</div>
                <div className="text-xs text-gray-500 mt-1">收藏</div>
              </div>
            </Grid.Item>
          </Grid>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="font-medium text-sm">我的订单</span>
            <span
              className="text-xs text-gray-400 flex items-center"
              onClick={() => router.push('/unified-orders')}
            >
              全部订单 <RightOutline fontSize={10} />
            </span>
          </div>
          <Grid columns={5} gap={8}>
            {orderQuickTabs.map((tab, i) => (
              <Grid.Item key={i} onClick={() => router.push(tab.path)}>
                <div className="text-center">
                  <span className="text-2xl">{tab.icon}</span>
                  <div className="text-xs text-gray-500 mt-1">{tab.title}</div>
                </div>
              </Grid.Item>
            ))}
          </Grid>
        </div>

        <div className="card">
          <List style={{ '--border-top': 'none', '--border-bottom': 'none', '--padding-left': '0' }}>
            {menuItems.map((item, ii) => (
              <List.Item
                key={ii}
                prefix={
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{ background: `${item.color}15`, color: item.color }}
                  >
                    {item.icon}
                  </div>
                }
                onClick={() => router.push(item.path)}
                arrow
              >
                <span className="text-sm">{item.title}</span>
              </List.Item>
            ))}
          </List>
        </div>
      </div>
    </div>
  );
}
