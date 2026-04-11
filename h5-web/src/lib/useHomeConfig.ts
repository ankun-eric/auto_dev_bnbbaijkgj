'use client';

import { useState, useEffect } from 'react';
import api from './api';

export interface HomeConfig {
  search_visible: boolean;
  search_placeholder: string;
  grid_columns: 3 | 4 | 5;
  font_switch_enabled: boolean;
  font_default_level: 'standard' | 'large' | 'xlarge';
  font_standard_size: number;
  font_large_size: number;
  font_xlarge_size: number;
}

export interface HomeBanner {
  id: number;
  image_url: string;
  link_type: 'internal' | 'external' | 'none';
  link_url: string;
  miniprogram_appid: string;
  sort_order: number;
}

export interface HomeMenu {
  id: number;
  name: string;
  icon_type: 'emoji' | 'image';
  icon_content: string;
  link_type: 'internal' | 'external' | 'none';
  link_url: string;
  miniprogram_appid: string;
  sort_order: number;
}

const DEFAULT_CONFIG: HomeConfig = {
  search_visible: true,
  search_placeholder: '搜索健康知识、服务、商品',
  grid_columns: 3,
  font_switch_enabled: false,
  font_default_level: 'standard',
  font_standard_size: 14,
  font_large_size: 18,
  font_xlarge_size: 22,
};

const DEFAULT_BANNERS: HomeBanner[] = [
  { id: 1, image_url: '', link_type: 'none', link_url: '', miniprogram_appid: '', sort_order: 1 },
  { id: 2, image_url: '', link_type: 'none', link_url: '', miniprogram_appid: '', sort_order: 2 },
];

const DEFAULT_MENUS: HomeMenu[] = [
  { id: 1, name: 'AI健康咨询', icon_type: 'emoji', icon_content: '💬', link_type: 'internal', link_url: '/ai', miniprogram_appid: '', sort_order: 1 },
  { id: 2, name: '体检报告', icon_type: 'emoji', icon_content: '📋', link_type: 'internal', link_url: '/checkup', miniprogram_appid: '', sort_order: 2 },
  { id: 3, name: '健康自查', icon_type: 'emoji', icon_content: '🔍', link_type: 'internal', link_url: '/symptom', miniprogram_appid: '', sort_order: 3 },
  { id: 4, name: '中医养生', icon_type: 'emoji', icon_content: '🌿', link_type: 'internal', link_url: '/tcm', miniprogram_appid: '', sort_order: 4 },
  { id: 5, name: '用药参考', icon_type: 'emoji', icon_content: '💊', link_type: 'internal', link_url: '/drug', miniprogram_appid: '', sort_order: 5 },
  { id: 6, name: '健康计划', icon_type: 'emoji', icon_content: '📅', link_type: 'internal', link_url: '/health-plan', miniprogram_appid: '', sort_order: 6 },
];

const CACHE_KEY = 'home_data_cache';
const CACHE_TTL = 60 * 60 * 1000;

interface CachedData {
  config: HomeConfig;
  banners: HomeBanner[];
  menus: HomeMenu[];
  timestamp: number;
}

function getCache(): CachedData | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const data: CachedData = JSON.parse(raw);
    if (Date.now() - data.timestamp > CACHE_TTL) {
      localStorage.removeItem(CACHE_KEY);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

function setCache(data: Omit<CachedData, 'timestamp'>) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(CACHE_KEY, JSON.stringify({ ...data, timestamp: Date.now() }));
}

export function useHomeConfig() {
  const [config, setConfig] = useState<HomeConfig>(DEFAULT_CONFIG);
  const [banners, setBanners] = useState<HomeBanner[]>([]);
  const [menus, setMenus] = useState<HomeMenu[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cached = getCache();
    if (cached) {
      setConfig(cached.config);
      setBanners(cached.banners);
      setMenus(cached.menus);
      setLoading(false);
      return;
    }

    async function fetchAll() {
      try {
        const [configRes, bannersRes, menusRes] = await Promise.all([
          api.get('/api/home-config').catch(() => null),
          api.get('/api/home-banners').catch(() => null),
          api.get('/api/home-menus').catch(() => null),
        ]);

        const cfg = (configRes as unknown as HomeConfig) || DEFAULT_CONFIG;
        const bList = (bannersRes as unknown as { items: HomeBanner[] })?.items || DEFAULT_BANNERS;
        const mList = (menusRes as unknown as { items: HomeMenu[] })?.items || DEFAULT_MENUS;

        setConfig(cfg);
        setBanners(bList);
        setMenus(mList);
        setCache({ config: cfg, banners: bList, menus: mList });
      } catch {
        setConfig(DEFAULT_CONFIG);
        setBanners(DEFAULT_BANNERS);
        setMenus(DEFAULT_MENUS);
      } finally {
        setLoading(false);
      }
    }

    fetchAll();
  }, []);

  return { config, banners, menus, loading };
}
