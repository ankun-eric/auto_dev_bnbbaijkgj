'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { List, Grid, Badge, Avatar, Tag, Toast } from 'antd-mobile';
import {
  RightOutline,
  SetOutline,
  MessageOutline,
  TeamOutline,
  EnvironmentOutline,
  EditSOutline,
} from 'antd-mobile-icons';
import { useAuth } from '@/lib/auth';
import { useFontSize } from '@/lib/useFontSize';
import FontSettingPopup from '@/components/FontSettingPopup';
import api from '@/lib/api';

// PRD「我的订单与售后状态体系优化」F-01/F-02：第 4 个图标改为「已完成」
// 第 5 个图标文案保持「退款/售后」，跳转目标仍为独立列表页
const orderQuickTabs = [
  { icon: '💳', title: '待付款', key: 'pending_payment', path: '/unified-orders?tab=pending_payment' },
  { icon: '📦', title: '待收货', key: 'pending_receipt', path: '/unified-orders?tab=pending_receipt' },
  { icon: '🎫', title: '待使用', key: 'pending_use', path: '/unified-orders?tab=pending_use' },
  // F-01：「待评价」 → 「已完成」；红点逻辑改为"未评价的已完成订单数"
  { icon: '✅', title: '已完成', key: 'completed_pending_review', path: '/unified-orders?tab=completed' },
  // F-02：保持文案「退款/售后」，跳转独立列表页
  { icon: '↩️', title: '退款/售后', key: 'refund', path: '/refund-list' },
];

interface MyStats {
  points: number;
  coupon_count: number;
  favorite_count: number;
}

export default function ProfilePage() {
  const router = useRouter();
  const { user } = useAuth();
  const [orderCounts, setOrderCounts] = useState<Record<string, number>>({});
  const [stats, setStats] = useState<MyStats>({ points: 0, coupon_count: 0, favorite_count: 0 });
  const [fontPopupVisible, setFontPopupVisible] = useState(false);
  const [fontConfig, setFontConfig] = useState<{
    font_switch_enabled: boolean;
    font_default_level: 'standard' | 'large' | 'xlarge';
    font_standard_size: number;
    font_large_size: number;
    font_xlarge_size: number;
  }>({
    font_switch_enabled: true,
    font_default_level: 'standard',
    font_standard_size: 16,
    font_large_size: 19,
    font_xlarge_size: 22,
  });
  const { fontLevel, setFontLevel } = useFontSize(fontConfig);

  const loadStats = () => {
    api.get('/api/users/me/stats')
      .then((res: any) => {
        const data = res.data || res;
        setStats({
          points: Number(data.points || 0),
          coupon_count: Number(data.coupon_count || 0),
          favorite_count: Number(data.favorite_count || 0),
        });
      })
      .catch(() => {});

    // Bug#3 / Bug#4：入口"积分"与"优惠券"数字与各详情页同源
    //   积分    → /api/points/summary.available_points（可用积分）
    //   优惠券  → /api/coupons/summary.available_count（可用券总数）
    // 后端新字段就绪后覆盖 me/stats 的旧值；未就绪则保持 me/stats
    api.get('/api/points/summary')
      .then((res: any) => {
        const d = res?.data || res || {};
        const pts = d.available_points ?? d.total_points;
        if (typeof pts === 'number') {
          setStats((prev) => ({ ...prev, points: Number(pts) }));
        }
      })
      .catch(() => {});
    api.get('/api/coupons/summary')
      .then((res: any) => {
        const d = res?.data || res || {};
        if (typeof d.available_count === 'number') {
          setStats((prev) => ({ ...prev, coupon_count: Number(d.available_count) }));
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    api.get('/api/orders/unified/counts')
      .then((res: any) => {
        const data = res.data || res;
        // F-01：第 4 个图标的红点 = 未评价的已完成订单数（pending_review）
        // 兼容老字段：counts.pending_review 即"completed AND has_reviewed=false"
        setOrderCounts({
          ...data,
          completed_pending_review: data.pending_review || 0,
        });
      })
      .catch(() => {});
    loadStats();
    api.get('/api/home-config').then((res: unknown) => {
      const data = res as Record<string, unknown>;
      setFontConfig({
        font_switch_enabled: data.font_switch_enabled !== false,
        font_default_level: (data.font_default_level as 'standard' | 'large' | 'xlarge') || 'standard',
        font_standard_size: (data.font_standard_size as number) || 16,
        font_large_size: (data.font_large_size as number) || 19,
        font_xlarge_size: (data.font_xlarge_size as number) || 22,
      });
    }).catch(() => {});
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') loadStats();
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

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
        className="px-4 pb-4"
        style={{
          paddingTop: 32,
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
        }}
      >
        <div className="flex items-center">
          <div onClick={() => user ? router.push('/profile/edit') : router.push('/login')}>
            <Avatar
              src={user?.avatar || ''}
              style={{
                '--size': '60px',
                '--border-radius': '50%',
                border: '2px solid rgba(255,255,255,0.5)',
              }}
            />
          </div>
          <div className="ml-4 flex-1 text-white">
            <div className="flex items-center">
              <span
                className="text-lg font-bold"
                onClick={() => user ? router.push('/profile/edit') : router.push('/login')}
              >
                {user?.nickname || '点击登录'}
              </span>
              {user && (
                <EditSOutline
                  fontSize={14}
                  className="ml-1 cursor-pointer"
                  style={{ color: 'rgba(255,255,255,0.8)' }}
                  onClick={() => router.push('/profile/edit')}
                />
              )}
            </div>
            {user && (
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.7)', marginTop: 2 }}>
                会员号：{user.user_no || user.id}
              </div>
            )}
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
            className="flex flex-col items-center cursor-pointer"
            onClick={() => router.push('/member-card')}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="3" y="3" width="8" height="8" rx="1" stroke="white" strokeWidth="1.5" />
              <rect x="13" y="3" width="8" height="8" rx="1" stroke="white" strokeWidth="1.5" />
              <rect x="3" y="13" width="8" height="8" rx="1" stroke="white" strokeWidth="1.5" />
              <rect x="15" y="15" width="4" height="4" rx="0.5" stroke="white" strokeWidth="1.5" />
              <line x1="17" y1="13" x2="17" y2="14.5" stroke="white" strokeWidth="1.5" />
              <line x1="13" y1="17" x2="14.5" y2="17" stroke="white" strokeWidth="1.5" />
              <rect x="5" y="5" width="4" height="4" rx="0.5" fill="white" />
              <rect x="15" y="5" width="4" height="4" rx="0.5" fill="white" />
              <rect x="5" y="15" width="4" height="4" rx="0.5" fill="white" />
            </svg>
            <span className="text-white text-xs mt-1" style={{ fontSize: 10 }}>会员码</span>
          </div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <div className="card">
          <Grid columns={3} gap={0}>
            <Grid.Item onClick={() => router.push('/points')}>
              <div className="text-center py-2">
                <div className="text-lg font-bold" style={{ color: '#52c41a' }}>{stats.points}</div>
                <div className="text-xs text-gray-500 mt-1">积分</div>
              </div>
            </Grid.Item>
            <Grid.Item onClick={() => router.push('/my-coupons')}>
              <div className="text-center py-2">
                <div className="text-lg font-bold" style={{ color: '#fa8c16' }}>{stats.coupon_count}</div>
                <div className="text-xs text-gray-500 mt-1">优惠券</div>
              </div>
            </Grid.Item>
            <Grid.Item onClick={() => router.push('/my-favorites')}>
              <div className="text-center py-2">
                <div className="text-lg font-bold" style={{ color: '#f5222d' }}>{stats.favorite_count}</div>
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
                  <Badge content={orderCounts[tab.key] || null} style={{ '--right': '-2px', '--top': '-2px' }}>
                    <span className="text-2xl">{tab.icon}</span>
                  </Badge>
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

      <FontSettingPopup
        visible={fontPopupVisible}
        onClose={() => setFontPopupVisible(false)}
        fontLevel={fontLevel}
        onFontLevelChange={setFontLevel}
        standardSize={fontConfig.font_standard_size}
        largeSize={fontConfig.font_large_size}
        xlargeSize={fontConfig.font_xlarge_size}
      />
    </div>
  );
}
