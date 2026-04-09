'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Dialog, Tag, SpinLoading, SwipeAction } from 'antd-mobile';
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

type VoiceOverlayState = 'idle' | 'recording' | 'recognizing' | 'error';

const MAX_RECORD_SEC = 15;
const MIN_RECORD_SEC = 1;
const AUTO_SEARCH_SEC = 2;

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

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

export default function SearchPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [keyword, setKeyword] = useState('');
  const [hotList, setHotList] = useState<HotItem[]>([]);
  const [historyList, setHistoryList] = useState<HistoryItem[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestItem[]>([]);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);

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

  const debouncedKeyword = useDebounce(keyword, 300);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    setIsLoggedIn(!!token);
  }, []);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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

  const fetchHot = useCallback(async () => {
    try {
      const data: any = await api.get('/api/search/hot');
      setHotList((Array.isArray(data) ? data : []).slice(0, 10));
    } catch { /* ignore */ }
  }, []);

  const fetchHistory = useCallback(async () => {
    if (!isLoggedIn) return;
    try {
      const data: any = await api.get('/api/search/history');
      setHistoryList((Array.isArray(data) ? data : []).slice(0, 20));
    } catch { /* ignore */ }
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
      } catch { /* ignore */ } finally {
        if (!cancelled) setSuggestLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [debouncedKeyword]);

  const doSearch = useCallback((q: string, source: string = 'text') => {
    if (!q.trim()) return;
    const params = new URLSearchParams({ q: q.trim() });
    if (source === 'voice') params.set('source', 'voice');
    router.push(`/search/result?${params.toString()}`);
  }, [router]);

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

  const handleSuggestClick = (item: SuggestItem) => {
    if (item.is_drug_keyword) {
      router.push('/drug');
      return;
    }
    doSearch(item.keyword);
  };

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
      if (!text) {
        setErrorMsg('好像没听到声音哦，再试试~');
        setOverlayState('error');
        return;
      }
      closeOverlay();
      setKeyword(text);
      setAutoSearchCountdown(AUTO_SEARCH_SEC);
      let remaining = AUTO_SEARCH_SEC;
      autoSearchTimerRef.current = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearAutoSearch();
          doSearch(text, 'voice');
        } else {
          setAutoSearchCountdown(remaining);
        }
      }, 1000);
    } catch {
      setErrorMsg('没听清楚，再说一次好吗~');
      setOverlayState('error');
    }
  }, [closeOverlay, clearAutoSearch, doSearch]);

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

  const handleKeywordChange = (val: string) => {
    setKeyword(val);
    if (autoSearchCountdown !== null) {
      clearAutoSearch();
      if (val.trim()) {
        setAutoSearchCountdown(AUTO_SEARCH_SEC);
        let remaining = AUTO_SEARCH_SEC;
        autoSearchTimerRef.current = setInterval(() => {
          remaining -= 1;
          if (remaining <= 0) {
            clearAutoSearch();
            doSearch(val);
          } else {
            setAutoSearchCountdown(remaining);
          }
        }, 1000);
      }
    }
  };

  const handleClearKeyword = () => {
    setKeyword('');
    clearAutoSearch();
  };

  const handleCancelAutoSearch = () => {
    clearAutoSearch();
  };

  const displayHistory = historyExpanded ? historyList : historyList.slice(0, 6);

  const swipeActions: Action[] = [
    { key: 'delete', text: '删除', color: 'danger' },
  ];

  const showSuggestions = keyword.trim().length > 0;
  const showMicButton = micAvailable && asrEnabled;

  const overlayVisible = overlayState !== 'idle';

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
              onChange={(e) => handleKeywordChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  clearAutoSearch();
                  doSearch(keyword);
                }
              }}
              placeholder="搜索文章、视频、服务、商品"
              className="flex-1 bg-transparent border-none outline-none text-sm ml-2 text-gray-800 placeholder-gray-400"
            />
            {keyword && (
              <button
                className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-300 flex items-center justify-center"
                onClick={handleClearKeyword}
              >
                <span className="text-white text-xs leading-none">×</span>
              </button>
            )}
          </div>
        </div>
        {showMicButton && (
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
        <button
          className="flex-shrink-0 text-sm font-medium ml-1"
          style={{ color: '#52c41a' }}
          onClick={() => { clearAutoSearch(); doSearch(keyword); }}
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
            onClick={handleCancelAutoSearch}
          >
            先不搜了
          </button>
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        {showSuggestions ? (
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
          <div className="px-4 py-4">
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

      {/* Voice recording overlay */}
      {overlayVisible && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          }}
        >
          {/* Close button */}
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
              {/* Timer */}
              <div style={{
                fontSize: 20, fontWeight: 600, marginBottom: 24,
                color: recordSec >= MAX_RECORD_SEC - 3 ? '#ff4d4f' : '#fff',
                fontVariantNumeric: 'tabular-nums',
              }}>
                {recordSec}s / {MAX_RECORD_SEC}s
              </div>

              {/* Sound wave bars (7 bars) */}
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 5, height: 80, marginBottom: 32 }}>
                {volumeBars.map((v, i) => (
                  <div key={i} style={{
                    width: 5, borderRadius: 3,
                    background: 'linear-gradient(to top, #52c41a, #13c2c2)',
                    height: `${Math.max(12, v * 80)}px`,
                    transition: 'height 0.1s ease-out',
                  }} />
                ))}
              </div>

              {/* Pulsing stop button */}
              <button
                onClick={stopRecording}
                style={{
                  width: 80, height: 80, borderRadius: '50%',
                  background: '#fff', border: '3px solid #52c41a',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', gap: 4,
                  WebkitAnimation: 'pulse-glow 1.5s ease-in-out infinite',
                  animation: 'pulse-glow 1.5s ease-in-out infinite',
                }}
              >
                <div style={{ width: 8, height: 8, background: '#52c41a', borderRadius: 1 }} />
                <span style={{ fontSize: 12, color: '#52c41a', fontWeight: 500, lineHeight: 1.2 }}>点我结束~</span>
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
