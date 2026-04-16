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
  BookOutlined,
  SearchOutlined,
  CloudOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  FormOutlined,
  HomeOutlined,
  HeartOutlined,
  ScheduleOutlined,
  EnvironmentOutlined,
  PhoneOutlined,
  TeamOutlined,
  SoundOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { useRouter, usePathname } from 'next/navigation';
import type { MenuProps } from 'antd';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

type MenuItem = Required<MenuProps>['items'][number];

const menuItems: MenuItem[] = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '数据概览' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
  { key: '/referral', icon: <TeamOutlined />, label: '推荐管理' },
  {
    key: 'merchant',
    icon: <ShopOutlined />,
    label: '商家管理',
    children: [
      { key: '/merchant/stores', label: '门店管理' },
      { key: '/merchant/accounts', label: '商家账号' },
    ],
  },
  {
    key: 'ai',
    icon: <RobotOutlined />,
    label: 'AI管理',
    children: [
      { key: '/ai-config', label: 'AI模型配置' },
      { key: '/chat-records', label: 'AI对话记录' },
      { key: '/knowledge', label: '知识库管理' },
      { key: '/search-config', label: '检索策略配置' },
      { key: '/fallback-config', label: '兜底策略配置' },
      { key: '/ocr-config', label: 'OCR识别配置' },
      { key: '/ocr-global-config', label: 'OCR全局设置' },
      { key: '/checkup-details', label: '体检报告解读明细' },
      { key: '/drug-details', label: '拍照识药记录明细' },
    ],
  },
  {
    key: 'ai-center',
    icon: <SettingOutlined />,
    label: 'AI配置中心',
    children: [
      { key: '/ai-center/sensitive-words', label: '敏感词管理' },
      { key: '/ai-center/prompts', label: '提示词配置' },
      { key: '/prompt-templates', icon: <FormOutlined />, label: 'Prompt 模板配置' },
      { key: '/ai-center/disclaimers', label: '免责提示配置' },
    ],
  },
  {
    key: 'ai-consult-config',
    icon: <PhoneOutlined />,
    label: 'AI咨询配置',
    children: [
      { key: '/function-buttons', label: '功能按钮管理' },
      { key: '/digital-humans', label: '数字人形象管理' },
      { key: '/voice-service', label: '语音服务配置' },
      { key: '/tts-config', icon: <SoundOutlined />, label: 'TTS语音配置' },
      { key: '/share-config', icon: <ShareAltOutlined />, label: '分享海报配置' },
    ],
  },
  {
    key: 'home-config',
    icon: <HomeOutlined />,
    label: '首页配置',
    children: [
      { key: '/home-settings', label: '首页基础设置' },
      { key: '/home-menus', label: '首页菜单管理' },
      { key: '/home-banners', label: '首页Banner管理' },
      { key: '/notices', label: '公告管理' },
      { key: '/bottom-nav', label: '底部导航配置' },
    ],
  },
  { key: '/city-management', icon: <EnvironmentOutlined />, label: '城市管理' },
  {
    key: 'search-manage',
    icon: <SearchOutlined />,
    label: '搜索管理',
    children: [
      { key: '/search/recommend', label: '推荐搜索词' },
      { key: '/search/statistics', label: '搜索统计' },
      { key: '/search/block-words', label: '屏蔽词管理' },
      { key: '/search/asr-config', label: '语音配置' },
    ],
  },
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
  {
    key: 'health-plan',
    icon: <ScheduleOutlined />,
    label: '健康计划管理',
    children: [
      { key: '/health-plan/default-tasks', label: '通用任务配置' },
      { key: '/health-plan/statistics', label: '打卡数据统计' },
    ],
  },
  {
    key: 'health',
    icon: <HeartOutlined />,
    label: '健康档案管理',
    children: [
      { key: '/health-records', label: '用户档案查看' },
      { key: '/relation-types', label: '关系类型配置' },
      { key: '/disease-presets', label: '预设列表管理' },
      { key: '/family-management', label: '家庭共管管理' },
    ],
  },
  {
    key: 'messages',
    icon: <MessageOutlined />,
    label: '系统消息管理',
    children: [
      { key: '/system-messages', label: '消息列表' },
      { key: '/system-messages/send', label: '发送消息' },
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
      { key: '/wechat-push', label: '微信推送管理' },
      { key: '/email-notify', label: '邮件通知管理' },
      { key: '/cos-config', label: '存储配置' },
    ],
  },
];

function getOpenKeys(pathname: string): string[] {
  if (pathname.startsWith('/services')) return ['services'];
  if (pathname.startsWith('/merchant')) return ['merchant'];
  if (pathname.startsWith('/content')) return ['content'];
  if (pathname.startsWith('/points')) return ['points'];
  if (pathname.startsWith('/ai-config') || pathname.startsWith('/chat-records') || pathname.startsWith('/knowledge') || pathname.startsWith('/search-config') || pathname.startsWith('/fallback-config') || pathname.startsWith('/ocr-config') || pathname.startsWith('/ocr-global-config') || pathname.startsWith('/checkup-details') || pathname.startsWith('/drug-details')) return ['ai'];
  if (pathname.startsWith('/ai-center') || pathname.startsWith('/prompt-templates')) return ['ai-center'];
  if (pathname.startsWith('/function-buttons') || pathname.startsWith('/digital-humans') || pathname.startsWith('/voice-service') || pathname.startsWith('/tts-config') || pathname.startsWith('/share-config')) return ['ai-consult-config'];
  if (pathname.startsWith('/home-settings') || pathname.startsWith('/home-menus') || pathname.startsWith('/home-banners') || pathname.startsWith('/notices') || pathname.startsWith('/bottom-nav')) return ['home-config'];
  if (pathname.startsWith('/search')) return ['search-manage'];
  if (pathname.startsWith('/system-messages')) return ['messages'];
  if (pathname.startsWith('/sms') || pathname.startsWith('/settings') || pathname.startsWith('/wechat-push') || pathname.startsWith('/email-notify') || pathname.startsWith('/cos-config')) return ['system'];
  if (pathname.startsWith('/health-plan')) return ['health-plan'];
  if (pathname.startsWith('/health-records') || pathname.startsWith('/relation-types') || pathname.startsWith('/disease-presets') || pathname.startsWith('/family-management')) return ['health'];
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
