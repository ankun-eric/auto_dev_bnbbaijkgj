'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Tabs, Card, Tag, Empty, InfiniteScroll } from 'antd-mobile';

const mockArticles = [
  { id: 1, title: '春季养生：这5个习惯让你元气满满', tag: '养生', views: 1230, time: '2024-03-15', type: 'article' },
  { id: 2, title: '高血压患者必知的10个饮食要点', tag: '饮食', views: 890, time: '2024-03-14', type: 'article' },
  { id: 3, title: '失眠怎么办？中医教你调理睡眠', tag: '中医', views: 2100, time: '2024-03-13', type: 'article' },
  { id: 4, title: '每天走路30分钟，身体会有哪些变化', tag: '运动', views: 1560, time: '2024-03-12', type: 'article' },
  { id: 5, title: '糖尿病人的饮食红绿灯', tag: '饮食', views: 980, time: '2024-03-11', type: 'article' },
  { id: 6, title: '办公室久坐的危害及缓解方法', tag: '保健', views: 750, time: '2024-03-10', type: 'article' },
];

const mockVideos = [
  { id: 101, title: '5分钟办公室颈椎操', tag: '运动', views: 5200, time: '2024-03-15', type: 'video', duration: '5:30' },
  { id: 102, title: '八段锦完整教学', tag: '中医', views: 8900, time: '2024-03-14', type: 'video', duration: '15:20' },
  { id: 103, title: '健康早餐搭配指南', tag: '饮食', views: 3400, time: '2024-03-13', type: 'video', duration: '8:45' },
];

const tagColors: Record<string, string> = {
  养生: '#52c41a',
  饮食: '#fa8c16',
  中医: '#eb2f96',
  运动: '#1890ff',
  保健: '#722ed1',
};

export default function ArticlesPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('article');
  const [hasMore, setHasMore] = useState(false);

  const items = activeTab === 'article' ? mockArticles : mockVideos;

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        健康知识
      </NavBar>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          background: '#fff',
        }}
      >
        <Tabs.Tab key="article" title="文章" />
        <Tabs.Tab key="video" title="视频" />
      </Tabs>

      <div className="px-4 pt-3">
        {items.length === 0 ? (
          <Empty description="暂无内容" style={{ padding: '80px 0' }} />
        ) : (
          items.map((item: any) => (
            <Card
              key={item.id}
              onClick={() => router.push(`/article/${item.id}`)}
              style={{ marginBottom: 12, borderRadius: 12 }}
            >
              <div className="flex">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm line-clamp-2">{item.title}</div>
                  <div className="flex items-center mt-2">
                    <Tag
                      style={{
                        '--background-color': `${tagColors[item.tag] || '#999'}15`,
                        '--text-color': tagColors[item.tag] || '#999',
                        '--border-color': 'transparent',
                        fontSize: 10,
                      }}
                    >
                      {item.tag}
                    </Tag>
                    <span className="text-xs text-gray-400 ml-2">{item.views} 阅读</span>
                    <span className="text-xs text-gray-300 ml-2">{item.time}</span>
                  </div>
                </div>
                <div
                  className="w-20 h-16 rounded-lg ml-3 flex items-center justify-center text-2xl flex-shrink-0"
                  style={{ background: '#f6ffed' }}
                >
                  {item.type === 'video' ? '🎬' : '📄'}
                </div>
              </div>
              {item.duration && (
                <div className="text-xs text-gray-400 mt-1">时长：{item.duration}</div>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
