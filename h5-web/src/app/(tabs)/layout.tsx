'use client';

import { usePathname, useRouter } from 'next/navigation';
import { TabBar } from 'antd-mobile';
import {
  AppOutline,
  MessageOutline,
  UnorderedListOutline,
  UserOutline,
} from 'antd-mobile-icons';

const tabs = [
  { key: '/home', title: '首页', icon: <AppOutline /> },
  { key: '/ai', title: 'AI健康咨询', icon: <MessageOutline /> },
  { key: '/services', title: '服务', icon: <UnorderedListOutline /> },
  { key: '/profile', title: '我的', icon: <UserOutline /> },
];

export default function TabsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const activeKey = tabs.find((t) => pathname.startsWith(t.key))?.key || '/home';

  return (
    <div className="flex flex-col min-h-screen">
      <div className="flex-1 overflow-y-auto">{children}</div>
      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100"
        style={{ maxWidth: 750, zIndex: 100 }}
      >
        <TabBar
          activeKey={activeKey}
          onChange={(key) => router.push(key)}
          style={{
            '--adm-color-primary': '#52c41a',
          } as React.CSSProperties}
        >
          {tabs.map((item) => (
            <TabBar.Item key={item.key} icon={item.icon} title={item.title} />
          ))}
        </TabBar>
      </div>
    </div>
  );
}
