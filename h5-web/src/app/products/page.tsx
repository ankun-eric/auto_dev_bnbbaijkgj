'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  NavBar,
  SearchBar,
  Tabs,
  Card,
  Tag,
  Image,
  Dropdown,
  Radio,
  Space,
  InfiniteScroll,
  Empty,
  SpinLoading,
  Checkbox,
} from 'antd-mobile';
import { DownOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface Category {
  id: number;
  name: string;
  parent_id: number | null;
  children: Category[];
}

interface Product {
  id: number;
  name: string;
  category_id: number;
  fulfillment_type: string;
  original_price: number | null;
  sale_price: number;
  images: string[] | null;
  sales_count: number;
  points_exchangeable: boolean;
  points_price: number;
  status: string;
}

export default function ProductsPage() {
  const router = useRouter();
  const [keyword, setKeyword] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);
  const [activeCat, setActiveCat] = useState<string>('all');
  const [activeSubCat, setActiveSubCat] = useState<number | null>(null);
  const [fulfillmentType, setFulfillmentType] = useState<string>('');
  const [pointsExchangeable, setPointsExchangeable] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/products/categories').then((res: any) => {
      const data = res.data || res;
      setCategories(data.items || []);
    }).catch(() => {});
  }, []);

  const subCategories = categories.find((c) => String(c.id) === activeCat)?.children || [];

  const fetchProducts = useCallback(async (pageNum: number, reset = false) => {
    try {
      const params: Record<string, any> = { page: pageNum, page_size: 20 };
      if (activeSubCat) {
        params.category_id = activeSubCat;
      } else if (activeCat !== 'all') {
        params.category_id = activeCat;
      }
      if (fulfillmentType) params.fulfillment_type = fulfillmentType;
      if (pointsExchangeable) params.points_exchangeable = true;
      if (keyword) params.keyword = keyword;

      const res: any = await api.get('/api/products', { params });
      const data = res.data || res;
      const items = data.items || [];
      if (reset) {
        setProducts(items);
      } else {
        setProducts((prev) => [...prev, ...items]);
      }
      setTotal(data.total || 0);
      setHasMore(pageNum * 20 < (data.total || 0));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeCat, activeSubCat, fulfillmentType, pointsExchangeable, keyword]);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    fetchProducts(1, true);
  }, [fetchProducts]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await fetchProducts(next);
  };

  const fulfillmentLabel = (type: string) => {
    const map: Record<string, string> = { in_store: '到店', delivery: '快递', virtual: '虚拟' };
    return map[type] || type;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        商品列表
      </NavBar>

      <div className="px-3 py-2 bg-white">
        <SearchBar
          placeholder="搜索商品"
          value={keyword}
          onChange={setKeyword}
          onSearch={() => { setPage(1); fetchProducts(1, true); }}
          style={{ '--border-radius': '20px', '--background': '#f5f5f5', '--height': '36px' }}
        />
      </div>

      <Tabs
        activeKey={activeCat}
        onChange={(key) => { setActiveCat(key); setActiveSubCat(null); }}
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          background: '#fff',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <Tabs.Tab key="all" title="全部" />
        {categories.map((cat) => (
          <Tabs.Tab key={String(cat.id)} title={cat.name} />
        ))}
      </Tabs>

      {subCategories.length > 0 && (
        <div className="flex gap-2 px-3 py-2 bg-white border-b border-gray-50 overflow-x-auto">
          <Tag
            onClick={() => setActiveSubCat(null)}
            style={{
              '--background-color': !activeSubCat ? '#52c41a' : '#f5f5f5',
              '--text-color': !activeSubCat ? '#fff' : '#666',
              '--border-color': 'transparent',
              flexShrink: 0,
            }}
          >
            全部
          </Tag>
          {subCategories.map((sub) => (
            <Tag
              key={sub.id}
              onClick={() => setActiveSubCat(sub.id)}
              style={{
                '--background-color': activeSubCat === sub.id ? '#52c41a' : '#f5f5f5',
                '--text-color': activeSubCat === sub.id ? '#fff' : '#666',
                '--border-color': 'transparent',
                flexShrink: 0,
              }}
            >
              {sub.name}
            </Tag>
          ))}
        </div>
      )}

      <div className="flex gap-2 px-3 py-2 bg-white border-b border-gray-100">
        <Dropdown>
          <Dropdown.Item key="fulfillment" title={fulfillmentType ? fulfillmentLabel(fulfillmentType) : '履约方式'}>
            <div className="p-3">
              <Radio.Group
                value={fulfillmentType}
                onChange={(val) => setFulfillmentType(val as string)}
              >
                <Space direction="vertical" block>
                  <Radio value="">全部</Radio>
                  <Radio value="on_site">{fulfillmentLabel('on_site')}</Radio>
                  <Radio value="in_store">{fulfillmentLabel('in_store')}</Radio>
                  <Radio value="delivery">{fulfillmentLabel('delivery')}</Radio>
                  <Radio value="virtual">{fulfillmentLabel('virtual')}</Radio>
                </Space>
              </Radio.Group>
            </div>
          </Dropdown.Item>
        </Dropdown>
        <Checkbox
          checked={pointsExchangeable}
          onChange={setPointsExchangeable}
          style={{ '--icon-size': '16px', '--font-size': '12px', fontSize: 12 }}
        >
          积分可兑
        </Checkbox>
      </div>

      <div className="px-3 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : products.length === 0 ? (
          <Empty description="暂无商品" style={{ padding: '80px 0' }} />
        ) : (
          products.map((p) => (
            <Card
              key={p.id}
              onClick={() => router.push(`/product/${p.id}`)}
              style={{ marginBottom: 12, borderRadius: 12 }}
            >
              <div className="flex">
                <div className="w-24 h-24 rounded-lg flex-shrink-0 overflow-hidden">
                  {p.images && p.images.length > 0 ? (
                    <Image src={p.images[0]} width={96} height={96} fit="cover" style={{ borderRadius: 8 }} />
                  ) : (
                    <div
                      className="w-full h-full flex items-center justify-center text-3xl"
                      style={{ background: 'linear-gradient(135deg, #f0fff0, #e8fce8)' }}
                    >
                      🛍️
                    </div>
                  )}
                </div>
                <div className="flex-1 ml-3 min-w-0">
                  <div className="flex items-center">
                    <span className="font-medium text-sm truncate">{p.name}</span>
                    {p.points_exchangeable && (
                      <Tag
                        style={{
                          '--background-color': '#fa8c1615',
                          '--text-color': '#fa8c16',
                          '--border-color': 'transparent',
                          fontSize: 10,
                          marginLeft: 6,
                        }}
                      >
                        积分兑
                      </Tag>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {fulfillmentLabel(p.fulfillment_type)}
                  </div>
                  <div className="flex items-end justify-between mt-3">
                    <div>
                      <span className="text-red-500 font-bold">¥{p.sale_price}</span>
                      {p.original_price && p.original_price > p.sale_price && (
                        <span className="text-xs text-gray-300 line-through ml-1">¥{p.original_price}</span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">已售{p.sales_count}</span>
                  </div>
                </div>
              </div>
            </Card>
          ))
        )}
        {!loading && products.length > 0 && (
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        )}
      </div>
    </div>
  );
}
