'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  NavBar,
  Tabs,
  Card,
  Image,
  Empty,
  SpinLoading,
  InfiniteScroll,
  SwipeAction,
  Toast,
} from 'antd-mobile';
import api from '@/lib/api';

interface FavoriteItem {
  id: number;
  content_type: string;
  content_id: number;
  created_at: string;
  detail: {
    id: number;
    name?: string;
    title?: string;
    sale_price?: number;
    images?: string[] | null;
    cover_image?: string | null;
    summary?: string | null;
    status?: string;
  } | null;
}

export default function MyFavoritesPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('product');
  const [items, setItems] = useState<FavoriteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const fetchFavorites = useCallback(async (pageNum: number, reset = false) => {
    try {
      const res: any = await api.get(`/api/favorites?tab=${activeTab}&page=${pageNum}&page_size=20`);
      const data = res.data || res;
      const list = data.items || [];
      if (reset) {
        setItems(list);
      } else {
        setItems((prev) => [...prev, ...list]);
      }
      setHasMore(pageNum * 20 < (data.total || 0));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    fetchFavorites(1, true);
  }, [fetchFavorites]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await fetchFavorites(next);
  };

  const handleRemove = async (item: FavoriteItem) => {
    try {
      await api.post(`/api/favorites?content_type=${item.content_type}&content_id=${item.content_id}`);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      Toast.show({ content: '已取消收藏' });
    } catch {
      Toast.show({ content: '操作失败' });
    }
  };

  const handleClick = (item: FavoriteItem) => {
    if (item.content_type === 'product' && item.detail) {
      router.push(`/product/${item.detail.id}`);
    } else if (['article', 'knowledge'].includes(item.content_type) && item.detail) {
      router.push(`/article/${item.detail.id}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        我的收藏
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
        <Tabs.Tab key="product" title="商品收藏" />
        <Tabs.Tab key="knowledge" title="知识收藏" />
      </Tabs>

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : items.length === 0 ? (
          <Empty description="暂无收藏" style={{ padding: '80px 0' }} />
        ) : (
          items.map((item) => (
            <SwipeAction
              key={item.id}
              rightActions={[
                {
                  key: 'delete',
                  text: '取消收藏',
                  color: 'danger',
                  onClick: () => handleRemove(item),
                },
              ]}
              style={{ marginBottom: 12 }}
            >
              <Card
                onClick={() => handleClick(item)}
                style={{ borderRadius: 12 }}
              >
                <div className="flex">
                  <div className="w-20 h-20 rounded-lg flex-shrink-0 overflow-hidden">
                    {activeTab === 'product' && item.detail ? (
                      item.detail.images && item.detail.images.length > 0 ? (
                        <Image src={item.detail.images[0]} width={80} height={80} fit="cover" style={{ borderRadius: 8 }} />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: '#f6ffed' }}>🛍️</div>
                      )
                    ) : item.detail?.cover_image ? (
                      <Image src={item.detail.cover_image} width={80} height={80} fit="cover" style={{ borderRadius: 8 }} />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: '#f0f5ff' }}>📄</div>
                    )}
                  </div>
                  <div className="flex-1 ml-3 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {item.detail?.name || item.detail?.title || '已删除的内容'}
                    </div>
                    {activeTab === 'product' && item.detail?.sale_price !== undefined && (
                      <div className="text-red-500 font-bold text-sm mt-1">¥{item.detail.sale_price}</div>
                    )}
                    {activeTab === 'knowledge' && item.detail?.summary && (
                      <div className="text-xs text-gray-400 mt-1 line-clamp-2">{item.detail.summary}</div>
                    )}
                    <div className="text-xs text-gray-300 mt-1">
                      {item.created_at ? new Date(item.created_at).toLocaleDateString('zh-CN') : ''}
                    </div>
                  </div>
                </div>
              </Card>
            </SwipeAction>
          ))
        )}
        {!loading && items.length > 0 && (
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        )}
      </div>
    </div>
  );
}
