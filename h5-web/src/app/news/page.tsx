'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Tag, Empty, InfiniteScroll, SpinLoading, SearchBar } from 'antd-mobile';
import api from '@/lib/api';

interface NewsRow {
  id: number;
  title: string;
  summary?: string;
  cover_image?: string;
  source?: string;
  tags?: string[];
  view_count?: number;
  is_top?: boolean;
  published_at?: string;
  created_at?: string;
}

export default function NewsListPage() {
  const router = useRouter();
  const [items, setItems] = useState<NewsRow[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');

  const reload = useCallback(async (kw: string) => {
    setLoading(true);
    try {
      const q = kw ? `&keyword=${encodeURIComponent(kw)}` : '';
      const res: any = await api.get(`/api/content/news?page=1&page_size=10${q}`);
      const data: NewsRow[] = res?.items ?? res?.data?.items ?? [];
      setItems(data);
      setPage(2);
      setHasMore(data.length >= 10);
    } catch {
      setItems([]);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      const q = keyword ? `&keyword=${encodeURIComponent(keyword)}` : '';
      const res: any = await api.get(`/api/content/news?page=${page}&page_size=10${q}`);
      const data: NewsRow[] = res?.items ?? res?.data?.items ?? [];
      setItems((prev) => [...prev, ...data]);
      setPage(page + 1);
      setHasMore(data.length >= 10);
    } catch {
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [page, loading, keyword]);

  useEffect(() => {
    reload('');
  }, [reload]);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        最新资讯
      </NavBar>

      <div className="px-3 py-2 bg-white">
        <SearchBar
          placeholder="搜索资讯"
          value={keyword}
          onChange={setKeyword}
          onSearch={(val) => reload(val)}
          onClear={() => reload('')}
        />
      </div>

      <div className="px-4 pt-3">
        {items.length === 0 && !loading ? (
          <Empty description="暂无资讯" style={{ padding: '80px 0' }} />
        ) : (
          items.map((item) => (
            <Card
              key={item.id}
              onClick={() => router.push(`/news/${item.id}`)}
              style={{ marginBottom: 12, borderRadius: 12 }}
            >
              <div className="flex">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    {item.is_top && (
                      <span className="text-xs px-1 rounded" style={{ background: '#ff4d4f', color: '#fff' }}>置顶</span>
                    )}
                    <div className="font-medium text-sm line-clamp-2">{item.title}</div>
                  </div>
                  {item.summary && (
                    <div className="text-xs text-gray-500 mt-1 line-clamp-2">{item.summary}</div>
                  )}
                  <div className="flex items-center flex-wrap gap-1 mt-2">
                    {item.tags && item.tags.slice(0, 2).map((t) => (
                      <Tag
                        key={t}
                        style={{
                          '--background-color': '#52c41a15',
                          '--text-color': '#52c41a',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        {t}
                      </Tag>
                    ))}
                    {item.source && <span className="text-xs text-gray-400">{item.source}</span>}
                    <span className="text-xs text-gray-400">{item.view_count ?? 0} 阅读</span>
                    {(item.published_at || item.created_at) && (
                      <span className="text-xs text-gray-300">
                        {new Date((item.published_at || item.created_at) as string).toLocaleDateString('zh-CN')}
                      </span>
                    )}
                  </div>
                </div>
                {item.cover_image ? (
                  <img
                    src={item.cover_image}
                    alt=""
                    className="rounded-lg ml-3 flex-shrink-0"
                    style={{ width: 80, height: 64, objectFit: 'cover' }}
                  />
                ) : (
                  <div
                    className="w-20 h-16 rounded-lg ml-3 flex items-center justify-center text-2xl flex-shrink-0"
                    style={{ background: '#f6ffed' }}
                  >
                    📰
                  </div>
                )}
              </div>
            </Card>
          ))
        )}
        <InfiniteScroll loadMore={loadMore} hasMore={hasMore}>
          {hasMore ? <SpinLoading color="primary" /> : <span className="text-xs text-gray-400">没有更多了</span>}
        </InfiniteScroll>
      </div>
    </div>
  );
}
