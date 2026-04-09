'use client';

import { useState, useEffect, useMemo, ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { TabBar } from 'antd-mobile';
import {
  AppOutline,
  MessageOutline,
  UnorderedListOutline,
  FileOutline,
  FolderOutline,
  ShopbagOutline,
  HeartOutline,
  PieOutline,
  BellOutline,
  UserOutline,
} from 'antd-mobile-icons';

interface NavItem {
  name: string;
  icon_key: string;
  path: string;
  is_fixed: boolean;
}

const ICON_MAP: Record<string, ReactNode> = {
  home: <AppOutline />,
  chat: <MessageOutline />,
  service: <UnorderedListOutline />,
  order: <FileOutline />,
  record: <FolderOutline />,
  mall: <ShopbagOutline />,
  health: <HeartOutline />,
  report: <PieOutline />,
  bell: <BellOutline />,
  profile: <UserOutline />,
};

const DEFAULT_TABS: NavItem[] = [
  { name: '首页', icon_key: 'home', path: '/', is_fixed: true },
  { name: '我的', icon_key: 'profile', path: '/profile', is_fixed: true },
];

const CACHE_KEY = 'bottom_nav_cache';
const CACHE_TIME_KEY = 'bottom_nav_cache_time';
const CACHE_TTL = 5 * 60 * 1000;

function mapPathToH5(path: string): string {
  if (path === '/') return '/home';
  return path;
}

function readCache(): NavItem[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const timeStr = localStorage.getItem(CACHE_TIME_KEY);
    if (!timeStr) return null;
    if (Date.now() - Number(timeStr) > CACHE_TTL) {
      localStorage.removeItem(CACHE_KEY);
      localStorage.removeItem(CACHE_TIME_KEY);
      return null;
    }
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCache(items: NavItem[]) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(items));
    localStorage.setItem(CACHE_TIME_KEY, String(Date.now()));
  } catch {
    // storage full — ignore
  }
}

async function fetchNavItems(): Promise<NavItem[]> {
  const base = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const res = await fetch(`${base}/api/h5/bottom-nav`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  if (json.code !== 0 || !Array.isArray(json.data)) throw new Error('Invalid response');
  return json.data as NavItem[];
}

export default function TabsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [navItems, setNavItems] = useState<NavItem[] | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const cached = readCache();
    if (cached) {
      setNavItems(cached);
      setLoaded(true);
      fetchNavItems()
        .then((fresh) => {
          writeCache(fresh);
          setNavItems(fresh);
        })
        .catch(() => {});
    } else {
      fetchNavItems()
        .then((fresh) => {
          writeCache(fresh);
          setNavItems(fresh);
        })
        .catch(() => {
          setNavItems(null);
        })
        .finally(() => setLoaded(true));
    }
  }, []);

  const tabs = useMemo(() => {
    const items = loaded ? (navItems ?? DEFAULT_TABS) : DEFAULT_TABS;
    return items.map((item) => ({
      key: mapPathToH5(item.path),
      title: item.name,
      icon: ICON_MAP[item.icon_key] ?? <AppOutline />,
    }));
  }, [navItems, loaded]);

  const activeKey = tabs.find((t) => pathname.startsWith(t.key))?.key || '/home';

  return (
    <div className="flex flex-col min-h-screen">
      <div className="flex-1 overflow-y-auto" style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>{children}</div>
      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100"
        style={{ maxWidth: 750, zIndex: 100, paddingBottom: 'env(safe-area-inset-bottom)' }}
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
