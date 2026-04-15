'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Tag, Toast, Empty, SpinLoading, InfiniteScroll, Image } from 'antd-mobile';
import { PictureOutline, CameraOutline, FileOutline } from 'antd-mobile-icons';
import api from '@/lib/api';
import { checkFileSize, uploadWithProgress } from '@/lib/upload-utils';
import AlertBanner from '@/components/AlertBanner';

const MAX_IMAGES = 5;
const MAX_SIZE = 20 * 1024 * 1024;

interface ReportItem {
  id: number;
  file_type: string;
  thumbnail_url?: string;
  file_url?: string;
  abnormal_count?: number;
  status: string;
  created_at: string;
  summary?: string;
  image_count?: number;
  health_score?: number;
  ai_analysis_json?: any;
}

interface SelectedFile {
  file: File;
  previewUrl: string;
  id: string;
}

function getScoreColor(score: number): string {
  if (score >= 90) return '#0D7A3E';
  if (score >= 75) return '#4CAF50';
  if (score >= 60) return '#FFC107';
  if (score >= 40) return '#FF9800';
  return '#F44336';
}

export default function CheckupPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [uploadPercent, setUploadPercent] = useState(-1);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [compareMode, setCompareMode] = useState(false);
  const [selectedReportIds, setSelectedReportIds] = useState<Set<number>>(new Set());
  const imageInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const toggleReportSelect = (id: number) => {
    setSelectedReportIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 2) {
          Toast.show({ content: '最多选择2份报告进行对比' });
          return prev;
        }
        next.add(id);
      }
      return next;
    });
  };

  const handleCompare = () => {
    const ids = Array.from(selectedReportIds);
    if (ids.length !== 2) {
      Toast.show({ content: '请选择2份报告进行对比' });
      return;
    }
    router.push(`/checkup/compare?id1=${ids[0]}&id2=${ids[1]}`);
  };

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
      const sizeCheck = await checkFileSize(f, 'checkup_report');
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
    setUploading(true);
    setUploadProgress(`正在上传 0/${selectedFiles.length} 张...`);
    setUploadPercent(0);

    try {
      const formData = new FormData();
      selectedFiles.forEach((sf) => {
        formData.append('files', sf.file);
      });
      formData.append('scene_name', '体检报告识别');

      setUploadProgress('上传中...');

      const data: any = await uploadWithProgress(
        '/api/ocr/batch-recognize',
        formData,
        (pct) => {
          setUploadPercent(pct);
          if (pct >= 100) setUploadProgress('识别中，请稍候...');
        },
        { timeout: 60000 },
      );

      if (data.fail_count && data.fail_count > 0 && data.fail_count === selectedFiles.length) {
        Toast.show({ content: '所有图片识别失败，请重试' });
        setUploading(false);
        setUploadProgress('');
        setUploadPercent(-1);
        return;
      }

      if (data.fail_count && data.fail_count > 0) {
        Toast.show({ content: `${data.fail_count}张图片识别失败，已跳过` });
      }

      const mergedId = data.merged_record_id;
      if (!mergedId) {
        Toast.show({ content: '识别返回异常，请重试' });
        setUploading(false);
        setUploadProgress('');
        setUploadPercent(-1);
        return;
      }

      Toast.show({ icon: 'success', content: '识别完成' });
      selectedFiles.forEach((sf) => URL.revokeObjectURL(sf.previewUrl));
      setSelectedFiles([]);
      setUploading(false);
      setUploadProgress('');
      setUploadPercent(-1);
      router.push(`/checkup/result/${mergedId}`);
    } catch (err: any) {
      const msg = err?.message || '上传失败，请重试';
      if (msg.includes('维护') || msg.includes('OCR') || msg.includes('closed')) {
        Toast.show({ content: '解读功能暂时维护中，请稍后再试' });
      } else {
        Toast.show({ content: msg });
      }
      setUploading(false);
      setUploadProgress('');
      setUploadPercent(-1);
    }
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
            支持图片或拍照，最多{MAX_IMAGES}张，AI将为您智能解读
          </p>

          <div className="flex gap-3">
            <button
              className="flex-1 flex flex-col items-center gap-2 py-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 active:bg-gray-100 transition-colors"
              onClick={() => imageInputRef.current?.click()}
              disabled={uploading || selectedFiles.length >= MAX_IMAGES}
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
              disabled={uploading || selectedFiles.length >= MAX_IMAGES}
            >
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ background: '#52c41a15', color: '#52c41a' }}
              >
                <CameraOutline fontSize={22} />
              </div>
              <span className="text-xs text-gray-600">拍照</span>
            </button>
          </div>

          {/* Selected images preview */}
          {selectedFiles.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  已选 <span className="text-blue-500 font-medium">{selectedFiles.length}</span>/{MAX_IMAGES} 张
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
                      disabled={uploading}
                    >
                      <span className="text-white text-xs leading-none">×</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload progress */}
          {uploading && (
            <div className="mt-4 py-3 px-3 rounded-xl bg-green-50">
              <div className="flex items-center gap-2 mb-2">
                <SpinLoading style={{ '--size': '18px', '--color': '#52c41a' }} />
                <span className="text-sm text-green-600">{uploadProgress}</span>
              </div>
              {uploadPercent >= 0 && (
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{ width: `${uploadPercent}%`, background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-10 text-right">{uploadPercent}%</span>
                </div>
              )}
            </div>
          )}

          {/* Submit button */}
          {selectedFiles.length > 0 && !uploading && (
            <button
              className="w-full mt-4 py-3 rounded-xl text-white text-sm font-medium"
              style={{ background: 'linear-gradient(135deg, #1890ff, #096dd9)' }}
              onClick={handleSubmit}
            >
              开始识别（{selectedFiles.length}张）
            </button>
          )}
        </div>

        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = '';
          }}
        />
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

        <div className="flex items-center justify-between mt-4">
          <div className="section-title">历史报告</div>
          {reports.length >= 2 && (
            <button
              className="text-xs px-3 py-1 rounded-full"
              style={{
                background: compareMode ? '#1890ff' : '#f5f5f5',
                color: compareMode ? '#fff' : '#666',
              }}
              onClick={() => {
                setCompareMode(!compareMode);
                setSelectedReportIds(new Set());
              }}
            >
              {compareMode ? '取消对比' : '对比模式'}
            </button>
          )}
        </div>
        {reports.length === 0 && !loadingList ? (
          <Empty description="暂无体检报告" style={{ padding: '40px 0' }} />
        ) : (
          reports.map((report) => (
            <Card
              key={report.id}
              style={{ marginBottom: 12, borderRadius: 12 }}
              onClick={() => {
                if (compareMode) {
                  toggleReportSelect(report.id);
                } else {
                  router.push(`/checkup/detail/${report.id}`);
                }
              }}
            >
              <div className="flex items-center gap-3">
                {compareMode && (
                  <div
                    className="w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center"
                    style={{
                      borderColor: selectedReportIds.has(report.id) ? '#1890ff' : '#d9d9d9',
                      background: selectedReportIds.has(report.id) ? '#1890ff' : '#fff',
                    }}
                  >
                    {selectedReportIds.has(report.id) && (
                      <span className="text-white text-xs">✓</span>
                    )}
                  </div>
                )}
                <div className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-gray-100 flex items-center justify-center relative">
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
                  {report.image_count && report.image_count > 1 && (
                    <div
                      className="absolute bottom-0 left-0 right-0 text-center text-white text-[9px] py-0.5"
                      style={{ background: 'rgba(0,0,0,0.45)', borderRadius: '0 0 8px 8px' }}
                    >
                      共{report.image_count}张
                    </div>
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
                {report.health_score != null && report.health_score > 0 && (
                  <div className="flex-shrink-0 text-center mr-1">
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center"
                      style={{
                        background: `${getScoreColor(report.health_score)}15`,
                        border: `2px solid ${getScoreColor(report.health_score)}`,
                      }}
                    >
                      <span
                        className="text-sm font-bold"
                        style={{ color: getScoreColor(report.health_score) }}
                      >
                        {report.health_score}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-400">评分</span>
                  </div>
                )}
                {!compareMode && <div className="text-gray-300 text-lg">›</div>}
              </div>
            </Card>
          ))
        )}

        {/* Compare action bar */}
        {compareMode && selectedReportIds.size > 0 && (
          <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-3 safe-area-bottom z-50">
            <button
              className="w-full py-3 rounded-xl text-sm font-medium text-white"
              style={{
                background: selectedReportIds.size === 2
                  ? 'linear-gradient(135deg, #1890ff, #096dd9)'
                  : '#ccc',
              }}
              disabled={selectedReportIds.size !== 2}
              onClick={handleCompare}
            >
              {selectedReportIds.size === 2
                ? '开始对比分析'
                : `已选${selectedReportIds.size}/2份报告`}
            </button>
          </div>
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
