'use client';

import { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, Tag, Toast, SpinLoading, Empty } from 'antd-mobile';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

type VoiceOverlayState = 'idle' | 'recording' | 'recognizing' | 'error';

const MAX_RECORD_SEC = 15;
const MIN_RECORD_SEC = 1;
const AUTO_SEARCH_SEC = 2;

function getPreferredMimeType(): string {
  if (typeof MediaRecorder !== 'undefined') {
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
    if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
    if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
    if (MediaRecorder.isTypeSupported('audio/mp3')) return 'audio/mp3';
  }
  return '';
}

function mimeToFormat(mime: string): string {
  if (!mime) return 'webm';
  if (mime.includes('webm')) return 'webm';
  if (mime.includes('mp4')) return 'm4a';
  if (mime.includes('mp3') || mime.includes('mpeg')) return 'mp3';
  return 'webm';
}

const removePunctuation = (str: string): string => {
  return str.replace(/[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:'"()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]/g, '').trim();
};

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
  const searchSource = searchParams.get('source') === 'voice' ? 'voice' : 'text';

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

  const [micAvailable, setMicAvailable] = useState(false);
  const [asrEnabled, setAsrEnabled] = useState(false);
  const [overlayState, setOverlayState] = useState<VoiceOverlayState>('idle');
  const [recordSec, setRecordSec] = useState(0);
  const [volumeBars, setVolumeBars] = useState<number[]>([0, 0, 0, 0, 0, 0, 0]);
  const [errorMsg, setErrorMsg] = useState('');
  const [autoSearchCountdown, setAutoSearchCountdown] = useState<number | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);
  const recordTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordStartTimeRef = useRef<number>(0);
  const autoSearchTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mimeTypeRef = useRef('');
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    let active = true;
    const checkCapabilities = async () => {
      const hasMic = !!(navigator.mediaDevices?.getUserMedia);
      if (active) setMicAvailable(hasMic);
      if (!hasMic) return;
      try {
        const data: any = await api.post('/api/search/asr/token');
        if (active && data?.provider) {
          setAsrEnabled(true);
        }
      } catch {
        if (active) setAsrEnabled(false);
      }
    };
    checkCapabilities();
    return () => { active = false; };
  }, []);

  const clearAutoSearch = useCallback(() => {
    if (autoSearchTimerRef.current) {
      clearInterval(autoSearchTimerRef.current);
      autoSearchTimerRef.current = null;
    }
    setAutoSearchCountdown(null);
  }, []);

  const cleanupRecording = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = 0;
    }
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (maxTimerRef.current) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch { /* ignore */ }
    }
    mediaRecorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      try { audioCtxRef.current.close(); } catch { /* ignore */ }
    }
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, []);

  const closeOverlay = useCallback(() => {
    cleanupRecording();
    setOverlayState('idle');
    setRecordSec(0);
    setVolumeBars([0, 0, 0, 0, 0, 0, 0]);
    setErrorMsg('');
  }, [cleanupRecording]);

  const doVoiceSearch = useCallback((text: string) => {
    router.replace(`/search/result?q=${encodeURIComponent(text)}&source=voice`);
  }, [router]);

  const sendToAsr = useCallback(async (blob: Blob) => {
    setOverlayState('recognizing');
    try {
      const fd = new FormData();
      const fmt = mimeToFormat(mimeTypeRef.current);
      fd.append('audio_file', blob, `recording.${fmt}`);
      fd.append('format', fmt);
      fd.append('sample_rate', '16000');
      const data: any = await api.post('/api/search/asr/recognize', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });
      if (data?.success === false) {
        setErrorMsg(data?.error || '好像没听到声音哦，再试试~');
        setOverlayState('error');
        return;
      }
      const text = data?.data?.text || data?.text || '';
      const cleanText = removePunctuation(text);
      if (!cleanText) {
        setErrorMsg('好像没听到声音哦，再试试~');
        setOverlayState('error');
        return;
      }
      closeOverlay();
      setKeyword(cleanText);
      setAutoSearchCountdown(AUTO_SEARCH_SEC);
      let remaining = AUTO_SEARCH_SEC;
      autoSearchTimerRef.current = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearAutoSearch();
          doVoiceSearch(cleanText);
        } else {
          setAutoSearchCountdown(remaining);
        }
      }, 1000);
    } catch {
      setErrorMsg('没听清楚，再说一次好吗~');
      setOverlayState('error');
    }
  }, [closeOverlay, clearAutoSearch, doVoiceSearch]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const startRecording = useCallback(async () => {
    audioChunksRef.current = [];
    setRecordSec(0);
    setErrorMsg('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mime = getPreferredMimeType();
      mimeTypeRef.current = mime;
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const elapsed = (Date.now() - recordStartTimeRef.current) / 1000;
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current);
          animFrameRef.current = 0;
        }
        if (recordTimerRef.current) {
          clearInterval(recordTimerRef.current);
          recordTimerRef.current = null;
        }
        if (maxTimerRef.current) {
          clearTimeout(maxTimerRef.current);
          maxTimerRef.current = null;
        }
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
          streamRef.current = null;
        }
        if (elapsed < MIN_RECORD_SEC) {
          setErrorMsg('说的太快了，再试一次吧~');
          setOverlayState('error');
          return;
        }
        const blob = new Blob(audioChunksRef.current, { type: mime || 'audio/webm' });
        sendToAsr(blob);
      };

      recorder.start(250);
      recordStartTimeRef.current = Date.now();
      setOverlayState('recording');

      recordTimerRef.current = setInterval(() => {
        const s = Math.floor((Date.now() - recordStartTimeRef.current) / 1000);
        setRecordSec(s);
      }, 500);

      maxTimerRef.current = setTimeout(() => {
        stopRecording();
      }, MAX_RECORD_SEC * 1000);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateBars = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        const barCount = 7;
        const step = Math.floor(dataArray.length / barCount);
        const bars: number[] = [];
        for (let i = 0; i < barCount; i++) {
          let sum = 0;
          for (let j = 0; j < step; j++) sum += dataArray[i * step + j];
          bars.push(Math.min(1, (sum / step) / 180));
        }
        setVolumeBars(bars);
        animFrameRef.current = requestAnimationFrame(updateBars);
      };
      animFrameRef.current = requestAnimationFrame(updateBars);
    } catch (err: any) {
      cleanupRecording();
      const msg = err?.name === 'NotAllowedError' ? '需要你允许使用麦克风才能听到你说话哦~' : '录音启动失败了，再试一次吧~';
      setErrorMsg(msg);
      setOverlayState('error');
    }
  }, [sendToAsr, stopRecording, cleanupRecording]);

  const handleMicClick = useCallback(() => {
    if (overlayState !== 'idle') return;
    startRecording();
  }, [overlayState, startRecording]);

  useEffect(() => {
    return () => {
      cleanupRecording();
      clearAutoSearch();
    };
  }, [cleanupRecording, clearAutoSearch]);

  useEffect(() => {
    setKeyword(q);
  }, [q]);

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
      const data: any = await api.get('/api/search', { params: { q: query, type: 'all', source: searchSource } });
      setAllItems(data.items || []);
      setTypeCounts(data.type_counts || {});
      setBlockTip(data.block_tip || null);
    } catch {
      // ignore
    } finally {
      setAllLoading(false);
    }
  }, [searchSource]);

  const fetchTab = useCallback(async (query: string, type: string, pageNum: number, append = false) => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data: any = await api.get('/api/search', {
        params: { q: query, type, page: pageNum, page_size: pageSize, source: searchSource },
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
  }, [searchSource, pageSize]);

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
    clearAutoSearch();
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
        router.push(`/product/${item.id}`);
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
              onChange={(e) => {
                setKeyword(e.target.value);
                if (autoSearchCountdown !== null) clearAutoSearch();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSearch();
              }}
              placeholder="搜索文章、视频、服务、商品"
              className="flex-1 bg-transparent border-none outline-none text-sm ml-2 text-gray-800 placeholder-gray-400"
            />
            <div className="flex items-center gap-2 flex-shrink-0">
              {micAvailable && asrEnabled && (
                <button
                  className="flex-shrink-0 w-8 h-8 flex items-center justify-center"
                  onClick={handleMicClick}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                  </svg>
                </button>
              )}
              {keyword && (
                <button
                  className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-300 flex items-center justify-center"
                  onClick={() => { setKeyword(''); clearAutoSearch(); }}
                >
                  <span className="text-white text-xs leading-none">×</span>
                </button>
              )}
            </div>
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

      {/* Auto search countdown hint */}
      {autoSearchCountdown !== null && (
        <div style={{ padding: '8px 16px', background: '#f6ffed', borderBottom: '1px solid #b7eb8f', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 13, color: '#333' }}>
            听到啦~ {autoSearchCountdown}秒后帮你搜索
          </span>
          <button
            style={{ fontSize: 13, color: '#1890ff', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 8px' }}
            onClick={() => clearAutoSearch()}
          >
            先不搜了
          </button>
        </div>
      )}

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

      {overlayState !== 'idle' && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <button
            onClick={closeOverlay}
            style={{
              position: 'absolute', top: 16, right: 16,
              width: 36, height: 36, borderRadius: '50%',
              background: 'rgba(255,255,255,0.15)', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          {overlayState === 'recording' && (
            <>
              <style dangerouslySetInnerHTML={{ __html: `
                @-webkit-keyframes pulse-glow {
                  0%, 100% { box-shadow: 0 0 0 0 rgba(82,196,26,0.4); -webkit-transform: scale(1); transform: scale(1); }
                  50% { box-shadow: 0 0 20px 10px rgba(82,196,26,0.2); -webkit-transform: scale(1.05); transform: scale(1.05); }
                }
                @keyframes pulse-glow {
                  0%, 100% { box-shadow: 0 0 0 0 rgba(82,196,26,0.4); transform: scale(1); }
                  50% { box-shadow: 0 0 20px 10px rgba(82,196,26,0.2); transform: scale(1.05); }
                }
              `}} />
              <div style={{
                fontSize: 20, fontWeight: 600, marginBottom: 24,
                color: recordSec >= MAX_RECORD_SEC - 3 ? '#ff4d4f' : '#fff',
                fontVariantNumeric: 'tabular-nums',
              }}>
                {recordSec}s / {MAX_RECORD_SEC}s
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 5, height: 100, marginBottom: 32 }}>
                {volumeBars.map((v, i) => (
                  <div key={i} style={{
                    width: 5, borderRadius: 3,
                    background: 'linear-gradient(to top, #52c41a, #13c2c2)',
                    height: `${Math.max(15, v * 100)}px`,
                    transition: 'height 0.1s ease-out',
                  }} />
                ))}
              </div>

              <button
                onClick={stopRecording}
                style={{
                  width: 100, height: 100, borderRadius: '50%',
                  background: '#fff', border: '3px solid #52c41a',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', gap: 4,
                  WebkitAnimation: 'pulse-glow 1.5s ease-in-out infinite',
                  animation: 'pulse-glow 1.5s ease-in-out infinite',
                }}
              >
                <div style={{ width: 10, height: 10, background: '#52c41a', borderRadius: 1 }} />
                <span style={{ fontSize: 16, color: '#52c41a', fontWeight: 500, lineHeight: 1.2 }}>点我结束~</span>
              </button>
            </>
          )}

          {overlayState === 'recognizing' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
              <SpinLoading style={{ '--size': '40px', '--color': '#52c41a' } as any} />
              <div style={{ fontSize: 16, color: '#fff', fontWeight: 500 }}>
                我在认真听，马上就好~
              </div>
            </div>
          )}

          {overlayState === 'error' && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '0 32px' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ff4d4f" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <div style={{ fontSize: 15, color: '#fff', textAlign: 'center' }}>
                {errorMsg}
              </div>
              <button
                onClick={() => {
                  cleanupRecording();
                  setOverlayState('idle');
                  setRecordSec(0);
                  setErrorMsg('');
                  setTimeout(() => startRecording(), 100);
                }}
                style={{
                  marginTop: 8, padding: '10px 32px', borderRadius: 24,
                  background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  color: '#fff', fontSize: 15, fontWeight: 500,
                  border: 'none', cursor: 'pointer',
                }}
              >
                再来一次~
              </button>
            </div>
          )}
        </div>
      )}
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
          <img src={resolveAssetUrl(item.cover_image)} alt="" className="w-full h-full object-cover" />
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
