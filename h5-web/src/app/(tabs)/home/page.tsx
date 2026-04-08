'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Swiper, Grid, List, Tag, Badge, NoticeBar, SpinLoading } from 'antd-mobile';
import { useHomeConfig, HomeBanner, HomeMenu } from '@/lib/useHomeConfig';
import { useFontSize } from '@/lib/useFontSize';
import FontSettingPopup from '@/components/FontSettingPopup';

const articles = [
  { id: 1, title: '春季养生：这5个习惯让你元气满满', tag: '养生', views: 1230 },
  { id: 2, title: '高血压患者必知的10个饮食要点', tag: '饮食', views: 890 },
  { id: 3, title: '失眠怎么办？中医教你调理睡眠', tag: '中医', views: 2100 },
  { id: 4, title: '每天走路30分钟，身体会有哪些变化', tag: '运动', views: 1560 },
];

const tasks = [
  { id: 1, title: '今日步数 8000步', done: false },
  { id: 2, title: '饮水 2000ml', done: false },
  { id: 3, title: '午休 30分钟', done: true },
];

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

export default function HomePage() {
  const router = useRouter();

  const [fontPopupVisible, setFontPopupVisible] = useState(false);

  const { config, banners, menus, loading } = useHomeConfig();
  const { fontLevel, fontSize, setFontLevel, fontSwitchEnabled } = useFontSize({
    font_switch_enabled: config.font_switch_enabled,
    font_default_level: config.font_default_level,
    font_standard_size: config.font_standard_size,
    font_large_size: config.font_large_size,
    font_xlarge_size: config.font_xlarge_size,
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <SpinLoading color="primary" />
      </div>
    );
  }

  return (
    <div className="pb-20" style={{ fontSize }}>
      <div className="gradient-header">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold">宾尼小康</h1>
            <p className="text-xs opacity-80 mt-1">AI健康管家 · 关爱您的每一天</p>
          </div>
          <div className="flex items-center gap-2">
            {fontSwitchEnabled && (
              <div
                className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center cursor-pointer"
                onClick={() => setFontPopupVisible(true)}
              >
                <span className="text-white text-sm font-bold">Aa</span>
              </div>
            )}
            <Badge content="3" style={{ '--right': '-2px', '--top': '2px' }}>
              <div
                className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center"
                onClick={() => router.push('/notifications')}
              >
                <span className="text-white text-sm">🔔</span>
              </div>
            </Badge>
          </div>
        </div>
        {config.search_visible && (
          <div
            className="flex items-center px-4 cursor-pointer"
            style={{
              height: 36,
              borderRadius: 20,
              background: 'rgba(255,255,255,0.9)',
            }}
            onClick={() => router.push('/search')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span className="ml-2 text-sm text-gray-400">搜索文章、视频、服务、商品</span>
          </div>
        )}
      </div>

      <div className="px-4 -mt-2">
        <NoticeBar
          content="宾尼小康提醒您：定期体检，关注健康，预防疾病。"
          color="info"
          style={{ borderRadius: 8, marginBottom: 12, fontSize: 12 }}
        />

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
            <span className="section-title mb-0">每日健康任务</span>
            <span className="text-xs text-primary" onClick={() => router.push('/health-plan')}>
              查看全部
            </span>
          </div>
          {tasks.map((t) => (
            <div key={t.id} className="flex items-center py-2 border-b border-gray-50 last:border-b-0">
              <div
                className="w-5 h-5 rounded-full border-2 flex items-center justify-center mr-3"
                style={{
                  borderColor: t.done ? '#52c41a' : '#ddd',
                  background: t.done ? '#52c41a' : 'transparent',
                }}
              >
                {t.done && <span className="text-white text-xs">✓</span>}
              </div>
              <span className={`text-sm ${t.done ? 'text-gray-400 line-through' : 'text-gray-700'}`}>
                {t.title}
              </span>
            </div>
          ))}
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

      <FontSettingPopup
        visible={fontPopupVisible}
        onClose={() => setFontPopupVisible(false)}
        fontLevel={fontLevel}
        onFontLevelChange={setFontLevel}
        standardSize={config.font_standard_size}
        largeSize={config.font_large_size}
        xlargeSize={config.font_xlarge_size}
      />
    </div>
  );
}
