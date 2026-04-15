'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Toast, Empty, SpinLoading, Card, Tag, Button } from 'antd-mobile';
import api from '@/lib/api';
import { checkFileSize, uploadWithProgress } from '@/lib/upload-utils';

const MAX_IMAGES = 5;
const MAX_SIZE = 20 * 1024 * 1024;

interface HistoryItem {
  id: number;
  session_id: number;
  drug_name: string;
  image_url: string;
  image_count?: number;
  status: string;
  created_at: string;
}

interface SelectedFile {
  file: File;
  previewUrl: string;
  id: string;
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
  const [uploadProgress, setUploadProgress] = useState('AI识别中...');
  const [uploadPercent, setUploadPercent] = useState(-1);
  const [error, setError] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);

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

  const addFiles = async (files: FileList | null) => {
    if (!files) return;
    const current = selectedFiles.length;
    const remaining = MAX_IMAGES - current;
    if (remaining <= 0) {
      Toast.show({ content: `最多只能选择${MAX_IMAGES}张图片` });
      return;
    }
    const toAdd = Array.from(files).slice(0, remaining);

    const valid: File[] = [];
    for (const f of toAdd) {
      const sizeCheck = await checkFileSize(f, 'drug_identify');
      if (!sizeCheck.ok) {
        Toast.show({ content: `文件 ${f.name} 超过限制（最大 ${sizeCheck.maxMb} MB），已跳过` });
        continue;
      }
      if (f.size > MAX_SIZE) {
        Toast.show({ content: '部分图片超过20MB，已跳过' });
        continue;
      }
      valid.push(f);
    }
    if (valid.length === 0) return;
    const newItems: SelectedFile[] = valid.map((file) => ({
      file,
      previewUrl: URL.createObjectURL(file),
      id: `${Date.now()}-${Math.random()}`,
    }));
    setSelectedFiles((prev) => [...prev, ...newItems]);
    setError('');
  };

  const removeFile = (id: string) => {
    setSelectedFiles((prev) => {
      const item = prev.find((f) => f.id === id);
      if (item) URL.revokeObjectURL(item.previewUrl);
      return prev.filter((f) => f.id !== id);
    });
  };

  const handleSubmit = async () => {
    if (selectedFiles.length === 0) return;
    setRecognizing(true);
    setError('');
    setUploadPercent(0);
    setUploadProgress(`正在上传 ${selectedFiles.length} 张图片...`);

    try {
      const formData = new FormData();
      selectedFiles.forEach((sf) => formData.append('files', sf.file));
      formData.append('scene_name', '拍照识药');

      const data: any = await uploadWithProgress(
        '/api/ocr/batch-recognize',
        formData,
        (pct) => {
          setUploadPercent(pct);
          if (pct >= 100) setUploadProgress('AI识别中...');
        },
        { timeout: 120000 },
      );

      if (data.session_id) {
        selectedFiles.forEach((sf) => URL.revokeObjectURL(sf.previewUrl));
        setSelectedFiles([]);
        router.push(`/drug/chat/${data.session_id}`);
      } else {
        setError('识别返回异常，请重试');
      }
    } catch {
      setError('识别失败，请重新拍照或选择图片');
    } finally {
      setRecognizing(false);
      setUploadPercent(-1);
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
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = '';
        }}
      />
      <input
        ref={albumInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          addFiles(e.target.files);
          e.target.value = '';
        }}
      />

      {/* Recognition overlay */}
      {recognizing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex flex-col items-center justify-center">
          <SpinLoading style={{ '--size': '48px', '--color': '#52c41a' }} />
          <span className="text-white text-base mt-4 font-medium">{uploadProgress}</span>
          {uploadPercent >= 0 && uploadPercent < 100 && (
            <div className="w-48 mt-3 flex items-center gap-2">
              <div className="flex-1 h-2 bg-white/20 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300 bg-green-400"
                  style={{ width: `${uploadPercent}%` }}
                />
              </div>
              <span className="text-xs text-white/80 w-10 text-right">{uploadPercent}%</span>
            </div>
          )}
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
              disabled={recognizing || selectedFiles.length >= MAX_IMAGES}
              className="flex-1 h-11 rounded-full text-white font-medium text-sm border-none"
              style={{
                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                opacity: recognizing || selectedFiles.length >= MAX_IMAGES ? 0.6 : 1,
              }}
            >
              拍照识药
            </button>
            <button
              onClick={() => albumInputRef.current?.click()}
              disabled={recognizing || selectedFiles.length >= MAX_IMAGES}
              className="flex-1 h-11 rounded-full font-medium text-sm bg-white"
              style={{
                border: '1px solid #52c41a',
                color: '#52c41a',
                opacity: recognizing || selectedFiles.length >= MAX_IMAGES ? 0.6 : 1,
              }}
            >
              从相册选择
            </button>
          </div>

          <p className="text-xs text-gray-400 text-center">
            拍摄药品包装，AI 帮您解读用药信息，最多{MAX_IMAGES}张
          </p>

          {/* Selected images preview */}
          {selectedFiles.length > 0 && (
            <div className="w-full mt-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  已选 <span className="font-medium" style={{ color: '#52c41a' }}>{selectedFiles.length}</span>/{MAX_IMAGES} 张
                </span>
                {selectedFiles.length < MAX_IMAGES && (
                  <span className="text-xs text-gray-400">还可添加{MAX_IMAGES - selectedFiles.length}张</span>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                {selectedFiles.map((sf) => (
                  <div key={sf.id} className="relative aspect-square">
                    <img
                      src={sf.previewUrl}
                      alt="preview"
                      className="w-full h-full object-cover rounded-lg"
                    />
                    <button
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-700 flex items-center justify-center"
                      onClick={() => removeFile(sf.id)}
                      disabled={recognizing}
                    >
                      <span className="text-white text-xs leading-none">×</span>
                    </button>
                  </div>
                ))}
              </div>

              <button
                className="w-full mt-3 py-2.5 rounded-full text-white text-sm font-medium border-none"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                onClick={handleSubmit}
                disabled={recognizing}
              >
                开始识别（{selectedFiles.length}张）
              </button>
            </div>
          )}

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
                  <div className="w-12 h-12 rounded-lg flex-shrink-0 bg-gray-100 overflow-hidden mr-3 relative">
                    {item.image_url ? (
                      <>
                        <img
                          src={item.image_url}
                          alt={item.drug_name}
                          className="w-full h-full object-cover"
                        />
                        {item.image_count && item.image_count > 1 && (
                          <div
                            className="absolute bottom-0 left-0 right-0 text-center text-white text-[9px] py-0.5"
                            style={{ background: 'rgba(0,0,0,0.45)', borderRadius: '0 0 8px 8px' }}
                          >
                            共{item.image_count}张
                          </div>
                        )}
                      </>
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
