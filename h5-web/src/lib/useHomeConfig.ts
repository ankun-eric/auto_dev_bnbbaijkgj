'use client';

import { useState, useEffect, useCallback } from 'react';
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

function clearCache() {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(CACHE_KEY);
  } catch {}
}

export function useHomeConfig() {
  const [config, setConfig] = useState<HomeConfig>(DEFAULT_CONFIG);
  const [banners, setBanners] = useState<HomeBanner[]>([]);
  const [menus, setMenus] = useState<HomeMenu[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async (opts?: { skipCache?: boolean }) => {
    if (!opts?.skipCache) {
      const cached = getCache();
      if (cached) {
        setConfig(cached.config);
        setBanners(cached.banners);
        setMenus(cached.menus);
        setLoading(false);
        return;
      }
    }

    try {
      const [configRes, bannersRes, menusRes] = await Promise.all([
        api.get('/api/home-config').catch(() => null),
        api.get('/api/home-banners').catch(() => null),
        api.get('/api/home-menus').catch(() => null),
      ]);

      const cfg = (configRes as unknown as HomeConfig) || DEFAULT_CONFIG;
      const bList = (bannersRes as unknown as { items: HomeBanner[] })?.items ?? [];
      const mList = (menusRes as unknown as { items: HomeMenu[] })?.items ?? [];

      setConfig(cfg);
      setBanners(bList);
      setMenus(mList);
      setCache({ config: cfg, banners: bList, menus: mList });
    } catch {
      setConfig(DEFAULT_CONFIG);
      setBanners([]);
      setMenus([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const refetch = useCallback(async () => {
    clearCache();
    await fetchAll({ skipCache: true });
  }, [fetchAll]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { config, banners, menus, loading, refetch };
}

export function clearHomeConfigCache() {
  clearCache();
}
