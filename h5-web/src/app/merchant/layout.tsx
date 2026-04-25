'use client';

import React, { useEffect, useState } from 'react';
import { ConfigProvider, Layout, Menu, Avatar, Dropdown, Typography, Space, Select, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import {
  DashboardOutlined,
  ShoppingCartOutlined,
  ScanOutlined,
  BarChartOutlined,
  AccountBookOutlined,
  FileTextOutlined,
  TeamOutlined,
  ShopOutlined,
  DownloadOutlined,
  MessageOutlined,
  LogoutOutlined,
  UserOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { usePathname, useRouter } from 'next/navigation';
import { getProfile, logoutMerchant, isAuthed, canAccess, roleLabel, setCurrentStoreId, getCurrentStoreId, MerchantLoginProfile } from './lib';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const allMenu = [
  { key: 'dashboard', path: '/merchant/dashboard', icon: <DashboardOutlined />, label: '工作台' },
  { key: 'orders', path: '/merchant/orders', icon: <ShoppingCartOutlined />, label: '订单管理' },
  { key: 'verifications', path: '/merchant/verifications', icon: <ScanOutlined />, label: '核销记录' },
  { key: 'reports', path: '/merchant/reports', icon: <BarChartOutlined />, label: '报表分析' },
  { key: 'settlement', path: '/merchant/settlement', icon: <AccountBookOutlined />, label: '对账结算' },
  { key: 'invoice', path: '/merchant/invoice', icon: <FileTextOutlined />, label: '发票信息' },
  { key: 'finance', path: '/merchant/finance', icon: <AccountBookOutlined />, label: '财务对账' },
  { key: 'staff', path: '/merchant/staff', icon: <TeamOutlined />, label: '员工管理' },
  { key: 'store-settings', path: '/merchant/store-settings', icon: <ShopOutlined />, label: '门店设置' },
  { key: 'downloads', path: '/merchant/downloads', icon: <DownloadOutlined />, label: '下载中心' },
  { key: 'messages', path: '/merchant/messages', icon: <MessageOutlined />, label: '消息中心' },
];

export default function MerchantLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || '';
  const router = useRouter();
  const [profile, setProfile] = useState<MerchantLoginProfile | null>(null);
  const [currentStore, setCurrentStore] = useState<number | null>(null);

  // [2026-04-25] Bug 修复：path 一旦命中 /merchant/m/ 就完全由移动版 layout 处理，
  // PC 版 layout 不介入鉴权/跳转，避免 /merchant/m/login 被 PC 版守卫重定向到 /merchant/login。
  const isMobilePath =
    pathname.includes('/merchant/m/') || pathname.endsWith('/merchant/m');

  // [2026-04-25] Bug 修复：PC 版登录/找回密码/选店等页面加入白名单，不要求登录态。
  const isLoginOrSelect =
    pathname.endsWith('/merchant/login') ||
    pathname.endsWith('/merchant/login/') ||
    pathname.endsWith('/merchant/forgot-password') ||
    pathname.endsWith('/merchant/forgot-password/') ||
    pathname.endsWith('/merchant/register') ||
    pathname.endsWith('/merchant/register/') ||
    pathname.endsWith('/merchant/select-store') ||
    pathname.endsWith('/merchant/select-store/');

  // [2026-04-24] 移动端 UA 自动重定向到 /merchant/m/*
  useEffect(() => {
    if (typeof window === 'undefined') return;
    // 已经在 /merchant/m/ 下则不处理
    if (isMobilePath) return;
    const url = new URL(window.location.href);
    if (url.searchParams.get('desktop') === '1') return;
    const ua = navigator.userAgent.toLowerCase();
    const isMobile = /iphone|ipod|ipad|android|mobile/.test(ua);
    if (!isMobile) return;
    // 映射：/merchant/xxx -> /merchant/m/xxx（按 basePath 处理）
    // url.pathname 已包含 basePath（如 /autodev/xxx/merchant/login）
    const merchantIdx = url.pathname.indexOf('/merchant/');
    if (merchantIdx < 0) return;
    const tail = url.pathname.substring(merchantIdx + '/merchant/'.length); // e.g. 'login' or 'dashboard/'
    url.pathname = url.pathname.substring(0, merchantIdx) + '/merchant/m/' + tail;
    window.location.replace(url.toString());
  }, [pathname, isMobilePath]);

  useEffect(() => {
    // 移动端路径由 /merchant/m/layout.tsx 处理，PC 版 layout 不介入
    if (isMobilePath) return;
    if (isLoginOrSelect) return;
    if (!isAuthed()) {
      router.replace('/merchant/login');
      return;
    }
    setProfile(getProfile());
    setCurrentStore(getCurrentStoreId());
  }, [isLoginOrSelect, isMobilePath, router]);

  // 移动端路径：直接透传子组件，由 /merchant/m/layout.tsx 渲染，PC 版 layout 不添加任何 UI
  if (isMobilePath) {
    return (
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: { colorPrimary: '#52c41a', borderRadius: 8 },
        }}
      >
        <AntdApp>{children}</AntdApp>
      </ConfigProvider>
    );
  }

  if (isLoginOrSelect) {
    return (
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: { colorPrimary: '#52c41a', borderRadius: 8 },
        }}
      >
        <AntdApp>{children}</AntdApp>
      </ConfigProvider>
    );
  }

  const menuItems = allMenu
    .filter(m => canAccess(profile?.role, m.key))
    .map(m => ({ key: m.path, icon: m.icon, label: m.label }));

  const selectedKey = menuItems.find(m => pathname.startsWith(m.key))?.key || '/merchant/dashboard';

  const handleSwitchStore = (storeId: number) => {
    setCurrentStoreId(storeId);
    setCurrentStore(storeId);
    window.location.reload();
  };

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: { colorPrimary: '#52c41a', borderRadius: 8 },
      }}
    >
      <AntdApp>
        <Layout style={{ minHeight: '100vh' }}>
          <Sider width={220} theme="light" style={{ borderRight: '1px solid #f0f0f0' }}>
            <div
              style={{
                height: 64,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: 16,
                color: '#52c41a',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              商家/机构工作台
            </div>
            <Menu
              mode="inline"
              selectedKeys={[selectedKey]}
              items={menuItems}
              onClick={({ key }) => router.push(key as string)}
              style={{ border: 'none' }}
            />
          </Sider>
          <Layout>
            <Header
              style={{
                background: '#fff',
                padding: '0 24px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <Space>
                <Text strong>{profile?.merchant_name || '商家'}</Text>
                {profile && profile.stores.length > 1 && (
                  <Select
                    size="small"
                    style={{ width: 180 }}
                    value={currentStore ?? undefined}
                    placeholder="选择门店"
                    options={profile.stores.map(s => ({ label: s.name, value: s.id }))}
                    onChange={handleSwitchStore}
                  />
                )}
                {profile && profile.stores.length === 1 && (
                  <Text type="secondary">· {profile.stores[0].name}</Text>
                )}
              </Space>
              <Dropdown
                menu={{
                  items: [
                    {
                      key: 'profile',
                      icon: <UserOutlined />,
                      label: '个人信息',
                      onClick: () => router.push('/merchant/profile'),
                    },
                    {
                      key: 'change-password',
                      icon: <LockOutlined />,
                      label: '修改密码',
                      onClick: () => router.push('/merchant/profile/change-password'),
                    },
                    { type: 'divider' as const },
                    {
                      key: 'logout',
                      icon: <LogoutOutlined />,
                      label: '退出登录',
                      onClick: logoutMerchant,
                    },
                  ],
                }}
              >
                <Space style={{ cursor: 'pointer' }}>
                  <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#52c41a' }} />
                  <Text>{profile ? roleLabel[profile.role] || profile.role : ''}</Text>
                </Space>
              </Dropdown>
            </Header>
            <Content style={{ padding: 24, background: '#f5f5f5' }}>
              <div style={{ background: '#fff', padding: 24, borderRadius: 8, minHeight: 'calc(100vh - 112px)' }}>
                {children}
              </div>
            </Content>
          </Layout>
        </Layout>
      </AntdApp>
    </ConfigProvider>
  );
}
