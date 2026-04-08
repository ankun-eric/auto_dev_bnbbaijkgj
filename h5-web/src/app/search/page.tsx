'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Dialog, Popup, Tag, SpinLoading, SwipeAction } from 'antd-mobile';
import { Action } from 'antd-mobile/es/components/swipe-action';
import api from '@/lib/api';

interface HotItem {
  keyword: string;
  category_hint?: string;
  source?: string;
}

interface HistoryItem {
  id: number;
  keyword: string;
  created_at?: string;
}

interface SuggestItem {
  keyword: string;
  category_hint?: string;
  is_drug_keyword?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  article: '#1890ff',
  video: '#722ed1',
  service: '#52c41a',
  points_mall: '#fa8c16',
  '拍照识药': '#13c2c2',
  '文章': '#1890ff',
  '视频': '#722ed1',
  '服务': '#52c41a',
  '积分商品': '#fa8c16',
};

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function SearchPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [keyword, setKeyword] = useState('');
  const [hotList, setHotList] = useState<HotItem[]>([]);
  const [historyList, setHistoryList] = useState<HistoryItem[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestItem[]>([]);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [voiceVisible, setVoiceVisible] = useState(false);
  const [asrEnabled, setAsrEnabled] = useState(false);
  const [voiceListening, setVoiceListening] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);

  const debouncedKeyword = useDebounce(keyword, 300);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    setIsLoggedIn(!!token);
  }, []);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const fetchHot = useCallback(async () => {
    try {
      const data: any = await api.get('/api/search/hot');
      setHotList((Array.isArray(data) ? data : []).slice(0, 10));
    } catch {
      // ignore
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    if (!isLoggedIn) return;
    try {
      const data: any = await api.get('/api/search/history');
      setHistoryList((Array.isArray(data) ? data : []).slice(0, 20));
    } catch {
      // ignore
    }
  }, [isLoggedIn]);

  useEffect(() => {
    fetchHot();
    fetchHistory();
  }, [fetchHot, fetchHistory]);

  useEffect(() => {
    if (!debouncedKeyword.trim()) {
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setSuggestLoading(true);
      try {
        const data: any = await api.get('/api/search/suggest', { params: { q: debouncedKeyword } });
        if (cancelled) return;
        setSuggestions(Array.isArray(data) ? data : []);
      } catch {
        // ignore
      } finally {
        if (!cancelled) setSuggestLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [debouncedKeyword]);

  const doSearch = (q: string) => {
    if (!q.trim()) return;
    router.push(`/search/result?q=${encodeURIComponent(q.trim())}`);
  };

  const handleDeleteOne = async (id: number) => {
    try {
      await api.delete(`/api/search/history/${id}`);
      setHistoryList((prev) => prev.filter((h) => h.id !== id));
      Toast.show({ content: '已删除', position: 'bottom' });
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  const handleClearAll = () => {
    Dialog.confirm({
      content: '确定清空所有搜索历史吗？',
      confirmText: '清空',
      cancelText: '取消',
      onConfirm: async () => {
        try {
          await api.delete('/api/search/history');
          setHistoryList([]);
          Toast.show({ content: '已清空', position: 'bottom' });
        } catch {
          Toast.show({ content: '清空失败', icon: 'fail' });
        }
      },
    });
  };

  const checkAsr = async () => {
    try {
      const data: any = await api.post('/api/search/asr/token');
      if (data.provider) {
        setAsrEnabled(true);
        return true;
      }
    } catch {
      // ignore
    }
    setAsrEnabled(false);
    return false;
  };

  const openVoice = async () => {
    const ok = await checkAsr();
    if (!ok) {
      Toast.show({ content: '语音搜索功能即将上线', position: 'center' });
      return;
    }
    setVoiceVisible(true);
    setVoiceListening(true);
  };

  const handleSuggestClick = (item: SuggestItem) => {
    if (item.is_drug_keyword) {
      router.push('/drug');
      return;
    }
    doSearch(item.keyword);
  };

  const displayHistory = historyExpanded ? historyList : historyList.slice(0, 6);

  const swipeActions: Action[] = [
    {
      key: 'delete',
      text: '删除',
      color: 'danger',
    },
  ];

  const showSuggestions = keyword.trim().length > 0;

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Top search bar */}
      <div className="flex items-center px-3 py-2 border-b border-gray-100 sticky top-0 bg-white z-10">
        <button
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center"
          onClick={() => router.back()}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <div className="flex-1 mx-2 relative">
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
                if (e.key === 'Enter') doSearch(keyword);
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
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center"
          onClick={openVoice}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </button>
        <button
          className="flex-shrink-0 text-sm font-medium ml-1"
          style={{ color: '#52c41a' }}
          onClick={() => doSearch(keyword)}
        >
          搜索
        </button>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        {showSuggestions ? (
          /* Suggestion list */
          <div className="px-4 py-2">
            {suggestLoading && (
              <div className="flex justify-center py-4">
                <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' }} />
              </div>
            )}
            {!suggestLoading && suggestions.length === 0 && debouncedKeyword.trim() && (
              <div className="text-center text-sm text-gray-400 py-6">暂无搜索建议</div>
            )}
            {suggestions.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center py-3 border-b border-gray-50 cursor-pointer active:bg-gray-50"
                onClick={() => handleSuggestClick(item)}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <span className="flex-1 text-sm text-gray-700 ml-3 truncate">{item.keyword}</span>
                {item.category_hint && (
                  <Tag
                    style={{
                      '--background-color': `${CATEGORY_COLORS[item.category_hint] || '#999'}15`,
                      '--text-color': CATEGORY_COLORS[item.category_hint] || '#999',
                      '--border-color': 'transparent',
                      fontSize: 10,
                    }}
                  >
                    {item.category_hint}
                  </Tag>
                )}
              </div>
            ))}
          </div>
        ) : (
          /* Hot search + History */
          <div className="px-4 py-4">
            {/* Hot search */}
            <div className="mb-6">
              <h3 className="text-base font-semibold text-gray-800 mb-3">热门搜索</h3>
              <div className="flex flex-wrap gap-2">
                {hotList.map((item, idx) => (
                  <Tag
                    key={idx}
                    className="cursor-pointer"
                    onClick={() => doSearch(item.keyword)}
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
                {hotList.length === 0 && (
                  <span className="text-sm text-gray-400">暂无热门搜索</span>
                )}
              </div>
            </div>

            {/* Search history */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-base font-semibold text-gray-800">搜索历史</h3>
                {isLoggedIn && historyList.length > 0 && (
                  <button className="text-xs text-gray-400" onClick={handleClearAll}>
                    全部清空
                  </button>
                )}
              </div>

              {!isLoggedIn ? (
                <div className="text-center py-6">
                  <p className="text-sm text-gray-400 mb-3">登录后可查看搜索历史</p>
                  <button
                    className="text-sm font-medium px-6 py-1.5 rounded-full border"
                    style={{ color: '#52c41a', borderColor: '#52c41a' }}
                    onClick={() => router.push('/login')}
                  >
                    去登录
                  </button>
                </div>
              ) : historyList.length === 0 ? (
                <div className="text-center py-6 text-sm text-gray-400">暂无搜索历史</div>
              ) : (
                <>
                  {displayHistory.map((item) => (
                    <SwipeAction
                      key={item.id}
                      rightActions={swipeActions}
                      onAction={() => handleDeleteOne(item.id)}
                    >
                      <div
                        className="flex items-center py-3 border-b border-gray-50 cursor-pointer active:bg-gray-50"
                        onClick={() => doSearch(item.keyword)}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
                          <circle cx="12" cy="12" r="10" />
                          <polyline points="12 6 12 12 16 14" />
                        </svg>
                        <span className="flex-1 text-sm text-gray-600 ml-3 truncate">{item.keyword}</span>
                        <button
                          className="flex-shrink-0 w-6 h-6 flex items-center justify-center"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteOne(item.id);
                          }}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          </svg>
                        </button>
                      </div>
                    </SwipeAction>
                  ))}
                  {historyList.length > 6 && !historyExpanded && (
                    <div
                      className="flex items-center justify-center py-3 cursor-pointer"
                      onClick={() => setHistoryExpanded(true)}
                    >
                      <span className="text-xs text-gray-400 mr-1">展开更多</span>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </div>
                  )}
                  {historyExpanded && historyList.length > 6 && (
                    <div
                      className="flex items-center justify-center py-3 cursor-pointer"
                      onClick={() => setHistoryExpanded(false)}
                    >
                      <span className="text-xs text-gray-400 mr-1">收起</span>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="18 15 12 9 6 15" />
                      </svg>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Voice search popup */}
      <Popup
        visible={voiceVisible}
        onMaskClick={() => {
          setVoiceVisible(false);
          setVoiceListening(false);
        }}
        position="bottom"
        bodyStyle={{
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          minHeight: '40vh',
          background: 'linear-gradient(180deg, #f0faf0 0%, #fff 100%)',
        }}
      >
        <div className="flex flex-col items-center py-8 px-6">
          <div className="text-base font-medium text-gray-700 mb-8">
            {voiceListening ? '正在聆听...' : '请说出您想搜索的内容'}
          </div>

          {/* Mic icon with pulse animation */}
          <div className="relative mb-8">
            {voiceListening && (
              <>
                <div className="absolute inset-0 w-20 h-20 rounded-full animate-ping" style={{ background: 'rgba(82,196,26,0.15)' }} />
                <div className="absolute inset-0 w-20 h-20 rounded-full animate-pulse" style={{ background: 'rgba(82,196,26,0.1)' }} />
              </>
            )}
            <div
              className="relative w-20 h-20 rounded-full flex items-center justify-center cursor-pointer"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              onClick={() => setVoiceListening(!voiceListening)}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </div>
          </div>

          {/* Wave animation */}
          {voiceListening && (
            <div className="flex items-end gap-1 h-8 mb-6">
              {[...Array(12)].map((_, i) => (
                <div
                  key={i}
                  className="w-1 rounded-full"
                  style={{
                    background: `linear-gradient(to top, #52c41a, #13c2c2)`,
                    animation: `voiceWave 0.8s ease-in-out ${i * 0.08}s infinite alternate`,
                    height: 8,
                  }}
                />
              ))}
            </div>
          )}

          <p className="text-sm text-gray-400 mt-2">语音搜索功能即将上线</p>

          <button
            className="mt-6 text-sm text-gray-500 px-6 py-2 rounded-full bg-gray-100"
            onClick={() => {
              setVoiceVisible(false);
              setVoiceListening(false);
            }}
          >
            取消
          </button>
        </div>
      </Popup>

      <style jsx>{`
        @keyframes voiceWave {
          from { height: 8px; }
          to { height: 28px; }
        }
      `}</style>
    </div>
  );
}
