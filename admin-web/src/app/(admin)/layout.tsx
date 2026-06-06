'use client';

import React, { useState, useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown, Typography, Button, theme, Space } from 'antd';
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
  HomeOutlined,
  HeartOutlined,
  EnvironmentOutlined,
  PhoneOutlined,
  TeamOutlined,
  AppstoreOutlined,
  IdcardOutlined,
  KeyOutlined,
  CreditCardOutlined,
  CrownOutlined,
  UndoOutlined,
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
      // [2026-05-05 营业管理入口收敛 PRD v1.0 · N-01] 老顶层菜单下线，入口改为门店列表行操作列「营业管理」按钮
      { key: '/merchant/accounts', label: '商家账号' },
      { key: '/merchant-categories', label: '机构类别管理' },
      { key: '/admin-settlements', label: '对账单管理' },
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
      { key: '/prompt-templates', label: 'Prompt 模板配置' },
      { key: '/ai-center/disclaimers', label: '免责提示配置' },
      { key: '/tcm-config', label: '中医养生配置' },
      { key: '/constitution-content', label: '体质测评运营内容' },
    ],
  },
  {
    key: 'ai-consult-config',
    icon: <PhoneOutlined />,
    label: 'AI咨询配置',
    children: [
      // [BUG-HSC-FIX-V2 2026-05-21] B-5：老菜单「部位症状字典」「健康自查问卷模板」下线，
      // 统一合并到「通用问卷模板管理」（健康自查模板直接在通用列表中编辑）。
      // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 通用问卷模板（健康自查/体质测评/睡眠测评等共用）
      { key: '/questionnaire-templates', label: '通用问卷模板管理' },
      { key: '/ai-call-config', label: 'AI 外呼配置' },
      { key: '/digital-humans', label: '数字人形象管理' },
      { key: '/voice-service', label: '语音服务配置' },
      { key: '/tts-config', label: 'TTS语音配置' },
      { key: '/share-config', label: '分享海报配置' },
      { key: '/ai-config/video-consult', label: '视频客服' },
      { key: '/ai-config/chat-timeout', label: '对话超时配置' },
    ],
  },
  {
    // [PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19] 首页配置组结构调整：
    // - 移除「首页基础设置」「页面风格」「首页菜单管理」
    // - 「AI 对话模式首页配置」改名「AI首页配置」
    // - 「功能按钮管理」从 AI咨询配置 迁入
    // - 原「首页基础设置」改名「字体配置」并瘦身为仅 font_* 字段
    key: 'home-config',
    icon: <HomeOutlined />,
    label: '首页配置',
    children: [
      { key: '/home-settings/ai-home-config', label: 'AI首页配置' },
      { key: '/function-buttons', label: '功能按钮管理' },
      { key: '/home-settings', label: '字体配置' },
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
    key: 'product-system',
    icon: <AppstoreOutlined />,
    label: '商品体系',
    children: [
      { key: '/product-system/categories', label: '商品分类' },
      { key: '/product-system/tags', label: '标签管理' },
      { key: '/product-system/products', label: '商品管理' },
      { key: '/product-system/cards', label: '卡管理' },
      { key: '/product-system/store-bindding', label: '适用门店' },
      { key: '/product-system/appointment-forms', label: '预约表单库' },
      { key: '/product-system/orders', label: '订单明细' },
      { key: '/product-system/coupons', label: '优惠券管理' },
      { key: '/product-system/new-user-coupons', label: '新人券池' },
      { key: '/product-system/partners', label: '合作方管理' },
      { key: '/product-system/redemptions', label: '核销管理' },
      { key: '/product-system/visits', label: '进店记录' },
      { key: '/product-system/statistics', label: '订单统计' },
    ],
  },
  // [2026-05-03 支付配置 PRD v1.0] 支付通道配置（仅 admin/super_admin 可见）
  { key: '/payment-config', icon: <CreditCardOutlined />, label: '支付配置' },
  // [微信小程序支付完整接入 v1.0] 退款管理
  { key: '/refunds', icon: <UndoOutlined />, label: '退款管理' },
  {
    key: 'content',
    icon: <FileTextOutlined />,
    label: '内容管理',
    children: [
      { key: '/content/articles', label: '文章管理' },
      { key: '/content/news', label: '资讯管理' },
      { key: '/content/categories', label: '分类管理' },
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
      // [付费会员体系 PRD v1.1] 旧「会员等级」（依积分自动划档）已废弃，改用付费会员套餐
      // 入口下线，菜单仅保留积分规则与积分商城
    ],
  },
  {
    key: 'membership',
    icon: <CrownOutlined />,
    label: '会员管理',
    children: [
      { key: '/membership/plans', label: '付费会员套餐管理' },
      { key: '/membership/free-quota', label: '免费会员额度配置' },
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
      // [PRD-GUARDIAN-V1.2] 守护关系管理（原顶层「守护关系查询」并入）
      { key: '/family-management', label: '守护关系管理' },
      // [PRD-GUARDIAN-V1.2 §12.3] 紧急呼叫触发源管理
      { key: '/emergency-sources', label: '紧急呼叫触发源管理' },
      // [PRD-HOME-SAFETY-V1 2026-05-27] 居家安全设备管理（紧急呼叫器/烟雾/水位）
      { key: '/home-safety', label: '居家安全设备管理' },
      // [PRD-HEALTH-PLAN-OFFLINE-V1.0 2026-05-25] 打卡数据统计搬家自原「健康计划管理」
      { key: '/health-records/statistics', label: '打卡数据统计' },
    ],
  },
  {
    key: 'devices',
    icon: <DatabaseOutlined />,
    label: '设备管理',
    children: [
      { key: '/devices/scene-groups', label: '设备场景分类' },
      { key: '/devices/catalog', label: '设备目录管理' },
    ],
  },
  {
    key: 'messages',
    icon: <MessageOutlined />,
    label: '系统消息管理',
    children: [
      { key: '/system-messages', label: '消息列表' },
      { key: '/system-messages/send', label: '发送消息' },
      // [PRD-FAMILY-GUARDIAN-V1] 家庭体检异常守护推送
      { key: '/alert-templates', label: '异常文案模板' },
      { key: '/abnormal-thresholds', label: '异常阈值配置' },
      { key: '/alert-logs', label: '推送记录' },
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
      { key: '/map-config', label: '地图配置' },
      { key: '/audit/phones', label: '审核手机号配置' },
      { key: '/audit/center', label: '审核中心' },
      // [2026-05-05 SDK 健康看板] 环境健康检查（运维侧 SDK 红绿灯）
      { key: '/system/sdk-health', label: '环境健康检查' },
      // [PRD-AI-PAGE-OPTIM-V1 2026-05-21] 种子数据导入：6 个问卷/标签种子包按需导入
      { key: '/system/seed-import', label: '种子数据导入' },
    ],
  },
];

/**
 * 管理后台侧边栏菜单视觉规范（强约束）：
 * - 一级菜单**必须**配置图标
 * - 二级菜单**禁止**配置图标，仅以纯文字呈现
 * - 折叠态弹出浮层中的二级菜单同样**禁止**配置图标
 *
 * 为防止后续维护者无意中给二级菜单配置 icon，这里在渲染前递归清洗：
 * 凡是 SubMenu 的 children（即二级及以下菜单），统一移除其 icon 字段。
 * 一级菜单（顶层 items）的 icon 保留不动。
 */
function stripChildrenIcons(items: MenuItem[]): MenuItem[] {
  return items.map((item) => {
    if (!item) return item;
    const anyItem = item as any;
    if (Array.isArray(anyItem.children)) {
      return {
        ...anyItem,
        children: anyItem.children.map((child: any) => {
          if (!child) return child;
          const { icon, ...rest } = child;
          if (Array.isArray(rest.children)) {
            const sanitized = stripChildrenIcons([rest] as MenuItem[]);
            return sanitized[0];
          }
          return rest;
        }),
      } as MenuItem;
    }
    return item;
  });
}

function getOpenKeys(pathname: string): string[] {
  if (pathname.startsWith('/merchant') || pathname.startsWith('/merchant-categories') || pathname.startsWith('/admin-settlements')) return ['merchant'];
  if (pathname.startsWith('/content')) return ['content'];
  if (pathname.startsWith('/points')) return ['points'];
  if (pathname.startsWith('/ai-config/video-consult') || pathname.startsWith('/ai-config/chat-timeout')) return ['ai-consult-config'];
  if (pathname.startsWith('/ai-config') || pathname.startsWith('/chat-records') || pathname.startsWith('/knowledge') || pathname.startsWith('/search-config') || pathname.startsWith('/fallback-config') || pathname.startsWith('/ocr-config') || pathname.startsWith('/ocr-global-config') || pathname.startsWith('/checkup-details') || pathname.startsWith('/drug-details')) return ['ai'];
  if (pathname.startsWith('/ai-center') || pathname.startsWith('/prompt-templates') || pathname.startsWith('/tcm-config') || pathname.startsWith('/constitution-content')) return ['ai-center'];
  if (pathname.startsWith('/function-buttons') || pathname.startsWith('/digital-humans') || pathname.startsWith('/voice-service') || pathname.startsWith('/tts-config') || pathname.startsWith('/share-config') || pathname.startsWith('/questionnaire-templates')) return ['ai-consult-config'];
  if (pathname.startsWith('/home-settings') || pathname.startsWith('/home-banners') || pathname.startsWith('/notices') || pathname.startsWith('/bottom-nav') || pathname.startsWith('/home-settings/ai-home-config') || pathname.startsWith('/function-buttons')) return ['home-config'];
  if (pathname.startsWith('/search')) return ['search-manage'];
  if (pathname.startsWith('/system-messages') || pathname.startsWith('/alert-templates') || pathname.startsWith('/abnormal-thresholds') || pathname.startsWith('/alert-logs')) return ['messages'];
  if (pathname.startsWith('/sms') || pathname.startsWith('/settings') || pathname.startsWith('/wechat-push') || pathname.startsWith('/email-notify') || pathname.startsWith('/cos-config') || pathname.startsWith('/map-config') || pathname.startsWith('/system/')) return ['system'];
  if (pathname.startsWith('/devices')) return ['devices'];
  if (pathname.startsWith('/health-records') || pathname.startsWith('/relation-types') || pathname.startsWith('/disease-presets') || pathname.startsWith('/family-management') || pathname.startsWith('/emergency-sources') || pathname.startsWith('/home-safety') || pathname.startsWith('/guardian-relations')) return ['health'];
  if (pathname.startsWith('/product-system')) return ['product-system'];
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
      key: 'profile',
      icon: <IdcardOutlined />,
      label: '个人信息',
      onClick: () => router.push('/profile'),
    },
    {
      key: 'change-password',
      icon: <KeyOutlined />,
      label: '修改密码',
      onClick: () => router.push('/profile/change-password'),
    },
    { type: 'divider' as const },
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
          items={stripChildrenIcons(menuItems)}
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
            gap: 16,
            borderBottom: '1px solid #f0f0f0',
            height: 64,
            position: 'sticky',
            top: 0,
            zIndex: 99,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          }}
        >
          {/* 左侧：仅保留菜单折叠按钮 */}
          <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 18, width: 48, height: 48 }}
              aria-label={collapsed ? '展开菜单' : '折叠菜单'}
            />
          </div>
          {/* 右侧：仅保留管理员头像 + 退出登录下拉 */}
          <Space size={16} align="center" style={{ flexShrink: 0 }}>
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
          </Space>
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
