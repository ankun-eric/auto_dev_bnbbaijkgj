'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { SearchBar, Empty, SpinLoading, InfiniteScroll, Toast } from 'antd-mobile';
import api from '@/lib/api';
import MarketingBadge from '@/components/MarketingBadge';

/**
 * 改造④：用户端首页·服务列表
 *
 * 形态（京东/淘宝分类页风格）：
 * ┌────────────────────────────────────┐
 * │ [🔍 搜索全部服务/商品]              │ ← 顶部常驻搜索（实时 300ms 防抖）
 * ├──────┬──────────────────────────────┤
 * │ 大类 │ ┌──┬──┬──┬──┐               │ ← 顶部子类横滑
 * │ 理疗 │ │推拿│艾灸│刮痧│拔罐│       │
 * │ 保健 │ └──┴──┴──┴──┘               │
 * │      ├──────────────────────────────┤
 * │ 居家 │ [卡片] 肩颈推拿 60分钟 [到店]│ ← 暖橙角标
 * │ 服务 │ ¥168                          │
 * │      │ ─────────────────────────────│
 * │ ...  │ [卡片] 艾草精油 100ml [快递]│ ← 蓝色角标
 * └──────┴──────────────────────────────┘
 *
 * 角标色值规范（终稿）：
 *   - 到店服务（in_store）→ 暖橙 #FF8A3D
 *   - 快递配送（delivery）→ 科技蓝 #3B82F6
 *   - 虚拟商品（virtual）  → 尊贵紫 #8B5CF6
 *
 * 搜索：
 *   - 顶部常驻、实时 300ms 防抖、全分类全关键词搜索
 *   - 无结果展示空状态图 + 6 个热门推荐
 */

interface Category {
  id: number;
  name: string;
  icon?: string | null;
  sort_order?: number;
  parent_id?: number | null;
  children?: Category[];
}

interface Product {
  id: number;
  name: string;
  description?: string | null;
  sale_price: number;
  market_price?: number | null;
  original_price?: number | null;
  cover_image?: string | null;
  images?: string[] | null;
  sales_count?: number;
  category_id?: number;
  category_name?: string | null;
  fulfillment_type?: string | null;
  stock?: number;
  selling_point?: string | null;
  marketing_badges?: string[] | null;
}

// 商品功能优化 v1.0：R5 卖点兜底显示分类名
function getSellingLine(product: Product, categoryMap: Record<number, string>): string {
  const sp = (product.selling_point || '').trim();
  if (sp) return sp;
  if (product.category_name) return product.category_name;
  if (product.category_id && categoryMap[product.category_id]) return categoryMap[product.category_id];
  return '';
}

const PAGE_SIZE = 10;

// 履约类型角标配置（终稿色值）
const FULFILLMENT_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  in_store: { label: '到店', bg: '#FF8A3D', color: '#FFFFFF' },
  delivery: { label: '快递', bg: '#3B82F6', color: '#FFFFFF' },
  virtual: { label: '虚拟', bg: '#8B5CF6', color: '#FFFFFF' },
};

function FulfillmentBadge({ type }: { type?: string | null }) {
  if (!type) return null;
  const conf = FULFILLMENT_BADGE[type];
  if (!conf) return null;
  return (
    <span
      style={{
        background: conf.bg,
        color: conf.color,
        padding: '2px 6px',
        borderRadius: 4,
        fontSize: 10,
        marginLeft: 4,
        flexShrink: 0,
        lineHeight: '14px',
        fontWeight: 600,
      }}
    >
      {conf.label}
    </span>
  );
}

function ProductCard({
  product,
  onClick,
  categoryMap,
}: {
  product: Product;
  onClick: () => void;
  categoryMap: Record<number, string>;
}) {
  const cover = product.cover_image || (product.images && product.images[0]) || null;
  // 商品功能优化 v1.0：
  // - R3：删除「销量」
  // - R4：不再展示「原价」
  // - R5：商品名下方展示一行卖点（灰 #999 / 12px / 单行省略），兜底分类名
  // - R6：商品图左上角展示营销角标（按优先级仅取 1 个）
  const sellingLine = getSellingLine(product, categoryMap);
  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl p-3 mb-2 active:bg-gray-50 cursor-pointer shadow-sm"
    >
      <div className="flex">
        <div className="relative w-20 h-20 flex-shrink-0">
          {cover ? (
            <img
              src={cover}
              alt={product.name}
              className="w-20 h-20 rounded-lg object-cover"
            />
          ) : (
            <div
              className="w-20 h-20 rounded-lg flex items-center justify-center text-2xl"
              style={{ background: 'linear-gradient(135deg, #f0fff0, #e8fce8)' }}
            >
              🏥
            </div>
          )}
          <MarketingBadge badges={product.marketing_badges} />
        </div>
        <div className="flex-1 ml-3 min-w-0">
          <div className="flex items-start">
            <span className="font-medium text-sm truncate flex-1">{product.name}</span>
            <FulfillmentBadge type={product.fulfillment_type} />
          </div>
          {sellingLine && (
            <p
              className="mt-1 truncate"
              style={{ color: '#999', fontSize: 12, lineHeight: '16px' }}
            >
              {sellingLine}
            </p>
          )}
          <div className="mt-1">
            <span className="text-base font-bold" style={{ color: '#52c41a' }}>
              ¥{Number(product.sale_price).toFixed(2)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ServicesPage() {
  const router = useRouter();

  // 一级分类（大类）和二级分类（子类）
  const [topCategories, setTopCategories] = useState<Category[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);
  const [activeTopId, setActiveTopId] = useState<number | null>(null);
  const [activeSubId, setActiveSubId] = useState<number | null>(null); // null = 全部

  // 商品列表
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);

  // 搜索
  const [searchInput, setSearchInput] = useState('');
  const [searchKeyword, setSearchKeyword] = useState(''); // 防抖后的关键词
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [hotRecs, setHotRecs] = useState<Product[]>([]);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 加载分类树 ──
  useEffect(() => {
    api
      .get('/api/products/categories')
      .then((res: any) => {
        const data = res.data || res;
        const tops: Category[] = (data.items || []).filter((c: Category) => !c.parent_id);
        const flat: Category[] = data.flat || [];
        setTopCategories(tops);
        setAllCategories(flat.length > 0 ? flat : tops);
        if (tops.length > 0) {
          setActiveTopId(tops[0].id);
        }
      })
      .catch(() => {});
  }, []);

  // 商品功能优化 v1.0：分类 ID → 分类名 映射，用于 R5 卖点兜底
  const categoryMap = useMemo<Record<number, string>>(() => {
    const map: Record<number, string> = {};
    allCategories.forEach((c) => {
      map[c.id] = c.name;
    });
    topCategories.forEach((c) => {
      if (!map[c.id]) map[c.id] = c.name;
      (c.children || []).forEach((child) => {
        if (!map[child.id]) map[child.id] = child.name;
      });
    });
    return map;
  }, [allCategories, topCategories]);

  // 当前大类的子类
  const subCategories = useMemo<Category[]>(() => {
    if (!activeTopId) return [];
    const top = topCategories.find((c) => c.id === activeTopId);
    if (top?.children && top.children.length > 0) return top.children;
    // fallback：从 flat 中筛
    return allCategories.filter((c) => c.parent_id === activeTopId);
  }, [activeTopId, topCategories, allCategories]);

  // ── 加载商品（按大类 + 子类）──
  const loadProducts = useCallback(
    async (topId: number | null, subId: number | null, pageNum: number, reset: boolean) => {
      if (!topId) return;
      try {
        const params: Record<string, any> = { page: pageNum, page_size: PAGE_SIZE };
        if (subId) {
          params.category_id = subId;
        } else {
          params.parent_category_id = topId;
        }
        const search = new URLSearchParams(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ).toString();
        const res: any = await api.get(`/api/products?${search}`);
        const data = res.data || res;
        const items: Product[] = data.items || [];
        if (reset) setProducts(items);
        else setProducts((prev) => [...prev, ...items]);
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
    if (searchKeyword) return; // 搜索态不加载普通列表
    if (!activeTopId) return;
    setLoading(true);
    setPage(1);
    loadProducts(activeTopId, activeSubId, 1, true);
  }, [activeTopId, activeSubId, loadProducts, searchKeyword]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await loadProducts(activeTopId, activeSubId, next, false);
  };

  // ── 搜索：300ms 防抖 ──
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setSearchKeyword(searchInput.trim());
    }, 300);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [searchInput]);

  // 执行搜索（全分类）
  useEffect(() => {
    if (!searchKeyword) {
      setSearchResults([]);
      setHotRecs([]);
      return;
    }
    setSearching(true);
    api
      .get(`/api/products?q=${encodeURIComponent(searchKeyword)}&page=1&page_size=30`)
      .then(async (res: any) => {
        const data = res.data || res;
        const items: Product[] = data.items || [];
        setSearchResults(items);
        // 无结果 → 取热门推荐
        if (items.length === 0) {
          try {
            const hotRes: any = await api.get('/api/products/hot-recommendations?limit=6');
            const hotData = hotRes.data || hotRes;
            setHotRecs(hotData.items || []);
          } catch {
            setHotRecs([]);
          }
        } else {
          setHotRecs([]);
        }
      })
      .catch(() => {
        setSearchResults([]);
        Toast.show({ content: '搜索失败，请稍后重试', icon: 'fail' });
      })
      .finally(() => setSearching(false));
  }, [searchKeyword]);

  const onProductClick = (p: Product) => router.push(`/product/${p.id}`);

  // ───────── 渲染：搜索态 ─────────
  if (searchKeyword) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20">
        {/* 顶部常驻搜索 */}
        <div
          className="sticky top-0 z-20 px-3 py-2 bg-white shadow-sm"
        >
          <SearchBar
            placeholder="搜索全部服务/商品"
            value={searchInput}
            onChange={setSearchInput}
            onClear={() => setSearchInput('')}
            style={{ '--border-radius': '20px', '--height': '36px' }}
          />
        </div>

        <div className="px-4 pt-3">
          {searching ? (
            <div className="flex items-center justify-center py-20">
              <SpinLoading color="primary" />
            </div>
          ) : searchResults.length > 0 ? (
            <>
              <div className="text-xs text-gray-400 mb-2">
                共找到 {searchResults.length} 个匹配结果
              </div>
              {searchResults.map((p) => (
                <ProductCard key={p.id} product={p} onClick={() => onProductClick(p)} categoryMap={categoryMap} />
              ))}
            </>
          ) : (
            <div className="py-8">
              <Empty description={`未找到「${searchKeyword}」相关结果`} />
              {hotRecs.length > 0 && (
                <div className="mt-6">
                  <div className="flex items-center mb-3">
                    <span className="text-base">🔥</span>
                    <span className="text-sm font-semibold text-gray-700 ml-1">
                      热门推荐
                    </span>
                  </div>
                  {hotRecs.map((p) => (
                    <ProductCard
                      key={p.id}
                      product={p}
                      onClick={() => onProductClick(p)}
                      categoryMap={categoryMap}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ───────── 渲染：常态（左侧大类 + 右侧子类 + 商品列表）─────────
  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* 顶部常驻搜索 */}
      <div className="sticky top-0 z-20 px-3 py-2 bg-white shadow-sm">
        <SearchBar
          placeholder="搜索全部服务/商品"
          value={searchInput}
          onChange={setSearchInput}
          style={{ '--border-radius': '20px', '--height': '36px' }}
        />
      </div>

      {/* 左侧大类 + 右侧内容 */}
      <div className="flex" style={{ minHeight: 'calc(100vh - 110px)' }}>
        {/* 左侧大类列表 */}
        <div
          className="w-[88px] flex-shrink-0 overflow-y-auto"
          style={{ background: '#f5f5f5', maxHeight: 'calc(100vh - 110px)' }}
        >
          {topCategories.map((cat) => {
            const active = activeTopId === cat.id;
            return (
              <div
                key={cat.id}
                onClick={() => {
                  setActiveTopId(cat.id);
                  setActiveSubId(null);
                }}
                className="px-2 py-3 text-center cursor-pointer relative"
                style={{
                  background: active ? '#fff' : 'transparent',
                  color: active ? '#52c41a' : '#666',
                  fontWeight: active ? 600 : 400,
                  fontSize: 14,
                }}
              >
                {active && (
                  <span
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: 8,
                      bottom: 8,
                      width: 3,
                      background: '#52c41a',
                      borderRadius: 2,
                    }}
                  />
                )}
                {cat.icon && <div className="text-lg mb-1">{cat.icon}</div>}
                <div className="leading-tight">{cat.name}</div>
              </div>
            );
          })}
        </div>

        {/* 右侧内容 */}
        <div className="flex-1 min-w-0">
          {/* 顶部子类横滑 */}
          {subCategories.length > 0 && (
            <div
              className="bg-white px-2 py-2 overflow-x-auto whitespace-nowrap shadow-sm"
              style={{ borderBottom: '1px solid #f0f0f0' }}
            >
              <span
                onClick={() => setActiveSubId(null)}
                className="inline-block px-3 py-1 mr-2 rounded-full text-xs cursor-pointer"
                style={{
                  background: activeSubId === null ? '#52c41a' : '#f5f5f5',
                  color: activeSubId === null ? '#fff' : '#666',
                }}
              >
                全部
              </span>
              {subCategories.map((sub) => (
                <span
                  key={sub.id}
                  onClick={() => setActiveSubId(sub.id)}
                  className="inline-block px-3 py-1 mr-2 rounded-full text-xs cursor-pointer"
                  style={{
                    background: activeSubId === sub.id ? '#52c41a' : '#f5f5f5',
                    color: activeSubId === sub.id ? '#fff' : '#666',
                  }}
                >
                  {sub.name}
                </span>
              ))}
            </div>
          )}

          {/* 商品列表 */}
          <div className="px-3 pt-3">
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <SpinLoading color="primary" />
              </div>
            ) : products.length === 0 ? (
              <Empty description="暂无相关服务" />
            ) : (
              <>
                {products.map((p) => (
                  <ProductCard key={p.id} product={p} onClick={() => onProductClick(p)} categoryMap={categoryMap} />
                ))}
                <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
