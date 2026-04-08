'use client';

import { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, Tag, Toast, SpinLoading, Empty } from 'antd-mobile';
import api from '@/lib/api';

const TAB_TYPES = [
  { key: 'all', title: '全部' },
  { key: 'article', title: '文章' },
  { key: 'video', title: '视频' },
  { key: 'service', title: '服务' },
  { key: 'points_mall', title: '积分商品' },
];

const TYPE_COLORS: Record<string, string> = {
  article: '#1890ff',
  video: '#722ed1',
  service: '#52c41a',
  points_mall: '#fa8c16',
};

const TYPE_LABELS: Record<string, string> = {
  article: '文章',
  video: '视频',
  service: '服务',
  points_mall: '积分商品',
};

interface SearchItem {
  id: number;
  title: string;
  type: string;
  cover_image?: string;
  summary?: string;
  tags?: any;
  score?: number;
}

interface HotItem {
  keyword: string;
  category_hint?: string;
  source?: string;
}

function SearchResultContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get('q') || '';

  const [keyword, setKeyword] = useState(q);
  const [activeTab, setActiveTab] = useState('all');
  const [allItems, setAllItems] = useState<SearchItem[]>([]);
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
  const [blockTip, setBlockTip] = useState<string | null>(null);
  const [tabResults, setTabResults] = useState<SearchItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [allLoading, setAllLoading] = useState(false);
  const [hotList, setHotList] = useState<HotItem[]>([]);
  const [drugKeywords, setDrugKeywords] = useState<string[]>([]);
  const [showDrugEntry, setShowDrugEntry] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const pageSize = 10;

  const fetchDrugKeywords = useCallback(async () => {
    try {
      const data: any = await api.get('/api/search/drug-keywords');
      const items = Array.isArray(data) ? data : [];
      setDrugKeywords(items.map((item: any) => typeof item === 'string' ? item : item.keyword));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchDrugKeywords();
  }, [fetchDrugKeywords]);

  useEffect(() => {
    if (q && drugKeywords.length > 0) {
      const matched = drugKeywords.some((kw: string) =>
        q.toLowerCase().includes(kw.toLowerCase()) || kw.toLowerCase().includes(q.toLowerCase())
      );
      setShowDrugEntry(matched);
    }
  }, [q, drugKeywords]);

  const fetchAll = useCallback(async (query: string) => {
    if (!query.trim()) return;
    setAllLoading(true);
    try {
      const data: any = await api.get('/api/search', { params: { q: query, type: 'all' } });
      setAllItems(data.items || []);
      setTypeCounts(data.type_counts || {});
      setBlockTip(data.block_tip || null);
    } catch {
      // ignore
    } finally {
      setAllLoading(false);
    }
  }, []);

  const fetchTab = useCallback(async (query: string, type: string, pageNum: number, append = false) => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data: any = await api.get('/api/search', {
        params: { q: query, type, page: pageNum, page_size: pageSize },
      });
      const items: SearchItem[] = data.items || [];
      if (append) {
        setTabResults((prev) => [...prev, ...items]);
      } else {
        setTabResults(items);
      }
      setHasMore(items.length >= pageSize);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHot = useCallback(async () => {
    try {
      const data: any = await api.get('/api/search/hot');
      setHotList((Array.isArray(data) ? data : []).slice(0, 10));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (q) {
      fetchAll(q);
    }
    fetchHot();
  }, [q, fetchAll, fetchHot]);

  useEffect(() => {
    if (activeTab !== 'all' && q) {
      setPage(1);
      setHasMore(true);
      fetchTab(q, activeTab, 1);
    }
  }, [activeTab, q, fetchTab]);

  const handleSearch = () => {
    if (!keyword.trim()) return;
    router.replace(`/search/result?q=${encodeURIComponent(keyword.trim())}`);
  };

  const loadMore = () => {
    if (loading || !hasMore) return;
    const nextPage = page + 1;
    setPage(nextPage);
    fetchTab(q, activeTab, nextPage, true);
  };

  const navigateToDetail = (item: SearchItem) => {
    switch (item.type) {
      case 'article':
      case 'video':
        router.push(`/article/${item.id}`);
        break;
      case 'service':
        router.push(`/service/${item.id}`);
        break;
      case 'points_mall':
        router.push('/points/mall');
        break;
      default:
        router.push(`/article/${item.id}`);
    }
  };

  const groupedResults = useMemo(() => {
    const groups: Record<string, SearchItem[]> = {};
    for (const item of allItems) {
      if (!groups[item.type]) groups[item.type] = [];
      groups[item.type].push(item);
    }
    return Object.entries(groups).map(([type, items]) => ({
      type,
      total: typeCounts[type] || items.length,
      items,
    }));
  }, [allItems, typeCounts]);

  const isEmpty = activeTab === 'all'
    ? !allLoading && allItems.length === 0 && q
    : !loading && tabResults.length === 0 && q;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top bar */}
      <div className="flex items-center px-3 py-2 bg-white border-b border-gray-100 sticky top-0 z-10">
        <button
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center"
          onClick={() => router.push('/home')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <div className="flex-1 mx-2">
          <div className="flex items-center bg-gray-100 rounded-full px-3 h-9">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={keyword}
              maxLength={100}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSearch();
              }}
              placeholder="搜索文章、视频、服务、商品"
              className="flex-1 bg-transparent border-none outline-none text-sm ml-2 text-gray-800 placeholder-gray-400"
            />
            {keyword && (
              <button
                className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-300 flex items-center justify-center"
                onClick={() => setKeyword('')}
              >
                <span className="text-white text-xs leading-none">×</span>
              </button>
            )}
          </div>
        </div>
        <button
          className="flex-shrink-0 text-sm font-medium"
          style={{ color: '#52c41a' }}
          onClick={handleSearch}
        >
          搜索
        </button>
      </div>

      {/* Drug quick entry */}
      {showDrugEntry && (
        <div
          className="mx-4 mt-3 bg-white rounded-xl p-3 flex items-center cursor-pointer shadow-sm"
          onClick={() => router.push('/drug')}
        >
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 mr-3"
            style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-gray-800">拍照识药</div>
            <div className="text-xs text-gray-400 mt-0.5">拍摄药品包装，AI帮您解读用药信息</div>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white mt-2">
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{
            '--title-font-size': '14px',
            '--active-line-color': '#52c41a',
            '--active-title-color': '#52c41a',
          } as React.CSSProperties}
        >
          {TAB_TYPES.map((tab) => (
            <Tabs.Tab title={tab.title} key={tab.key} />
          ))}
        </Tabs>
      </div>

      {/* Results area */}
      <div className="flex-1 px-4 py-3">
        {(allLoading || (loading && tabResults.length === 0)) && (
          <div className="flex justify-center py-10">
            <SpinLoading style={{ '--size': '28px', '--color': '#52c41a' }} />
          </div>
        )}

        {isEmpty && (
          <EmptyState hotList={hotList} router={router} />
        )}

        {/* Block tip */}
        {blockTip && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 mb-3 text-sm text-yellow-700">
            {blockTip}
          </div>
        )}

        {/* All tab - grouped */}
        {activeTab === 'all' && !allLoading && groupedResults.length > 0 && (
          <div className="space-y-4">
            {groupedResults.map((group) => {
              if (!group.items || group.items.length === 0) return null;
              const color = TYPE_COLORS[group.type] || '#999';
              const label = TYPE_LABELS[group.type] || group.type;
              return (
                <div key={group.type} className="bg-white rounded-xl overflow-hidden shadow-sm">
                  <div className="px-4 pt-3 pb-2 flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-700">
                      {label}相关
                      <span className="text-xs text-gray-400 font-normal ml-1">（{group.total}条）</span>
                    </span>
                  </div>
                  {group.items.slice(0, 3).map((item) => (
                    <ResultCard
                      key={`${group.type}-${item.id}`}
                      item={item}
                      onClick={() => navigateToDetail(item)}
                    />
                  ))}
                  {group.total > 3 && (
                    <div
                      className="text-center py-2.5 border-t border-gray-50 cursor-pointer"
                      onClick={() => setActiveTab(group.type)}
                    >
                      <span className="text-xs" style={{ color }}>查看更多 &gt;</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Single tab results */}
        {activeTab !== 'all' && !loading && tabResults.length > 0 && (
          <div className="space-y-3">
            {tabResults.map((item) => (
              <ResultCard
                key={`${activeTab}-${item.id}`}
                item={item}
                onClick={() => navigateToDetail(item)}
              />
            ))}

            {/* Load more */}
            {hasMore ? (
              <div
                className="text-center py-4 cursor-pointer"
                onClick={loadMore}
              >
                {loading ? (
                  <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' }} />
                ) : (
                  <span className="text-sm text-gray-400">加载更多</span>
                )}
              </div>
            ) : (
              <div className="text-center py-4 text-xs text-gray-300">
                没有更多了
              </div>
            )}
          </div>
        )}

        {activeTab !== 'all' && loading && tabResults.length > 0 && (
          <div className="flex justify-center py-4">
            <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' }} />
          </div>
        )}
      </div>
    </div>
  );
}

function ResultCard({ item, onClick }: { item: SearchItem; onClick: () => void }) {
  const color = TYPE_COLORS[item.type] || '#999';
  const label = TYPE_LABELS[item.type] || item.type;

  return (
    <div
      className="bg-white rounded-xl p-3 flex items-center cursor-pointer active:bg-gray-50 shadow-sm"
      onClick={onClick}
    >
      {item.cover_image && (
        <div className="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 mr-3 bg-gray-100">
          <img src={item.cover_image} alt="" className="w-full h-full object-cover" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-800 truncate">{item.title}</div>
        {item.summary && (
          <div className="text-xs text-gray-400 mt-1 truncate">{item.summary}</div>
        )}
        <div className="mt-1.5">
          <Tag
            style={{
              '--background-color': `${color}15`,
              '--text-color': color,
              '--border-color': 'transparent',
              '--border-radius': '4px',
              fontSize: 10,
            }}
          >
            {label}
          </Tag>
        </div>
      </div>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ddd" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 ml-2">
        <polyline points="9 18 15 12 9 6" />
      </svg>
    </div>
  );
}

function EmptyState({ hotList, router }: { hotList: HotItem[]; router: ReturnType<typeof import('next/navigation').useRouter> }) {
  return (
    <div className="flex flex-col items-center py-10">
      <div className="w-24 h-24 mb-4 flex items-center justify-center">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#ddd" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      </div>
      <p className="text-sm text-gray-400 mb-6">暂无搜索结果</p>

      {hotList.length > 0 && (
        <div className="w-full mb-6">
          <h4 className="text-sm font-medium text-gray-600 mb-3 text-center">推荐热门内容</h4>
          <div className="flex flex-wrap justify-center gap-2">
            {hotList.map((item, idx) => (
              <Tag
                key={idx}
                className="cursor-pointer"
                onClick={() => router.replace(`/search/result?q=${encodeURIComponent(item.keyword)}`)}
                style={{
                  '--background-color': '#f5f5f5',
                  '--text-color': '#666',
                  '--border-color': 'transparent',
                  padding: '6px 12px',
                  borderRadius: 16,
                  fontSize: 13,
                }}
              >
                {item.keyword}
              </Tag>
            ))}
          </div>
        </div>
      )}

      <button
        className="text-sm font-medium px-6 py-2 rounded-full text-white"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
        onClick={() => router.push('/ai')}
      >
        试试 AI 健康咨询
      </button>
    </div>
  );
}

export default function SearchResultPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <SpinLoading style={{ '--size': '32px', '--color': '#52c41a' }} />
        </div>
      }
    >
      <SearchResultContent />
    </Suspense>
  );
}
