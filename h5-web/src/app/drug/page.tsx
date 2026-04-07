'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Toast, Empty, SpinLoading, Card, Tag, Button } from 'antd-mobile';
import api from '@/lib/api';

interface HistoryItem {
  id: number;
  session_id: number;
  drug_name: string;
  image_url: string;
  status: string;
  created_at: string;
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function DrugPage() {
  const router = useRouter();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [recognizing, setRecognizing] = useState(false);
  const [error, setError] = useState('');

  const cameraInputRef = useRef<HTMLInputElement>(null);
  const albumInputRef = useRef<HTMLInputElement>(null);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res: any = await api.get('/api/drug-identify/history', {
        params: { page: 1, page_size: 20 },
      });
      const data = res.data || res;
      setHistory(data.items || []);
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleFileSelected = async (file: File | undefined) => {
    if (!file) return;
    setRecognizing(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('scene_name', '拍照识药');
      const res: any = await api.post('/api/ocr/recognize', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      const data = res.data || res;
      if (data.session_id) {
        router.push(`/drug/chat/${data.session_id}`);
      } else {
        setError('识别返回异常，请重试');
      }
    } catch {
      setError('识别失败，请重新拍照或选择图片');
    } finally {
      setRecognizing(false);
      if (cameraInputRef.current) cameraInputRef.current.value = '';
      if (albumInputRef.current) albumInputRef.current.value = '';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <NavBar
        onBack={() => router.back()}
        style={{
          '--height': '48px',
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          color: '#fff',
          '--border-bottom': 'none',
        } as React.CSSProperties}
      >
        <span className="text-white font-medium">拍照识药</span>
      </NavBar>

      {/* Hidden file inputs */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFileSelected(e.target.files?.[0])}
      />
      <input
        ref={albumInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handleFileSelected(e.target.files?.[0])}
      />

      {/* Recognition overlay */}
      {recognizing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex flex-col items-center justify-center">
          <SpinLoading style={{ '--size': '48px', '--color': '#52c41a' }} />
          <span className="text-white text-base mt-4 font-medium">AI识别中...</span>
        </div>
      )}

      {/* Camera action area */}
      <div className="px-4 pt-6 pb-4">
        <div className="bg-white rounded-2xl p-6 flex flex-col items-center shadow-sm">
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center mb-5"
            style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </div>

          <div className="flex gap-3 w-full mb-4">
            <button
              onClick={() => cameraInputRef.current?.click()}
              disabled={recognizing}
              className="flex-1 h-11 rounded-full text-white font-medium text-sm border-none"
              style={{
                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                opacity: recognizing ? 0.6 : 1,
              }}
            >
              拍照识药
            </button>
            <button
              onClick={() => albumInputRef.current?.click()}
              disabled={recognizing}
              className="flex-1 h-11 rounded-full font-medium text-sm bg-white"
              style={{
                border: '1px solid #52c41a',
                color: '#52c41a',
                opacity: recognizing ? 0.6 : 1,
              }}
            >
              从相册选择
            </button>
          </div>

          <p className="text-xs text-gray-400 text-center">
            拍摄药品包装，AI 帮您解读用药信息
          </p>

          {error && (
            <div className="mt-4 w-full text-center">
              <p className="text-sm text-red-500 mb-2">{error}</p>
              <Button
                size="small"
                onClick={() => {
                  setError('');
                  cameraInputRef.current?.click();
                }}
                style={{
                  color: '#52c41a',
                  borderColor: '#52c41a',
                  borderRadius: 20,
                }}
              >
                重新拍照
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* History section */}
      <div className="flex-1 px-4 pb-6">
        <div className="flex items-center justify-between mb-3">
          <span className="section-title mb-0">识别记录</span>
        </div>

        {historyLoading ? (
          <div className="flex items-center justify-center py-10">
            <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
          </div>
        ) : history.length === 0 ? (
          <div className="bg-white rounded-2xl py-10 text-center shadow-sm">
            <Empty
              description="暂无识别记录，拍张药品照片试试吧"
              style={{ '--description-font-size': '13px' } as React.CSSProperties}
            />
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((item) => (
              <Card
                key={item.id}
                onClick={() => router.push(`/drug/chat/${item.session_id}`)}
                style={{ borderRadius: 12 }}
              >
                <div className="flex items-center">
                  <div
                    className="w-12 h-12 rounded-lg flex-shrink-0 bg-gray-100 overflow-hidden mr-3"
                  >
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.drug_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="1.5">
                          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                          <circle cx="8.5" cy="8.5" r="1.5" />
                          <polyline points="21 15 16 10 5 21" />
                        </svg>
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {item.drug_name || '未知药品'}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {formatTime(item.created_at)}
                    </div>
                  </div>
                  <Tag
                    style={{
                      '--background-color': item.status === 'failed' ? '#f5222d15' : '#52c41a15',
                      '--text-color': item.status === 'failed' ? '#f5222d' : '#52c41a',
                      '--border-color': 'transparent',
                      fontSize: 10,
                    } as React.CSSProperties}
                  >
                    {item.status === 'failed' ? '识别失败' : '已识别'}
                  </Tag>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
