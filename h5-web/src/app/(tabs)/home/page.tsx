'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { SearchBar, Swiper, Grid, Card, List, Tag, Badge, NoticeBar } from 'antd-mobile';
import {
  MessageOutline,
  FileOutline,
  SearchOutline,
  HeartOutline,
  AppstoreOutline,
  CheckShieldOutline,
} from 'antd-mobile-icons';

const banners = [
  { id: 1, title: 'AI健康咨询', desc: '7×24小时在线健康咨询', color: '#52c41a' },
  { id: 2, title: '中医养生', desc: '中医养生体质调理', color: '#13c2c2' },
  { id: 3, title: '健康计划', desc: '个性化健康管理方案', color: '#1890ff' },
];

const features = [
  { icon: <MessageOutline style={{ fontSize: 24 }} />, title: 'AI健康咨询', path: '/ai', color: '#52c41a' },
  { icon: <FileOutline style={{ fontSize: 24 }} />, title: '体检报告', path: '/checkup', color: '#1890ff' },
  { icon: <SearchOutline style={{ fontSize: 24 }} />, title: '健康自查', path: '/symptom', color: '#722ed1' },
  { icon: <HeartOutline style={{ fontSize: 24 }} />, title: '中医养生', path: '/tcm', color: '#eb2f96' },
  { icon: <AppstoreOutline style={{ fontSize: 24 }} />, title: '用药参考', path: '/drug', color: '#fa8c16' },
  { icon: <CheckShieldOutline style={{ fontSize: 24 }} />, title: '健康计划', path: '/health-plan', color: '#13c2c2' },
];

const articles = [
  { id: 1, title: '春季养生：这5个习惯让你元气满满', tag: '养生', image: '', views: 1230 },
  { id: 2, title: '高血压患者必知的10个饮食要点', tag: '饮食', image: '', views: 890 },
  { id: 3, title: '失眠怎么办？中医教你调理睡眠', tag: '中医', image: '', views: 2100 },
  { id: 4, title: '每天走路30分钟，身体会有哪些变化', tag: '运动', image: '', views: 1560 },
];

const tasks = [
  { id: 1, title: '今日步数 8000步', done: false },
  { id: 2, title: '饮水 2000ml', done: false },
  { id: 3, title: '午休 30分钟', done: true },
];

export default function HomePage() {
  const router = useRouter();
  const [searchVal, setSearchVal] = useState('');

  return (
    <div className="pb-20">
      <div className="gradient-header">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold">宾尼小康</h1>
            <p className="text-xs opacity-80 mt-1">AI健康管家 · 关爱您的每一天</p>
          </div>
          <Badge content="3" style={{ '--right': '-2px', '--top': '2px' }}>
            <div
              className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center"
              onClick={() => router.push('/notifications')}
            >
              <span className="text-white text-sm">🔔</span>
            </div>
          </Badge>
        </div>
        <SearchBar
          placeholder="搜索症状、疾病、药品"
          value={searchVal}
          onChange={setSearchVal}
          style={{
            '--border-radius': '20px',
            '--background': 'rgba(255,255,255,0.9)',
            '--height': '36px',
          }}
          onSearch={() => router.push(`/drug?q=${searchVal}`)}
        />
      </div>

      <div className="px-4 -mt-2">
        <NoticeBar
          content="宾尼小康提醒您：定期体检，关注健康，预防疾病。"
          color="info"
          style={{ borderRadius: 8, marginBottom: 12, fontSize: 12 }}
        />

        <Swiper
          autoplay
          loop
          style={{ '--border-radius': '12px', marginBottom: 16 }}
        >
          {banners.map((b) => (
            <Swiper.Item key={b.id}>
              <div
                className="h-36 rounded-xl flex flex-col justify-center px-6"
                style={{ background: `linear-gradient(135deg, ${b.color}, ${b.color}88)` }}
              >
                <h3 className="text-white text-lg font-bold">{b.title}</h3>
                <p className="text-white/80 text-sm mt-1">{b.desc}</p>
                <div className="mt-3">
                  <span className="bg-white/20 text-white text-xs px-3 py-1 rounded-full">
                    立即体验 →
                  </span>
                </div>
              </div>
            </Swiper.Item>
          ))}
        </Swiper>

        <div className="card">
          <div className="section-title">功能入口</div>
          <Grid columns={3} gap={16}>
            {features.map((f, i) => (
              <Grid.Item key={i} onClick={() => router.push(f.path)}>
                <div className="flex flex-col items-center py-2">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center mb-2"
                    style={{ background: `${f.color}15`, color: f.color }}
                  >
                    {f.icon}
                  </div>
                  <span className="text-xs text-gray-600">{f.title}</span>
                </div>
              </Grid.Item>
            ))}
          </Grid>
        </div>

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
    </div>
  );
}
