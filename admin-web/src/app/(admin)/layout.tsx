'use client';

import React, { useState, useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown, Typography, Button, theme } from 'antd';
import {
  DashboardOutlined,
  UserOutlined,
  RobotOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  FileTextOutlined,
  MedicineBoxOutlined,
  GiftOutlined,
  CustomerServiceOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  MessageOutlined,
  MailOutlined,
} from '@ant-design/icons';
import { useRouter, usePathname } from 'next/navigation';
import type { MenuProps } from 'antd';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

type MenuItem = Required<MenuProps>['items'][number];

const menuItems: MenuItem[] = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '数据概览' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
  {
    key: 'merchant',
    icon: <ShopOutlined />,
    label: '商家管理',
    children: [
      { key: '/merchant/stores', label: '门店管理' },
      { key: '/merchant/accounts', label: '商家账号' },
    ],
  },
  { key: '/ai-config', icon: <RobotOutlined />, label: 'AI模型配置' },
  {
    key: 'services',
    icon: <ShopOutlined />,
    label: '服务管理',
    children: [
      { key: '/services/categories', label: '服务分类' },
      { key: '/services/items', label: '服务项目' },
    ],
  },
  { key: '/orders', icon: <ShoppingCartOutlined />, label: '订单管理' },
  {
    key: 'content',
    icon: <FileTextOutlined />,
    label: '内容管理',
    children: [
      { key: '/content/articles', label: '文章管理' },
      { key: '/content/videos', label: '视频管理' },
    ],
  },
  { key: '/experts', icon: <MedicineBoxOutlined />, label: '专家管理' },
  {
    key: 'points',
    icon: <GiftOutlined />,
    label: '积分体系',
    children: [
      { key: '/points/rules', label: '积分规则' },
      { key: '/points/mall', label: '积分商城' },
      { key: '/points/levels', label: '会员等级' },
    ],
  },
  { key: '/customer-service', icon: <CustomerServiceOutlined />, label: '客服工作台' },
  {
    key: 'system',
    icon: <SettingOutlined />,
    label: '系统管理',
    children: [
      { key: '/settings', label: '系统设置' },
      { key: '/sms', label: '短信管理' },
      { key: '/wechat-push', icon: <MessageOutlined />, label: '微信推送管理' },
      { key: '/email-notify', icon: <MailOutlined />, label: '邮件通知管理' },
    ],
  },
];

function getOpenKeys(pathname: string): string[] {
  if (pathname.startsWith('/services')) return ['services'];
  if (pathname.startsWith('/merchant')) return ['merchant'];
  if (pathname.startsWith('/content')) return ['content'];
  if (pathname.startsWith('/points')) return ['points'];
  if (pathname.startsWith('/sms') || pathname.startsWith('/settings') || pathname.startsWith('/wechat-push') || pathname.startsWith('/email-notify')) return ['system'];
  return [];
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [adminUser, setAdminUser] = useState<any>({ name: '管理员' });
  const router = useRouter();
  const pathname = usePathname();
  const { token } = theme.useToken();

  useEffect(() => {
    const stored = localStorage.getItem('admin_user');
    if (stored) {
      try {
        setAdminUser(JSON.parse(stored));
      } catch {}
    }
  }, []);

  const handleMenuClick = (info: { key: string }) => {
    router.push(info.key);
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    router.push('/login');
  };

  const dropdownItems: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={240}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid #f0f0f0',
            gap: 8,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <MedicineBoxOutlined style={{ fontSize: 18, color: '#fff' }} />
          </div>
          {!collapsed && (
            <Text strong style={{ fontSize: 16, color: '#333', whiteSpace: 'nowrap' }}>
              宾尼小康
            </Text>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[pathname]}
          defaultOpenKeys={getOpenKeys(pathname)}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ border: 'none', padding: '8px 0' }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 240, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f0f0f0',
            height: 64,
            position: 'sticky',
            top: 0,
            zIndex: 99,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 18, width: 48, height: 48 }}
          />
          <Dropdown menu={{ items: dropdownItems }} placement="bottomRight">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <Avatar
                style={{
                  backgroundColor: token.colorPrimary,
                }}
                icon={<UserOutlined />}
              />
              <Text>{adminUser?.name || adminUser?.nickname || '管理员'}</Text>
            </div>
          </Dropdown>
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: '#fff',
            borderRadius: 12,
            minHeight: 'calc(100vh - 112px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
