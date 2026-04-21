'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Tag, Empty, InfiniteScroll, SpinLoading } from 'antd-mobile';
import api from '@/lib/api';

interface ArticleRow {
  id: number;
  title: string;
  summary?: string;
  category?: string;
  tags?: string[];
  view_count?: number;
  cover_image?: string;
  published_at?: string;
  created_at?: string;
}

const tagColors: Record<string, string> = {
  养生: '#52c41a',
  饮食: '#fa8c16',
  中医: '#eb2f96',
  运动: '#1890ff',
  保健: '#722ed1',
};

export default function ArticlesPage() {
  const router = useRouter();
  const [items, setItems] = useState<ArticleRow[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  const loadMore = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res: any = await api.get(`/api/content/articles?page=${page}&page_size=10`);
      const data: ArticleRow[] = res?.items ?? res?.data?.items ?? [];
      setItems((prev) => [...prev, ...data]);
      setPage(page + 1);
      setHasMore(data.length >= 10);
    } catch {
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [page, loading]);

  useEffect(() => {
    if (items.length === 0 && page === 1) {
      loadMore();
    }
  }, [items.length, page, loadMore]);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        健康知识
      </NavBar>

      <div className="px-4 pt-3">
        {items.length === 0 && !loading ? (
          <Empty description="暂无内容" style={{ padding: '80px 0' }} />
        ) : (
          items.map((item) => {
            const tagName = item.category || (item.tags && item.tags[0]) || '健康';
            return (
              <Card
                key={item.id}
                onClick={() => router.push(`/article/${item.id}`)}
                style={{ marginBottom: 12, borderRadius: 12 }}
              >
                <div className="flex">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm line-clamp-2">{item.title}</div>
                    {item.summary && (
                      <div className="text-xs text-gray-500 mt-1 line-clamp-2">{item.summary}</div>
                    )}
                    <div className="flex items-center mt-2">
                      <Tag
                        style={{
                          '--background-color': `${tagColors[tagName] || '#52c41a'}15`,
                          '--text-color': tagColors[tagName] || '#52c41a',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        {tagName}
                      </Tag>
                      <span className="text-xs text-gray-400 ml-2">{item.view_count ?? 0} 阅读</span>
                      {(item.published_at || item.created_at) && (
                        <span className="text-xs text-gray-300 ml-2">
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
                      📄
                    </div>
                  )}
                </div>
              </Card>
            );
          })
        )}
        <InfiniteScroll loadMore={loadMore} hasMore={hasMore}>
          {hasMore ? <SpinLoading color="primary" /> : <span className="text-xs text-gray-400">没有更多了</span>}
        </InfiniteScroll>
      </div>
    </div>
  );
}
