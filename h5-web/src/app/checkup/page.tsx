'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Button, Card, Tag, Toast, Empty, SpinLoading, InfiniteScroll, Image, ActionSheet } from 'antd-mobile';
import { PictureOutline, CameraOutline, FileOutline } from 'antd-mobile-icons';
import api from '@/lib/api';
import AlertBanner from '@/components/AlertBanner';

interface ReportItem {
  id: number;
  file_type: string;
  thumbnail_url?: string;
  file_url?: string;
  abnormal_count?: number;
  status: string;
  created_at: string;
  summary?: string;
}

export default function CheckupPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const pdfInputRef = useRef<HTMLInputElement>(null);

  const fetchReports = useCallback(async (pageNum: number, reset = false) => {
    if (loadingList) return;
    setLoadingList(true);
    try {
      const res: any = await api.get('/api/report/list', {
        params: { page: pageNum, page_size: 10 },
      });
      const data = res.data || res;
      const items: ReportItem[] = data.items || data.list || [];
      const total = data.total || 0;
      if (reset) {
        setReports(items);
      } else {
        setReports((prev) => [...prev, ...items]);
      }
      setHasMore(pageNum * 10 < total && items.length > 0);
      setPage(pageNum);
    } catch {
      if (pageNum === 1) setReports([]);
      setHasMore(false);
    } finally {
      setLoadingList(false);
    }
  }, [loadingList]);

  useEffect(() => {
    fetchReports(1, true);
  }, []);

  const loadMore = async () => {
    await fetchReports(page + 1);
  };

  const handleFileUpload = async (file: File) => {
    if (!file) return;

    const maxSize = 20 * 1024 * 1024;
    if (file.size > maxSize) {
      Toast.show({ content: '文件大小不能超过20MB' });
      return;
    }

    setUploading(true);
    setUploadProgress('上传中...');

    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadRes: any = await api.post('/api/report/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const uploadData = uploadRes.data || uploadRes;
      const reportId = uploadData.report_id || uploadData.id;

      if (!reportId) {
        Toast.show({ content: '上传失败，请重试' });
        setUploading(false);
        setUploadProgress('');
        return;
      }

      setUploadProgress('OCR识别中...');

      const analyzeRes: any = await api.post('/api/report/analyze', { report_id: Number(reportId) });
      const analyzeData = analyzeRes.data || analyzeRes;

      if (analyzeData.ocr_disabled || analyzeData.ocr_closed) {
        Toast.show({ content: '解读功能暂时维护中，请稍后再试' });
        setUploading(false);
        setUploadProgress('');
        fetchReports(1, true);
        return;
      }

      setUploadProgress('AI解读中...');
      Toast.show({ icon: 'success', content: '解读完成' });
      setUploading(false);
      setUploadProgress('');

      router.push(`/checkup/result/${reportId}`);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message || '上传失败，请重试';
      if (msg.includes('维护') || msg.includes('OCR') || msg.includes('closed')) {
        Toast.show({ content: '解读功能暂时维护中，请稍后再试' });
      } else {
        Toast.show({ content: msg });
      }
      setUploading(false);
      setUploadProgress('');
    }
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
    e.target.value = '';
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        体检报告
      </NavBar>

      <AlertBanner />

      <div className="px-4 pt-4">
        <div className="card">
          <div className="section-title">上传体检报告</div>
          <p className="text-xs text-gray-400 mb-4">
            支持图片、拍照或PDF文件，AI将为您智能解读
          </p>

          <div className="flex gap-3">
            <button
              className="flex-1 flex flex-col items-center gap-2 py-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 active:bg-gray-100 transition-colors"
              onClick={() => imageInputRef.current?.click()}
              disabled={uploading}
            >
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: '#1890ff15', color: '#1890ff' }}
              >
                <PictureOutline fontSize={22} />
              </div>
              <span className="text-xs text-gray-600">相册</span>
            </button>

            <button
              className="flex-1 flex flex-col items-center gap-2 py-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 active:bg-gray-100 transition-colors"
              onClick={() => cameraInputRef.current?.click()}
              disabled={uploading}
            >
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: '#52c41a15', color: '#52c41a' }}
              >
                <CameraOutline fontSize={22} />
              </div>
              <span className="text-xs text-gray-600">拍照</span>
            </button>

            <button
              className="flex-1 flex flex-col items-center gap-2 py-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 active:bg-gray-100 transition-colors"
              onClick={() => pdfInputRef.current?.click()}
              disabled={uploading}
            >
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: '#fa8c1615', color: '#fa8c16' }}
              >
                <FileOutline fontSize={22} />
              </div>
              <span className="text-xs text-gray-600">PDF</span>
            </button>
          </div>

          {uploading && (
            <div className="flex items-center justify-center gap-2 mt-4 py-3 rounded-xl bg-green-50">
              <SpinLoading style={{ '--size': '18px', '--color': '#52c41a' }} />
              <span className="text-sm text-green-600">{uploadProgress}</span>
            </div>
          )}
        </div>

        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={onInputChange}
        />
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={onInputChange}
        />
        <input
          ref={pdfInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={onInputChange}
        />

        <div className="section-title mt-4">历史报告</div>
        {reports.length === 0 && !loadingList ? (
          <Empty description="暂无体检报告" style={{ padding: '40px 0' }} />
        ) : (
          reports.map((report) => (
            <Card
              key={report.id}
              style={{ marginBottom: 12, borderRadius: 12 }}
              onClick={() => router.push(`/checkup/detail/${report.id}`)}
            >
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-gray-100 flex items-center justify-center">
                  {report.file_type === 'pdf' ? (
                    <div className="flex flex-col items-center">
                      <FileOutline fontSize={24} color="#fa8c16" />
                      <span className="text-[10px] text-gray-400 mt-0.5">PDF</span>
                    </div>
                  ) : report.thumbnail_url ? (
                    <Image
                      src={report.thumbnail_url}
                      width={56}
                      height={56}
                      fit="cover"
                      style={{ borderRadius: 8 }}
                    />
                  ) : (
                    <PictureOutline fontSize={24} color="#ccc" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    体检报告 - {formatDate(report.created_at)}
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    {report.status === 'completed' ? (
                      <Tag
                        style={{
                          '--background-color': '#52c41a15',
                          '--text-color': '#52c41a',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        已解读
                      </Tag>
                    ) : report.status === 'failed' ? (
                      <Tag
                        style={{
                          '--background-color': '#f5222d15',
                          '--text-color': '#f5222d',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        分析失败
                      </Tag>
                    ) : report.status === 'analyzing' ? (
                      <Tag
                        style={{
                          '--background-color': '#1890ff15',
                          '--text-color': '#1890ff',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        分析中
                      </Tag>
                    ) : (
                      <Tag
                        style={{
                          '--background-color': '#fa8c1615',
                          '--text-color': '#fa8c16',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        待分析
                      </Tag>
                    )}
                    {report.abnormal_count != null && report.abnormal_count > 0 && (
                      <Tag
                        style={{
                          '--background-color': '#f5222d15',
                          '--text-color': '#f5222d',
                          '--border-color': 'transparent',
                          fontSize: 10,
                        }}
                      >
                        {report.abnormal_count}项异常
                      </Tag>
                    )}
                  </div>
                </div>
                <div className="text-gray-300 text-lg">›</div>
              </div>
            </Card>
          ))
        )}

        <InfiniteScroll loadMore={loadMore} hasMore={hasMore}>
          {loadingList && (
            <div className="flex justify-center py-4">
              <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
            </div>
          )}
        </InfiniteScroll>

        <div className="h-6" />
      </div>
    </div>
  );
}
