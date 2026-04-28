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
 * │ 大类 │ ┌──┬──┬──┬──┐               │ ← 顶部子类横滑（固定）
 * │ 理疗 │ │推拿│艾灸│刮痧│拔罐│       │
 * │ 保健 │ └──┴──┴──┴──┘               │
 * │      ├──────────────────────────────┤
 * │ 居家 │ [卡片] 肩颈推拿 60分钟       │
 * │ 服务 │ ¥168              [到店]     │ ← 角标在价格行右侧
 * │      │ ─────────────────────────────│
 * │ ...  │ [卡片] 艾草精油 100ml        │
 * └──────┴──────────────────────────────┘
 *
 * 角标色值规范（终稿）：
 *   - 到店服务（in_store）→ 暖橙 #FF8A3D
 *   - 快递配送（delivery）→ 科技蓝 #3B82F6
 *   - 虚拟商品（virtual）  → 尊贵紫 #8B5CF6
 *
 * F1/F2: 左侧分类栏固定 + 独立滚动
 * F3/F4/F5: 二级Tab固定 + 横向滑动 + 底部阴影
 * F6: 滚动联动Tab高亮（IntersectionObserver + 100ms节流）
 * F7: 点击Tab平滑滚动定位（300-500ms ease-out）
 * F8: Tab高亮平滑过渡动效（200-300ms ease-in-out）
 * F9: 履约角标移至价格行
 * F10: 商品名称完整显示（移除truncate）
 */

interface Category {
  id: number | string;
  name: string;
  icon?: string | null;
  sort_order?: number;
  parent_id?: number | null;
  children?: Category[];
  is_virtual?: boolean;
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
  min_price?: number;
  has_multi_spec?: boolean;
  spec_mode?: number;
  skus?: any[];
}

function getSellingLine(product: Product, categoryMap: Record<number, string>): string {
  const sp = (product.selling_point || '').trim();
  if (sp) return sp;
  if (product.category_name) return product.category_name;
  if (product.category_id && categoryMap[product.category_id]) return categoryMap[product.category_id];
  return '';
}

const PAGE_SIZE = 10;

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

/* F9: 角标移至价格行；F10: 名称完整显示 */
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
          {/* F10: 移除 truncate，名称自然换行完整显示 */}
          <div className="font-medium text-sm" style={{ lineHeight: '1.4', wordBreak: 'break-word' }}>
            {product.name}
          </div>
          {sellingLine && (
            <p
              className="mt-1 truncate"
              style={{ color: '#999', fontSize: 12, lineHeight: '16px' }}
            >
              {sellingLine}
            </p>
          )}
          {/* F9: 价格行 + 履约角标移至此行最右 */}
          <div className="mt-1 flex items-center justify-between">
            <span className="text-base font-bold" style={{ color: '#52c41a' }}>
              ¥{product.min_price || product.sale_price}
              {product.has_multi_spec && <span style={{ fontSize: '0.75em', fontWeight: 'normal' }}>起</span>}
            </span>
            <FulfillmentBadge type={product.fulfillment_type} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ServicesPage() {
  const router = useRouter();

  const [topCategories, setTopCategories] = useState<Category[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);
  const [activeTopId, setActiveTopId] = useState<number | string | null>(null);
  const [activeSubId, setActiveSubId] = useState<number | string | null>(null); // null = 全部

  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);

  const [searchInput, setSearchInput] = useState('');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [hotRecs, setHotRecs] = useState<Product[]>([]);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // F6/F7 联动相关
  const productListRef = useRef<HTMLDivElement>(null);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const sectionRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const tabRefs = useRef<Map<string, HTMLSpanElement>>(new Map());
  const isScrollingByClick = useRef(false);
  const scrollClickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 加载分类树 ──
  useEffect(() => {
    api
      .get('/api/products/categories')
      .then((res: any) => {
        const data = res.data || res;
        const tops: Category[] = (data.items || []);
        const flat: Category[] = data.flat || [];
        setTopCategories(tops);
        setAllCategories(flat.length > 0 ? flat : tops);
        if (tops.length > 0) {
          setActiveTopId(tops[0].id);
        }
      })
      .catch(() => {});
  }, []);

  const categoryMap = useMemo<Record<number, string>>(() => {
    const map: Record<number, string> = {};
    allCategories.forEach((c) => {
      map[c.id as number] = c.name;
    });
    topCategories.forEach((c) => {
      if (!map[c.id as number]) map[c.id as number] = c.name;
      (c.children || []).forEach((child) => {
        if (!map[child.id as number]) map[child.id as number] = child.name;
      });
    });
    return map;
  }, [allCategories, topCategories]);

  const subCategories = useMemo<Category[]>(() => {
    if (!activeTopId) return [];
    if (activeTopId === 'recommend') return [];
    const top = topCategories.find((c) => c.id === activeTopId);
    if (top?.children && top.children.length > 0) return top.children;
    return allCategories.filter((c) => c.parent_id === activeTopId);
  }, [activeTopId, topCategories, allCategories]);

  const hasSubCategories = subCategories.length > 0;

  // 按子类分组的商品（用于有子类时的分组渲染）
  const groupedProducts = useMemo(() => {
    if (!hasSubCategories) return null;
    const groups: { category: Category; items: Product[] }[] = [];
    const catMap = new Map<number | string, Product[]>();
    for (const p of products) {
      const cid = p.category_id || 'unknown';
      if (!catMap.has(cid)) catMap.set(cid, []);
      catMap.get(cid)!.push(p);
    }
    for (const sub of subCategories) {
      const items = catMap.get(sub.id) || [];
      if (items.length > 0) {
        groups.push({ category: sub, items });
      }
    }
    // 未匹配到子类的商品归到末尾
    const matchedIds = new Set(subCategories.map((s) => s.id));
    const unmatched: Product[] = [];
    Array.from(catMap.entries()).forEach(([cid, items]) => {
      if (!matchedIds.has(cid)) unmatched.push(...items);
    });
    if (unmatched.length > 0 && groups.length > 0) {
      groups[groups.length - 1].items.push(...unmatched);
    } else if (unmatched.length > 0) {
      groups.push({ category: { id: 'other', name: '其他' }, items: unmatched });
    }
    return groups;
  }, [hasSubCategories, products, subCategories]);

  // ── 数据加载逻辑变更：有子类时按 parent_category_id 加载所有商品 ──
  const loadProducts = useCallback(
    async (topId: number | string | null, subId: number | string | null, pageNum: number, reset: boolean, hasSubs: boolean) => {
      if (!topId && topId !== 0) return;
      try {
        const params: Record<string, any> = { page: pageNum, page_size: PAGE_SIZE };
        if (topId === 'recommend') {
          params.category_id = 'recommend';
        } else if (hasSubs) {
          // 有子类时始终按一级分类加载全部商品，前端分组
          params.parent_category_id = topId;
        } else if (subId) {
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
    if (searchKeyword) return;
    if (!activeTopId) return;
    setLoading(true);
    setPage(1);
    // 有子类时忽略 activeSubId，始终加载全部
    loadProducts(activeTopId, hasSubCategories ? null : activeSubId, 1, true, hasSubCategories);
  }, [activeTopId, activeSubId, loadProducts, searchKeyword, hasSubCategories]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await loadProducts(activeTopId, hasSubCategories ? null : activeSubId, next, false, hasSubCategories);
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

  // ── F6: 滚动联动Tab高亮（100ms节流 + IntersectionObserver） ──
  useEffect(() => {
    if (!hasSubCategories || !productListRef.current) return;

    let throttleTimer: ReturnType<typeof setTimeout> | null = null;

    const handleScroll = () => {
      if (isScrollingByClick.current) return;
      if (throttleTimer) return;
      throttleTimer = setTimeout(() => {
        throttleTimer = null;
        const container = productListRef.current;
        if (!container) return;
        const containerTop = container.getBoundingClientRect().top;
        let closestId: string | null = null;
        let closestDist = Infinity;

        sectionRefs.current.forEach((el, id) => {
          const rect = el.getBoundingClientRect();
          const dist = Math.abs(rect.top - containerTop);
          if (rect.top <= containerTop + 60 && dist < closestDist) {
            closestDist = dist;
            closestId = id;
          }
        });

        // Fallback: if nothing is above threshold, pick the first visible section
        if (!closestId) {
          sectionRefs.current.forEach((el, id) => {
            const rect = el.getBoundingClientRect();
            const dist = Math.abs(rect.top - containerTop);
            if (dist < closestDist) {
              closestDist = dist;
              closestId = id;
            }
          });
        }

        if (closestId !== null) {
          setActiveSubId(closestId === 'all' ? null : closestId);
          scrollTabIntoView(closestId === 'all' ? 'all' : closestId);
        }
      }, 100);
    };

    const container = productListRef.current;
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      container.removeEventListener('scroll', handleScroll);
      if (throttleTimer) clearTimeout(throttleTimer);
    };
  }, [hasSubCategories, subCategories]);

  // F6辅助：将高亮Tab滚动到可视范围
  const scrollTabIntoView = (id: string | number) => {
    const tabEl = tabRefs.current.get(String(id));
    const tabBar = tabBarRef.current;
    if (!tabEl || !tabBar) return;
    const tabRect = tabEl.getBoundingClientRect();
    const barRect = tabBar.getBoundingClientRect();
    if (tabRect.left < barRect.left || tabRect.right > barRect.right) {
      tabEl.scrollIntoView({ inline: 'center', behavior: 'smooth', block: 'nearest' });
    }
  };

  // ── F7: 点击Tab平滑滚动定位 ──
  const handleTabClick = (subId: number | string | null) => {
    if (subId === activeSubId) return;
    if (!hasSubCategories) {
      setActiveSubId(subId);
      return;
    }
    setActiveSubId(subId);

    const targetKey = subId === null ? 'all' : String(subId);
    const sectionEl = sectionRefs.current.get(targetKey);
    const container = productListRef.current;
    if (!sectionEl || !container) return;

    // 暂时禁用滚动联动
    isScrollingByClick.current = true;
    if (scrollClickTimer.current) clearTimeout(scrollClickTimer.current);

    const containerTop = container.getBoundingClientRect().top;
    const sectionTop = sectionEl.getBoundingClientRect().top;
    const scrollOffset = sectionTop - containerTop + container.scrollTop;

    container.scrollTo({
      top: scrollOffset,
      behavior: 'smooth',
    });

    // 动画结束后恢复联动（≈500ms）
    scrollClickTimer.current = setTimeout(() => {
      isScrollingByClick.current = false;
    }, 500);
  };

  // 切换一级分类时重置联动状态
  useEffect(() => {
    sectionRefs.current.clear();
    if (productListRef.current) {
      productListRef.current.scrollTop = 0;
    }
  }, [activeTopId]);

  // ───────── 渲染：搜索态 ─────────
  if (searchKeyword) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20">
        <div className="sticky top-0 z-20 px-3 py-2 bg-white shadow-sm">
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

  // ───────── 渲染：常态（全新布局） ─────────
  // F1/F2: 全屏容器不滚动，左侧栏固定+独立滚动
  // F3/F4/F5: 二级Tab固定+横向滑动+底部阴影
  return (
    <div
      className="bg-gray-50"
      style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* 顶部搜索栏（固定吸顶） */}
      <div className="px-3 py-2 bg-white shadow-sm flex-shrink-0" style={{ zIndex: 20 }}>
        <SearchBar
          placeholder="搜索全部服务/商品"
          value={searchInput}
          onChange={setSearchInput}
          style={{ '--border-radius': '20px', '--height': '36px' }}
        />
      </div>

      {/* 主内容区：左侧分类 + 右侧（Tab + 商品列表） */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* F1/F2: 左侧一级分类栏 —— 固定宽度，独立滚动 */}
        <div
          className="flex-shrink-0"
          style={{
            width: 88,
            overflowY: 'auto',
            background: '#f5f5f5',
            WebkitOverflowScrolling: 'touch',
            paddingBottom: 80,
          }}
        >
          {topCategories.map((cat) => {
            const active = activeTopId === cat.id;
            return (
              <div
                key={String(cat.id)}
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

        {/* 右侧区域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
          {/* F3/F4/F5: 二级Tab栏 —— 固定在商品列表上方，横向可滑动，底部阴影 */}
          {hasSubCategories && (
            <div
              ref={tabBarRef}
              className="bg-white flex-shrink-0"
              style={{
                overflowX: 'auto',
                overflowY: 'hidden',
                whiteSpace: 'nowrap',
                WebkitOverflowScrolling: 'touch',
                boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
                position: 'relative',
                zIndex: 10,
                padding: '8px 8px 10px',
              }}
            >
              {/* "全部" Tab */}
              <span
                ref={(el) => { if (el) tabRefs.current.set('all', el); }}
                onClick={() => handleTabClick(null)}
                className="inline-block px-3 py-1 mr-2 rounded-full text-xs cursor-pointer"
                style={{
                  position: 'relative',
                  background: activeSubId === null ? '#52c41a' : '#f5f5f5',
                  color: activeSubId === null ? '#fff' : '#666',
                  transition: 'background 250ms ease-in-out, color 250ms ease-in-out',
                }}
              >
                全部
              </span>
              {subCategories.map((sub) => (
                <span
                  key={String(sub.id)}
                  ref={(el) => { if (el) tabRefs.current.set(String(sub.id), el); }}
                  onClick={() => handleTabClick(sub.id)}
                  className="inline-block px-3 py-1 mr-2 rounded-full text-xs cursor-pointer"
                  style={{
                    position: 'relative',
                    background: activeSubId === sub.id ? '#52c41a' : '#f5f5f5',
                    color: activeSubId === sub.id ? '#fff' : '#666',
                    transition: 'background 250ms ease-in-out, color 250ms ease-in-out',
                  }}
                >
                  {sub.name}
                </span>
              ))}
            </div>
          )}

          {/* 商品列表 —— 唯一的垂直滚动区域 */}
          <div
            ref={productListRef}
            className="px-3 pt-3"
            style={{
              flex: 1,
              overflowY: 'auto',
              WebkitOverflowScrolling: 'touch',
              paddingBottom: 80,
            }}
          >
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <SpinLoading color="primary" />
              </div>
            ) : products.length === 0 ? (
              <Empty description="暂无相关服务" />
            ) : hasSubCategories && groupedProducts ? (
              /* 有子类时分组渲染，支持 F6/F7 联动 */
              <>
                {groupedProducts.map((group, gi) => (
                  <div
                    key={String(group.category.id)}
                    ref={(el) => {
                      if (el) sectionRefs.current.set(String(group.category.id), el);
                    }}
                    data-section-id={String(group.category.id)}
                  >
                    <div
                      className="text-xs font-medium mb-2"
                      style={{
                        color: '#999',
                        paddingTop: gi === 0 ? 0 : 12,
                        paddingBottom: 4,
                      }}
                    >
                      {group.category.name}
                    </div>
                    {group.items.map((p) => (
                      <ProductCard key={p.id} product={p} onClick={() => onProductClick(p)} categoryMap={categoryMap} />
                    ))}
                  </div>
                ))}
                <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
              </>
            ) : (
              /* 无子类 / 推荐分类：平铺渲染 */
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
