'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { List, Grid, Badge, Avatar, Tag } from 'antd-mobile';
import {
  RightOutline,
  FileOutline,
  TeamOutline,
  ClockCircleOutline,
  StarOutline,
  BellOutline,
  SetOutline,
  HeartOutline,
  MessageOutline,
} from 'antd-mobile-icons';
import { useAuth } from '@/lib/auth';
import { useFontSize } from '@/lib/useFontSize';
import FontSettingPopup from '@/components/FontSettingPopup';
import api from '@/lib/api';

const orderTabs = [
  { icon: '💳', title: '待支付', badge: '2', path: '/orders?tab=pending' },
  { icon: '📋', title: '待核销', badge: '1', path: '/orders?tab=unused' },
  { icon: '✅', title: '已完成', badge: '', path: '/orders?tab=done' },
  { icon: '📦', title: '全部', badge: '', path: '/orders' },
];

export default function ProfilePage() {
  const router = useRouter();
  const { user } = useAuth();
  const [fontPopupVisible, setFontPopupVisible] = useState(false);
  const [fontConfig, setFontConfig] = useState<{
    font_switch_enabled: boolean;
    font_default_level: 'standard' | 'large' | 'xlarge';
    font_standard_size: number;
    font_large_size: number;
    font_xlarge_size: number;
  }>({
    font_switch_enabled: false,
    font_default_level: 'standard',
    font_standard_size: 14,
    font_large_size: 18,
    font_xlarge_size: 22,
  });

  useEffect(() => {
    api.get('/api/home-config').then((res: unknown) => {
      const data = res as Record<string, unknown>;
      setFontConfig({
        font_switch_enabled: !!data.font_switch_enabled,
        font_default_level: (data.font_default_level as 'standard' | 'large' | 'xlarge') || 'standard',
        font_standard_size: (data.font_standard_size as number) || 14,
        font_large_size: (data.font_large_size as number) || 18,
        font_xlarge_size: (data.font_xlarge_size as number) || 22,
      });
    }).catch(() => {});
  }, []);

  const { fontLevel, setFontLevel } = useFontSize(fontConfig);

  const menuGroups = [
    {
      items: [
        { icon: <FileOutline />, title: '健康档案', path: '/health-profile', color: '#52c41a' },
        { icon: <TeamOutline />, title: '家庭成员', path: '/health-profile', color: '#1890ff' },
        { icon: <ClockCircleOutline />, title: '我的预约', path: '/orders?tab=appointment', color: '#722ed1' },
      ],
    },
    {
      items: [
        { icon: <StarOutline />, title: '积分商城', path: '/points', color: '#fa8c16' },
        { icon: <BellOutline />, title: '消息通知', path: '/notifications', badge: '5', color: '#f5222d' },
        { icon: <MessageOutline />, title: '在线客服', path: '/customer-service', color: '#13c2c2' },
      ],
    },
    {
      items: [
        ...(fontConfig.font_switch_enabled
          ? [{ icon: <HeartOutline />, title: '字体大小', path: '', color: '#fa541c', action: 'font' as const }]
          : []),
        { icon: <SetOutline />, title: '设置', path: '/settings', color: '#8c8c8c' },
      ],
    },
  ];

  return (
    <div className="pb-20">
      <div
        className="px-4 pt-12 pb-6"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="flex items-center" onClick={() => user ? undefined : router.push('/login')}>
          <Avatar
            src=""
            style={{
              '--size': '60px',
              '--border-radius': '50%',
              border: '2px solid rgba(255,255,255,0.5)',
            }}
          />
          <div className="ml-4 text-white">
            <div className="text-lg font-bold">{user?.nickname || '点击登录'}</div>
            <div className="flex items-center mt-1">
              <Tag
                style={{
                  '--background-color': 'rgba(255,255,255,0.2)',
                  '--text-color': '#fff',
                  '--border-color': 'transparent',
                  fontSize: 10,
                }}
              >
                {user?.memberLevel || '普通会员'}
              </Tag>
              <span className="text-xs text-white/70 ml-2">
                积分 {user?.points || 0}
              </span>
            </div>
          </div>
          <RightOutline className="ml-auto text-white/60" />
        </div>

        <div className="grid grid-cols-3 gap-4 mt-6">
          <div className="text-center text-white" onClick={() => router.push('/points')}>
            <div className="text-lg font-bold">{user?.points || 0}</div>
            <div className="text-xs opacity-70">积分</div>
          </div>
          <div className="text-center text-white" onClick={() => router.push('/articles')}>
            <div className="text-lg font-bold">12</div>
            <div className="text-xs opacity-70">收藏</div>
          </div>
          <div className="text-center text-white" onClick={() => router.push('/health-plan')}>
            <div className="text-lg font-bold">7</div>
            <div className="text-xs opacity-70">签到天数</div>
          </div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="font-medium text-sm">我的订单</span>
            <span
              className="text-xs text-gray-400 flex items-center"
              onClick={() => router.push('/orders')}
            >
              全部订单 <RightOutline fontSize={10} />
            </span>
          </div>
          <Grid columns={4} gap={8}>
            {orderTabs.map((tab, i) => (
              <Grid.Item key={i} onClick={() => router.push(tab.path)}>
                <div className="text-center">
                  <Badge content={tab.badge || null}>
                    <span className="text-2xl">{tab.icon}</span>
                  </Badge>
                  <div className="text-xs text-gray-500 mt-1">{tab.title}</div>
                </div>
              </Grid.Item>
            ))}
          </Grid>
        </div>

        {menuGroups.map((group, gi) => (
          <div key={gi} className="card">
            <List style={{ '--border-top': 'none', '--border-bottom': 'none', '--padding-left': '0' }}>
              {group.items.map((item, ii) => (
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
                  onClick={() => {
                    if ('action' in item && item.action === 'font') {
                      setFontPopupVisible(true);
                    } else {
                      router.push(item.path);
                    }
                  }}
                  arrow
                  extra={
                    'badge' in item && item.badge ? (
                      <Badge content={item.badge as string} />
                    ) : undefined
                  }
                >
                  <span className="text-sm">{item.title}</span>
                </List.Item>
              ))}
            </List>
          </div>
        ))}
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
