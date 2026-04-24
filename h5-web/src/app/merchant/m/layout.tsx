'use client';

// [2026-04-24] 商家端移动端 H5 独立布局
// 采用 antd-mobile，底部 TabBar（仅在登录后且非登录页显示）

import React, { useEffect, useMemo, useState } from 'react';
import { ConfigProvider, TabBar, SafeArea } from 'antd-mobile';
import zhCN from 'antd-mobile/es/locales/zh-CN';
import { usePathname, useRouter } from 'next/navigation';
import { getProfile, isAuthed, getTabsForRole, MerchantLoginProfile } from './mobile-lib';

export default function MerchantMobileLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || '';
  const router = useRouter();
  const [profile, setProfile] = useState<MerchantLoginProfile | null>(null);
  const [mounted, setMounted] = useState(false);

  const normalizedPath = pathname.replace(/\/+$/, '');
  const isLoginOrSelect =
    normalizedPath.endsWith('/merchant/m/login') ||
    normalizedPath.endsWith('/merchant/m/select-store');

  useEffect(() => {
    setMounted(true);
    if (isLoginOrSelect) return;
    if (!isAuthed()) {
      router.replace('/merchant/m/login');
      return;
    }
    setProfile(getProfile());
  }, [isLoginOrSelect, router]);

  const tabs = useMemo(() => getTabsForRole(profile?.role), [profile?.role]);

  const activeTabKey = useMemo(() => {
    if (normalizedPath.includes('/merchant/m/dashboard')) return 'dashboard';
    if (normalizedPath.includes('/merchant/m/orders')) return 'orders';
    if (normalizedPath.includes('/merchant/m/verify')) return 'verify';
    if (normalizedPath.includes('/merchant/m/settlement')) return 'settlement';
    if (normalizedPath.includes('/merchant/m/me')) return 'me';
    return '';
  }, [normalizedPath]);

  // 登录/选店 页不显示 TabBar
  const showTabBar =
    !isLoginOrSelect &&
    mounted &&
    !!activeTabKey;

  return (
    <ConfigProvider locale={zhCN}>
      <div
        style={{
          minHeight: '100vh',
          background: '#f7f8fa',
          display: 'flex',
          flexDirection: 'column',
          maxWidth: 768,
          margin: '0 auto',
          position: 'relative',
        }}
      >
        <div
          style={{
            flex: 1,
            paddingBottom: showTabBar ? 68 : 0,
            minHeight: 'calc(100vh - 0px)',
          }}
        >
          {children}
        </div>

        {showTabBar && (
          <div
            style={{
              position: 'fixed',
              bottom: 0,
              left: 0,
              right: 0,
              background: '#fff',
              borderTop: '1px solid #eee',
              zIndex: 999,
              maxWidth: 768,
              margin: '0 auto',
            }}
          >
            <TabBar
              activeKey={activeTabKey}
              onChange={(key) => {
                const item = tabs.find((t) => t.key === key);
                if (item) router.push(item.path);
              }}
              safeArea
            >
              {tabs.map((t) => (
                <TabBar.Item
                  key={t.key}
                  icon={<span style={{ fontSize: 22 }}>{t.icon}</span>}
                  title={t.title}
                />
              ))}
            </TabBar>
            <SafeArea position="bottom" />
          </div>
        )}
      </div>
    </ConfigProvider>
  );
}
