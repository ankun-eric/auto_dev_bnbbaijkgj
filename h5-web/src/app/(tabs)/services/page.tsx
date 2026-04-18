'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, Card, Tag, SearchBar, Empty, SpinLoading, InfiniteScroll } from 'antd-mobile';
import api from '@/lib/api';

interface Category {
  id: number;
  name: string;
  icon?: string | null;
  sort_order?: number;
  parent_id?: number | null;
}

interface Product {
  id: number;
  name: string;
  description?: string | null;
  sale_price: number;
  market_price?: number | null;
  cover_image?: string | null;
  images?: string[];
  sales_count?: number;
  category_id?: number;
}

const PAGE_SIZE = 10;

export default function ServicesPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [activeKey, setActiveKey] = useState<string>('');
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    api.get('/api/products/categories')
      .then((res: any) => {
        const data = res.data || res;
        const items: Category[] = (data.items || []).filter((c: Category) => !c.parent_id);
        setCategories(items);
        if (items.length > 0 && !activeKey) {
          setActiveKey(String(items[0].id));
        }
      })
      .catch(() => {});
  }, []);

  const loadProducts = useCallback(
    async (categoryId: string, pageNum: number, reset: boolean) => {
      if (!categoryId) return;
      try {
        const res: any = await api.get(
          `/api/products?category_id=${categoryId}&page=${pageNum}&page_size=${PAGE_SIZE}`
        );
        const data = res.data || res;
        const items: Product[] = data.items || [];
        if (reset) {
          setProducts(items);
        } else {
          setProducts((prev) => [...prev, ...items]);
        }
        const total = Number(data.total || 0);
        setHasMore(pageNum * PAGE_SIZE < total);
      } catch {
        if (reset) setProducts([]);
        setHasMore(false);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!activeKey) return;
    setLoading(true);
    setPage(1);
    loadProducts(activeKey, 1, true);
  }, [activeKey, loadProducts]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await loadProducts(activeKey, next, false);
  };

  const filteredProducts = search
    ? products.filter(
        (p) => p.name.includes(search) || (p.description || '').includes(search)
      )
    : products;

  const currentCategory = categories.find((c) => String(c.id) === activeKey);

  return (
    <div className="pb-20">
      <div className="gradient-header pb-4">
        <h1 className="text-xl font-bold mb-3">健康服务</h1>
        <SearchBar
          placeholder="搜索服务"
          value={search}
          onChange={setSearch}
          style={{
            '--border-radius': '20px',
            '--background': 'rgba(255,255,255,0.9)',
            '--height': '36px',
          }}
        />
      </div>

      {categories.length > 0 && (
        <Tabs
          activeKey={activeKey}
          onChange={setActiveKey}
          style={{
            '--active-line-color': '#52c41a',
            '--active-title-color': '#52c41a',
            position: 'sticky',
            top: 0,
            zIndex: 10,
            background: '#fff',
          }}
        >
          {categories.map((cat) => (
            <Tabs.Tab key={String(cat.id)} title={cat.name} />
          ))}
        </Tabs>
      )}

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : filteredProducts.length === 0 ? (
          <Empty description="暂无相关服务" />
        ) : (
          filteredProducts.map((p) => {
            const cover = p.cover_image || (p.images && p.images[0]) || null;
            const icon = currentCategory?.icon || '🏥';
            return (
              <Card
                key={p.id}
                onClick={() => router.push(`/product/${p.id}`)}
                style={{ marginBottom: 12, borderRadius: 12 }}
              >
                <div className="flex">
                  {cover ? (
                    <img
                      src={cover}
                      alt={p.name}
                      className="w-24 h-24 rounded-lg object-cover flex-shrink-0"
                    />
                  ) : (
                    <div
                      className="w-24 h-24 rounded-lg flex items-center justify-center text-3xl flex-shrink-0"
                      style={{ background: 'linear-gradient(135deg, #f0fff0, #e8fce8)' }}
                    >
                      {icon}
                    </div>
                  )}
                  <div className="flex-1 ml-3 min-w-0">
                    <div className="flex items-center">
                      <span className="font-medium text-sm truncate">{p.name}</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">{p.description || ''}</p>
                    <div className="flex items-end justify-between mt-3">
                      <div>
                        <span className="text-primary font-bold">¥{Number(p.sale_price).toFixed(2)}</span>
                        {p.market_price && Number(p.market_price) > Number(p.sale_price) && (
                          <span className="text-xs text-gray-300 line-through ml-1">
                            ¥{Number(p.market_price).toFixed(2)}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-400">已售{p.sales_count || 0}</span>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })
        )}
        {!loading && filteredProducts.length > 0 && !search && (
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        )}
      </div>
    </div>
  );
}
