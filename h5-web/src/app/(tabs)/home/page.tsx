'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Swiper, Grid, List, Tag, Badge, NoticeBar, SpinLoading, Toast, Dialog, Button, PullToRefresh } from 'antd-mobile';
import { useHomeConfig, HomeBanner, HomeMenu } from '@/lib/useHomeConfig';
import api from '@/lib/api';
import { getSelectedCity, getLocationCache, requestGeolocation, CityInfo } from '@/lib/cityUtils';
import MarketingBadge from '@/components/MarketingBadge';

interface RecommendProduct {
  id: number;
  name: string;
  sale_price: number;
  cover_image?: string | null;
  images?: string[] | null;
  selling_point?: string | null;
  category_name?: string | null;
  marketing_badges?: string[] | null;
}

const UNREAD_POLL_INTERVAL = 60 * 1000;

interface NoticeItem {
  id: number;
  content: string;
  link_url: string;
  start_time: string;
  end_time: string;
  is_enabled: boolean;
  sort_order: number;
}

const FALLBACK_NOTICE = '宾尼小康提醒您：定期体检，关注健康，预防疾病。';
const CACHE_DURATION = 30 * 60 * 1000;
let noticeCache: { data: NoticeItem[]; timestamp: number } | null = null;

interface ArticleItem {
  id: number;
  title: string;
  tag: string;
  views: number;
}

interface NewsHomeItem {
  id: number;
  title: string;
  coverImage: string;
  publishedAt: string;
}

interface TodoItem {
  id: number;
  name: string;
  type: string;
  source: string;
  source_id?: number;
  target_value?: number;
  target_unit?: string;
  is_completed: boolean;
  remind_time?: string;
  extra?: Record<string, unknown>;
}

interface TodoSubGroup {
  sub_group_name: string;
  category_id?: number;
  items: TodoItem[];
  completed_count: number;
  total_count: number;
  is_empty: boolean;
}

interface TodoGroup {
  group_name: string;
  group_type: string;
  items: TodoItem[];
  sub_groups?: TodoSubGroup[];
  completed_count: number;
  total_count: number;
  is_empty: boolean;
}

interface TodayTodosResponse {
  total_completed: number;
  total_count: number;
  groups: TodoGroup[];
}

const FALLBACK_COLORS = ['#52c41a', '#13c2c2', '#1890ff', '#722ed1', '#eb2f96', '#fa8c16'];

function handleLink(
  linkType: string,
  linkUrl: string,
  router: ReturnType<typeof useRouter>,
) {
  if (linkType === 'internal' && linkUrl) {
    router.push(linkUrl);
  } else if (linkType === 'external' && linkUrl) {
    window.open(linkUrl, '_blank');
  }
}

type CityStatus = 'idle' | 'locating' | 'located' | 'failed';

export default function HomePage() {
  const router = useRouter();

  const [notices, setNotices] = useState<NoticeItem[] | null>(null);
  const [todayTodos, setTodayTodos] = useState<TodayTodosResponse | null>(null);
  const [todosLoading, setTodosLoading] = useState(true);
  const [inputVisible, setInputVisible] = useState<number | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [unreadCount, setUnreadCount] = useState(0);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [latestNews, setLatestNews] = useState<NewsHomeItem[]>([]);
  const [hotProducts, setHotProducts] = useState<RecommendProduct[]>([]);

  const [cityDisplay, setCityDisplay] = useState('定位');
  const [cityStatus, setCityStatus] = useState<CityStatus>('idle');
  const cityInitRef = useRef(false);

  // 30s 节流：切回前台时避免频繁刷新
  const lastRefreshRef = useRef<number>(0);

  const fetchTodos = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-plan/today-todos');
      const data = res.data || res;
      setTodayTodos(data);
    } catch {
      setTodayTodos(null);
    } finally {
      setTodosLoading(false);
    }
  }, []);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res: any = await api.get('/api/messages/unread-count');
      const data = res.data || res;
      setUnreadCount(data.unread_count ?? 0);
    } catch { /* ignore */ }
  }, []);

  const fetchArticles = useCallback(async () => {
    try {
      const res: any = await api.get('/api/content/articles?page=1&page_size=3');
      const items: any[] = res?.items ?? res?.data?.items ?? [];
      const mapped: ArticleItem[] = items.map((a) => ({
        id: a.id,
        title: a.title ?? '',
        tag: a.category ?? '健康',
        views: a.view_count ?? 0,
      }));
      setArticles(mapped);
    } catch {
      setArticles([]);
    }
  }, []);

  // 商品功能优化 v1.0：首页热门推荐商品（带营销角标）
  const fetchHotProducts = useCallback(async () => {
    try {
      const res: any = await api.get('/api/products/hot-recommendations?limit=6');
      const items: any[] = Array.isArray(res) ? res : (res?.items ?? res?.data?.items ?? res?.data ?? []);
      const list: RecommendProduct[] = (items || []).map((p) => ({
        id: Number(p.id),
        name: String(p.name ?? ''),
        sale_price: Number(p.sale_price ?? 0),
        cover_image: p.cover_image ?? (Array.isArray(p.images) ? p.images[0] : null),
        images: Array.isArray(p.images) ? p.images : null,
        selling_point: p.selling_point ?? null,
        category_name: p.category_name ?? null,
        marketing_badges: Array.isArray(p.marketing_badges) ? p.marketing_badges : [],
      }));
      setHotProducts(list);
    } catch {
      setHotProducts([]);
    }
  }, []);

  const fetchLatestNews = useCallback(async () => {
    try {
      const res: any = await api.get('/api/content/news/latest?limit=5');
      const items: any[] = res?.items ?? res?.data?.items ?? [];
      const mapped: NewsHomeItem[] = items.map((n) => ({
        id: n.id,
        title: n.title ?? '',
        coverImage: n.cover_image ?? '',
        publishedAt: n.published_at ?? n.created_at ?? '',
      }));
      setLatestNews(mapped);
    } catch {
      setLatestNews([]);
    }
  }, []);

  const fetchNotices = useCallback(async (skipCache = false) => {
    const now = Date.now();
    if (!skipCache && noticeCache && now - noticeCache.timestamp < CACHE_DURATION) {
      setNotices(noticeCache.data);
      return;
    }
    try {
      const json = await api.get('/api/notices/active') as { items?: NoticeItem[] };
      const data: NoticeItem[] = json.items ?? [];
      noticeCache = { data, timestamp: Date.now() };
      setNotices(data);
    } catch {
      setNotices(null);
    }
  }, []);

  useEffect(() => {
    const fetchLogo = async () => {
      try {
        const res: any = await api.get('/api/settings/logo');
        if (res?.data?.logo_url) {
          setLogoUrl(res.data.logo_url);
        }
      } catch {}
    };
    fetchLogo();
  }, []);

  useEffect(() => {
    fetchUnreadCount();
    const timer = setInterval(fetchUnreadCount, UNREAD_POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchUnreadCount]);

  useEffect(() => {
    fetchNotices();
    fetchTodos();
    fetchArticles();
    fetchLatestNews();
    fetchHotProducts();
  }, [fetchTodos, fetchNotices, fetchArticles, fetchLatestNews, fetchHotProducts]);

  const refreshCityDisplay = useCallback(() => {
    const selected = getSelectedCity();
    if (selected) {
      setCityDisplay(selected.name);
      setCityStatus('located');
      return;
    }
    const cached = getLocationCache();
    if (cached) {
      setCityDisplay(cached.name);
      setCityStatus('located');
      return;
    }
    setCityDisplay('定位');
    setCityStatus('idle');
  }, []);

  useEffect(() => {
    refreshCityDisplay();

    const onStorage = (e: StorageEvent) => {
      if (e.key === 'selected_city_name' || e.key === 'selected_city_id') {
        refreshCityDisplay();
      }
    };
    window.addEventListener('storage', onStorage);

    const onFocus = () => refreshCityDisplay();
    window.addEventListener('focus', onFocus);

    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('focus', onFocus);
    };
  }, [refreshCityDisplay]);

  useEffect(() => {
    if (cityInitRef.current) return;
    cityInitRef.current = true;

    const selected = getSelectedCity();
    if (selected) return;

    setCityStatus('locating');
    setCityDisplay('定位中...');
    requestGeolocation().then((city) => {
      if (getSelectedCity()) {
        refreshCityDisplay();
        return;
      }
      if (city) {
        setCityDisplay(city.name);
        setCityStatus('located');
      } else {
        setCityDisplay('定位');
        setCityStatus('failed');
      }
    });
  }, [refreshCityDisplay]);

  const handleQuickCheck = async (item: TodoItem) => {
    if (item.is_completed) return;
    if (item.target_value != null && item.target_value > 0) {
      setInputVisible(item.id);
      setInputValue('');
      return;
    }
    try {
      await api.post(`/api/health-plan/today-todos/${item.id}/check`, {
        type: item.type,
        value: null,
      });
      Toast.show({ content: '打卡成功', icon: 'success' });
      fetchTodos();
    } catch {
      Toast.show({ content: '打卡失败', icon: 'fail' });
    }
  };

  const handleValueSubmit = async (item: TodoItem) => {
    const val = parseFloat(inputValue);
    if (isNaN(val) || val < 0) {
      Toast.show({ content: '请输入有效数值', icon: 'fail' });
      return;
    }
    try {
      await api.post(`/api/health-plan/today-todos/${item.id}/check`, {
        type: item.type,
        value: val,
      });
      Toast.show({ content: '打卡成功', icon: 'success' });
      setInputVisible(null);
      setInputValue('');
      fetchTodos();
    } catch {
      Toast.show({ content: '打卡失败', icon: 'fail' });
    }
  };

  const { config, banners, menus, loading, refetch: refetchHomeConfig } = useHomeConfig();

  const handleRefresh = useCallback(async () => {
    lastRefreshRef.current = Date.now();
    // 同步清掉 noticeCache，保证公告栏也能刷新
    noticeCache = null;
    await Promise.all([
      refetchHomeConfig(),
      fetchNotices(true),
      fetchTodos(),
      fetchArticles(),
      fetchLatestNews(),
      fetchHotProducts(),
      fetchUnreadCount(),
    ]);
  }, [refetchHomeConfig, fetchNotices, fetchTodos, fetchArticles, fetchLatestNews, fetchUnreadCount]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastRefreshRef.current < 30 * 1000) return;
      handleRefresh();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [handleRefresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <SpinLoading color="primary" />
      </div>
    );
  }

  return (
    <PullToRefresh onRefresh={handleRefresh}>
    <div className="pb-20">
      <div className="compact-home-header">
        {/* 第一行：品牌 + 地区（40px，整体左对齐） */}
        <div
          className="flex items-center"
          style={{ height: 40, paddingLeft: 16, paddingRight: 16 }}
        >
          <h1
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: '#fff',
              margin: 0,
              lineHeight: '24px',
            }}
          >
            宾尼小康
          </h1>
          <div
            className="flex items-center"
            style={{
              marginLeft: 12,
              minHeight: 32,
              cursor: cityStatus === 'locating' ? 'default' : 'pointer',
            }}
            onClick={() => {
              if (cityStatus === 'locating') return;
              router.push('/city-select');
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            <span
              className="truncate"
              style={{
                color: '#fff',
                fontSize: 14,
                marginLeft: 4,
                maxWidth: 80,
                display: 'inline-block',
              }}
            >
              {cityDisplay.length > 4 ? cityDisplay.slice(0, 4) + '…' : cityDisplay}
            </span>
            {cityStatus !== 'locating' && (
              <span style={{ color: '#fff', fontSize: 10, marginLeft: 4 }}>▼</span>
            )}
          </div>
        </div>
        {/* 第二行：搜索 + 扫一扫 + 消息（48px） */}
        <div
          className="flex items-center"
          style={{ height: 48, paddingLeft: 16, paddingRight: 16, gap: 12 }}
        >
          {config.search_visible ? (
            // PRD F1：搜索栏配色统一 — 白底 + 浅灰描边 + 灰 placeholder/图标
            <div
              className="flex items-center flex-1 cursor-pointer"
              onClick={() => router.push('/search')}
              style={{
                height: 36,
                borderRadius: 20,
                background: '#FFFFFF',
                border: '1px solid #E5E5E5',
                paddingLeft: 12,
                paddingRight: 12,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span
                className="ml-2 text-sm truncate"
                style={{ color: '#999999', flex: 1 }}
              >
                {config.search_placeholder || '搜索健康服务…'}
              </span>
            </div>
          ) : (
            <div style={{ flex: 1 }} />
          )}
          <div
            className="flex items-center justify-center cursor-pointer"
            style={{ width: 32, height: 32 }}
            onClick={() => router.push('/scan')}
            aria-label="扫一扫"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 7V5a2 2 0 0 1 2-2h2" />
              <path d="M17 3h2a2 2 0 0 1 2 2v2" />
              <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
              <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
              <line x1="7" y1="12" x2="17" y2="12" />
            </svg>
          </div>
          <Badge
            content={unreadCount > 0 ? (unreadCount > 99 ? '99+' : unreadCount) : null}
            style={{ '--right': '-2px', '--top': '2px', '--color': '#FF4D4F' }}
          >
            <div
              className="flex items-center justify-center cursor-pointer"
              style={{ width: 32, height: 32 }}
              onClick={() => router.push('/messages')}
              aria-label="消息"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            </div>
          </Badge>
        </div>
      </div>

      <div className="px-4 pt-2">
        {(() => {
          if (notices !== null && notices.length === 0) return null;
          const items = notices && notices.length > 0 ? notices : null;
          const content = items
            ? items.map((n) => n.content).join(' | ')
            : FALLBACK_NOTICE;
          const linkUrl = items
            ? (items.find((n) => n.link_url)?.link_url ?? '')
            : '';
          return (
            <NoticeBar
              content={content}
              color="info"
              style={{ borderRadius: 8, marginBottom: 12, fontSize: 12 }}
              onClick={linkUrl ? () => router.push(linkUrl) : undefined}
            />
          );
        })()}

        {(() => {
          const validBanners = banners.filter((b) => !!b.image_url);
          if (validBanners.length === 0) return null;
          return (
            <Swiper
              autoplay
              loop
              style={{ '--border-radius': '10px', marginTop: 8, marginBottom: 12 }}
            >
              {validBanners.map((b: HomeBanner) => (
                <Swiper.Item key={b.id}>
                  <div
                    className="rounded-[10px] overflow-hidden cursor-pointer"
                    style={{ height: 100 }}
                    onClick={() => handleLink(b.link_type, b.link_url, router)}
                  >
                    <img
                      src={b.image_url}
                      alt=""
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                </Swiper.Item>
              ))}
            </Swiper>
          );
        })()}

        {menus.length > 0 && (
          <div className="card">
            <Grid columns={config.grid_columns || 3} gap={16}>
              {menus.map((m: HomeMenu, i: number) => (
                <Grid.Item key={m.id} onClick={() => handleLink(m.link_type, m.link_url, router)}>
                  <div className="flex flex-col items-center py-2">
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center mb-2"
                      style={{
                        background: `${FALLBACK_COLORS[i % FALLBACK_COLORS.length]}15`,
                      }}
                    >
                      {m.icon_type === 'image' ? (
                        <img src={m.icon_content} alt={m.name} className="w-6 h-6" />
                      ) : (
                        <span style={{ fontSize: 24 }}>{m.icon_content}</span>
                      )}
                    </div>
                    <span className="text-xs text-gray-600">{m.name}</span>
                  </div>
                </Grid.Item>
              ))}
            </Grid>
          </div>
        )}

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <span className="section-title mb-0">📋 今日待办</span>
            <div className="flex items-center gap-2">
              {todayTodos && todayTodos.total_count > 0 && (
                <span className="text-xs text-gray-400">
                  已完成 {todayTodos.total_completed}/{todayTodos.total_count}
                </span>
              )}
              <span className="text-xs" style={{ color: '#52c41a' }} onClick={() => router.push('/health-plan')}>
                查看全部
              </span>
            </div>
          </div>

          {todosLoading ? (
            <div className="flex items-center justify-center py-6">
              <SpinLoading color="primary" style={{ '--size': '24px' }} />
            </div>
          ) : !todayTodos || todayTodos.total_count === 0 ? (
            <div className="text-center py-6">
              <div className="text-3xl mb-2">🎉</div>
              <div className="text-sm text-gray-400 mb-3">暂无待办任务</div>
              <Button
                size="mini"
                style={{ borderRadius: 20, color: '#52c41a', borderColor: '#52c41a' }}
                onClick={() => router.push('/health-plan')}
              >
                创建你的第一个健康计划
              </Button>
            </div>
          ) : (
            todayTodos.groups?.map((group) => {
              const groupIcon = group.group_type === 'medication' ? '💊' : group.group_type === 'checkin' ? '✅' : '📋';

              if (group.group_type === 'custom') {
                if (group.is_empty) {
                  return null;
                }
                const planGroups: Record<string, TodoItem[]> = {};
                group.items.forEach((item) => {
                  const planName = (item.extra?.plan_name as string) || '其他计划';
                  if (!planGroups[planName]) planGroups[planName] = [];
                  planGroups[planName].push(item);
                });
                return Object.entries(planGroups).map(([planName, planItems]) => (
                  <div key={`plan-${planName}`} className="mb-3 last:mb-0">
                    <div className="flex items-center mb-2">
                      <span className="text-sm mr-1">📋</span>
                      <span className="text-xs font-medium text-gray-600">{planName}</span>
                    </div>
                    {planItems.map((item) => (
                      <div key={item.id}>
                        <div
                          className="flex items-center py-1.5 ml-2 cursor-pointer"
                          onClick={() => handleQuickCheck(item)}
                        >
                          <div
                            className="w-4 h-4 rounded-full border-2 flex items-center justify-center mr-2 shrink-0"
                            style={{
                              borderColor: item.is_completed ? '#52c41a' : '#ddd',
                              background: item.is_completed ? '#52c41a' : 'transparent',
                            }}
                          >
                            {item.is_completed && <span className="text-white" style={{ fontSize: 8 }}>✓</span>}
                          </div>
                          <span className={`text-sm flex-1 ${item.is_completed ? 'text-gray-400 line-through' : ''}`}>
                            {item.name}
                            {item.remind_time && <span className="text-xs text-gray-400 ml-1">{item.remind_time}</span>}
                          </span>
                        </div>
                        {inputVisible === item.id && (
                          <div className="flex items-center ml-8 mb-1 gap-2">
                            <input
                              type="number"
                              value={inputValue}
                              onChange={(e) => setInputValue(e.target.value)}
                              placeholder={`输入${item.target_unit || '数值'}`}
                              className="flex-1 text-xs px-2 py-1.5 rounded-lg border border-gray-200"
                              autoFocus
                            />
                            <Button size="mini" color="primary" style={{ borderRadius: 6, background: '#52c41a', border: 'none', fontSize: 11 }} onClick={() => handleValueSubmit(item)}>确认</Button>
                            <Button size="mini" style={{ borderRadius: 6, fontSize: 11 }} onClick={() => { setInputVisible(null); setInputValue(''); }}>取消</Button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ));
              }

              return (
              <div key={group.group_type} className="mb-3 last:mb-0" style={{ opacity: group.is_empty ? 0.5 : 1 }}>
                <div className="flex items-center mb-2">
                  <span className="text-sm mr-1">{groupIcon}</span>
                  <span className="text-xs font-medium text-gray-600">{group.group_name}</span>
                  {group.is_empty && <span className="text-xs text-gray-300 ml-2">今日无待办</span>}
                </div>

                {group.is_empty ? (
                  <div className="text-xs text-gray-300 ml-4 mb-1">今日无待办</div>
                ) : (
                  group.items.map((item) => (
                    <div key={item.id}>
                      <div
                        className="flex items-center py-1.5 ml-2 cursor-pointer"
                        onClick={() => handleQuickCheck(item)}
                      >
                        <div
                          className="w-4 h-4 rounded-full border-2 flex items-center justify-center mr-2 shrink-0"
                          style={{
                            borderColor: item.is_completed ? '#52c41a' : '#ddd',
                            background: item.is_completed ? '#52c41a' : 'transparent',
                          }}
                        >
                          {item.is_completed && <span className="text-white" style={{ fontSize: 8 }}>✓</span>}
                        </div>
                        <span className={`text-sm flex-1 ${item.is_completed ? 'text-gray-400 line-through' : ''}`}>
                          {item.name}
                          {item.remind_time && <span className="text-xs text-gray-400 ml-1">{item.remind_time}</span>}
                        </span>
                      </div>
                      {inputVisible === item.id && (
                        <div className="flex items-center ml-8 mb-1 gap-2">
                          <input
                            type="number"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            placeholder={`输入${item.target_unit || '数值'}`}
                            className="flex-1 text-xs px-2 py-1.5 rounded-lg border border-gray-200"
                            autoFocus
                          />
                          <Button size="mini" color="primary" style={{ borderRadius: 6, background: '#52c41a', border: 'none', fontSize: 11 }} onClick={() => handleValueSubmit(item)}>确认</Button>
                          <Button size="mini" style={{ borderRadius: 6, fontSize: 11 }} onClick={() => { setInputVisible(null); setInputValue(''); }}>取消</Button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            );})
          )}

          <div className="flex items-center justify-between pt-2 mt-2 border-t border-gray-50">
            {todayTodos && todayTodos.total_count > 0 && (
              <div
                className="cursor-pointer"
                onClick={() => router.push('/health-plan/statistics')}
              >
                <span className="text-xs" style={{ color: '#52c41a' }}>📊 查看统计</span>
              </div>
            )}
            <div
              className="cursor-pointer ml-auto"
              onClick={() => router.push('/health-plan')}
            >
              <span className="text-xs font-medium" style={{ color: '#52c41a' }}>查看全部计划 &gt;</span>
            </div>
          </div>
        </div>

        {/* 商品功能优化 v1.0：首页热门推荐（带营销角标） */}
        {hotProducts.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-3">
              <span className="section-title mb-0">热门推荐</span>
              <span className="text-xs text-primary" onClick={() => router.push('/services')}>
                更多
              </span>
            </div>
            <div
              className="flex overflow-x-auto"
              style={{
                gap: 10,
                paddingBottom: 4,
                scrollbarWidth: 'none',
                WebkitOverflowScrolling: 'touch',
              }}
            >
              {hotProducts.map((p) => {
                const cover = p.cover_image || (p.images && p.images[0]) || null;
                const sellingLine = (p.selling_point || '').trim() || p.category_name || '';
                return (
                  <div
                    key={p.id}
                    onClick={() => router.push(`/product/${p.id}`)}
                    className="bg-white rounded-lg"
                    style={{
                      flex: '0 0 140px',
                      width: 140,
                      boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                      cursor: 'pointer',
                      overflow: 'hidden',
                    }}
                  >
                    <div style={{ position: 'relative', width: '100%', height: 100 }}>
                      {cover ? (
                        <img
                          src={cover}
                          alt={p.name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                        />
                      ) : (
                        <div
                          style={{
                            width: '100%', height: '100%',
                            background: 'linear-gradient(135deg, #f0fff0, #e8fce8)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 28,
                          }}
                        >🏥</div>
                      )}
                      <MarketingBadge badges={p.marketing_badges} size="sm" />
                    </div>
                    <div style={{ padding: 8 }}>
                      <div
                        style={{
                          fontSize: 13, fontWeight: 500, lineHeight: 1.3,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}
                      >
                        {p.name}
                      </div>
                      {sellingLine && (
                        <div
                          style={{
                            color: '#999', fontSize: 12, lineHeight: '16px', marginTop: 2,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}
                        >
                          {sellingLine}
                        </div>
                      )}
                      <div style={{ color: '#52c41a', fontWeight: 700, fontSize: 14, marginTop: 2 }}>
                        ¥{p.sale_price}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {latestNews.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-3">
              <span className="section-title mb-0">最新资讯</span>
              <span className="text-xs text-primary" onClick={() => router.push('/news')}>
                更多
              </span>
            </div>
            <div className="bg-white rounded-lg overflow-hidden" style={{ boxShadow: '0 1px 4px rgba(0,0,0,0.04)' }}>
              {latestNews.map((n, idx) => (
                <div
                  key={n.id}
                  className="flex items-center p-3"
                  style={{ borderBottom: idx < latestNews.length - 1 ? '1px solid #f0f0f0' : 'none', cursor: 'pointer' }}
                  onClick={() => router.push(`/news/${n.id}`)}
                >
                  {n.coverImage ? (
                    <img src={n.coverImage} alt="" className="rounded" style={{ width: 72, height: 54, objectFit: 'cover', marginRight: 10, flexShrink: 0 }} />
                  ) : (
                    <div className="rounded" style={{ width: 72, height: 54, background: '#f5f5f5', marginRight: 10, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>资讯</div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="text-sm font-medium" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {n.title}
                    </div>
                    {n.publishedAt && (
                      <div className="text-xs text-gray-400 mt-1">{new Date(n.publishedAt).toLocaleDateString('zh-CN')}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {articles.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-3">
              <span className="section-title mb-0">健康知识</span>
              <span className="text-xs text-primary" onClick={() => router.push('/articles')}>
                更多
              </span>
            </div>
            <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
              {articles.map((a) => (
                <List.Item
                  key={a.id}
                  onClick={() => router.push(`/article/${a.id}`)}
                  description={
                    <div className="flex items-center mt-1">
                      <Tag color="primary" fill="outline" style={{ '--border-radius': '4px', fontSize: 10, '--background-color': '#52c41a15', '--text-color': '#52c41a', '--border-color': '#52c41a30' }}>
                        {a.tag || '健康'}
                      </Tag>
                      <span className="text-xs text-gray-400 ml-2">{a.views ?? 0} 阅读</span>
                    </div>
                  }
                  style={{ paddingLeft: 0 }}
                >
                  <span className="text-sm font-medium">{a.title}</span>
                </List.Item>
              ))}
            </List>
          </div>
        )}
      </div>

      <div
        className="fixed right-4 bottom-24 z-50 w-12 h-12 rounded-full flex items-center justify-center shadow-lg cursor-pointer"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
        onClick={() => router.push('/invite')}
      >
        <span className="text-xl">🎁</span>
      </div>
    </div>
    </PullToRefresh>
  );
}
