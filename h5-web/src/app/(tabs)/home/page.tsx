'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Swiper, Grid, List, Tag, Badge, NoticeBar, SpinLoading, Toast, Dialog, Button } from 'antd-mobile';
import { useHomeConfig, HomeBanner, HomeMenu } from '@/lib/useHomeConfig';
import api from '@/lib/api';
import { getSelectedCity, getLocationCache, requestGeolocation, CityInfo } from '@/lib/cityUtils';

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

const articles = [
  { id: 1, title: '春季养生：这5个习惯让你元气满满', tag: '养生', views: 1230 },
  { id: 2, title: '高血压患者必知的10个饮食要点', tag: '饮食', views: 890 },
  { id: 3, title: '失眠怎么办？中医教你调理睡眠', tag: '中医', views: 2100 },
  { id: 4, title: '每天走路30分钟，身体会有哪些变化', tag: '运动', views: 1560 },
];

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

  const [cityDisplay, setCityDisplay] = useState('定位');
  const [cityStatus, setCityStatus] = useState<CityStatus>('idle');
  const cityInitRef = useRef(false);

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
    const fetchNotices = async () => {
      const now = Date.now();
      if (noticeCache && now - noticeCache.timestamp < CACHE_DURATION) {
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
    };
    fetchNotices();
    fetchTodos();
  }, [fetchTodos]);

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

  const { config, banners, menus, loading } = useHomeConfig();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <SpinLoading color="primary" />
      </div>
    );
  }

  return (
    <div className="pb-20">
      <div className="gradient-header">
        <div className="flex items-center justify-between mb-4" style={{ minHeight: 48 }}>
          <div className="flex items-center" style={{ paddingLeft: 4 }}>
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Logo"
                style={{ height: 36, width: 36, objectFit: 'contain', borderRadius: 8, display: 'block' }}
              />
            ) : (
              <h1 className="text-xl font-bold">宾尼小康</h1>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center cursor-pointer"
              onClick={() => router.push('/scan')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 7V5a2 2 0 0 1 2-2h2" />
                <path d="M17 3h2a2 2 0 0 1 2 2v2" />
                <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
                <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
                <line x1="7" y1="12" x2="17" y2="12" />
              </svg>
            </div>
            <Badge content={unreadCount > 0 ? (unreadCount > 99 ? '99+' : unreadCount) : null} style={{ '--right': '-2px', '--top': '2px' }}>
              <div
                className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center cursor-pointer"
                onClick={() => router.push('/messages')}
              >
                <span className="text-white text-sm">🔔</span>
              </div>
            </Badge>
          </div>
        </div>
        {config.search_visible && (
          <div
            className="flex items-center"
            style={{
              height: 36,
              borderRadius: 20,
              background: '#E8F7EE',
            }}
          >
            <div
              className="flex items-center shrink-0 pl-3 pr-2"
              style={{
                cursor: cityStatus === 'locating' ? 'default' : 'pointer',
                maxWidth: 90,
              }}
              onClick={() => {
                if (cityStatus === 'locating') return;
                router.push('/city-select');
              }}
            >
              <span
                className="text-sm font-medium truncate"
                style={{ color: '#389e0d', maxWidth: 64, display: 'inline-block' }}
              >
                {cityDisplay.length > 4 ? cityDisplay.slice(0, 4) + '…' : cityDisplay}
              </span>
              {cityStatus !== 'locating' && (
                <span className="text-xs ml-0.5" style={{ color: '#52c41a' }}>▼</span>
              )}
            </div>
            <div style={{ width: 1, height: 16, background: 'rgba(82,196,26,0.25)' }} />
            <div
              className="flex-1 flex items-center px-3 cursor-pointer"
              onClick={() => router.push('/search')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span className="ml-2 text-sm" style={{ color: '#86909C' }}>{config.search_placeholder || '搜索您想要的健康服务'}</span>
            </div>
          </div>
        )}
      </div>

      <div className="px-4 -mt-2">
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

        {banners.length > 0 && (
          <Swiper
            autoplay
            loop
            style={{ '--border-radius': '12px', marginBottom: 16 }}
          >
            {banners.map((b: HomeBanner, idx: number) => (
              <Swiper.Item key={b.id}>
                <div
                  className="h-36 rounded-xl overflow-hidden cursor-pointer"
                  onClick={() => handleLink(b.link_type, b.link_url, router)}
                >
                  {b.image_url ? (
                    <img
                      src={b.image_url}
                      alt=""
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div
                      className="h-full flex flex-col justify-center px-6"
                      style={{
                        background: `linear-gradient(135deg, ${FALLBACK_COLORS[idx % FALLBACK_COLORS.length]}, ${FALLBACK_COLORS[idx % FALLBACK_COLORS.length]}88)`,
                      }}
                    >
                      <h3 className="text-white text-lg font-bold">宾尼小康</h3>
                      <p className="text-white/80 text-sm mt-1">AI健康管家</p>
                      <div className="mt-3">
                        <span className="bg-white/20 text-white text-xs px-3 py-1 rounded-full">
                          立即体验 →
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </Swiper.Item>
            ))}
          </Swiper>
        )}

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
                      {a.tag}
                    </Tag>
                    <span className="text-xs text-gray-400 ml-2">{a.views} 阅读</span>
                  </div>
                }
                style={{ paddingLeft: 0 }}
              >
                <span className="text-sm font-medium">{a.title}</span>
              </List.Item>
            ))}
          </List>
        </div>
      </div>

      <div
        className="fixed right-4 bottom-24 z-50 w-12 h-12 rounded-full flex items-center justify-center shadow-lg cursor-pointer"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
        onClick={() => router.push('/invite')}
      >
        <span className="text-xl">🎁</span>
      </div>
    </div>
  );
}
