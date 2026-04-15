'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Tag, Toast, Empty, SpinLoading, InfiniteScroll, Image, Popup, Radio } from 'antd-mobile';
import { PictureOutline, CameraOutline, FileOutline } from 'antd-mobile-icons';
import api from '@/lib/api';
import { checkFileSize, uploadWithProgress } from '@/lib/upload-utils';
import AlertBanner from '@/components/AlertBanner';

const MAX_IMAGES = 5;
const MAX_SIZE = 20 * 1024 * 1024;

interface FamilyMemberInfo {
  id: number;
  nickname: string;
  relationship_type: string;
  is_self?: boolean;
  relation_type_name?: string;
}

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
  family_member?: FamilyMemberInfo | null;
}

interface SelectedFile {
  file: File;
  previewUrl: string;
  id: string;
}

const RELATION_EMOJI: Record<string, string> = {
  '本人': '👤', '爸爸': '👨', '妈妈': '👩', '老公': '👨‍❤️‍👨', '老婆': '👩‍❤️‍👩',
  '儿子': '👦', '女儿': '👧', '哥哥': '👱‍♂️', '弟弟': '🧑', '姐姐': '👱‍♀️', '妹妹': '👧',
  '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵', '其他': '🧑',
  '父亲': '👨', '母亲': '👩', '配偶': '💑', '子女': '👧', '兄弟姐妹': '👫',
};

function getMemberEmoji(name: string): string {
  return RELATION_EMOJI[name] || '🧑';
}

function getMemberTagColor(relationshipType: string): string {
  const t = relationshipType || '';
  if (t === 'self' || t === '本人') return '#1677ff';
  if (['爸爸', '父亲'].includes(t)) return '#fa8c16';
  if (['妈妈', '母亲'].includes(t)) return '#eb2f96';
  if (['老公', '老婆', '配偶'].includes(t)) return '#722ed1';
  if (['儿子', '女儿', '子女'].includes(t)) return '#13c2c2';
  return '#8c8c8c';
}

function getMemberTagLabel(member: FamilyMemberInfo | null | undefined): { label: string; color: string } {
  if (!member) return { label: '本人', color: '#1677ff' };
  const label = member.nickname || member.relation_type_name || member.relationship_type || '本人';
  const relType = member.is_self ? '本人' : (member.relation_type_name || member.relationship_type);
  return { label, color: getMemberTagColor(relType) };
}

function getScoreColor(score: number): string {
  if (score >= 90) return '#0D7A3E';
  if (score >= 75) return '#4CAF50';
  if (score >= 60) return '#FFC107';
  if (score >= 40) return '#FF9800';
  return '#F44336';
}

const STEP_ITEMS = [
  { title: '上传报告', desc: '选择/拍照上传' },
  { title: '选择对象', desc: '报告是谁的' },
  { title: 'AI 解读', desc: '生成健康建议' },
];

function StepBar({ current, onStepClick }: { current: number; onStepClick: (idx: number) => void }) {
  return (
    <div className="flex items-center justify-between px-2 py-3">
      {STEP_ITEMS.map((item, idx) => {
        const isActive = idx === current;
        const isDone = idx < current;
        const canClick = idx < current;
        return (
          <div key={idx} className="flex items-center flex-1">
            <button
              className="flex items-center gap-2 flex-1 min-w-0"
              disabled={!canClick}
              onClick={() => canClick && onStepClick(idx)}
            >
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold transition-all"
                style={{
                  background: isDone ? '#52c41a' : isActive ? 'linear-gradient(135deg, #1890ff, #096dd9)' : '#e8e8e8',
                  color: isDone || isActive ? '#fff' : '#999',
                }}
              >
                {isDone ? '✓' : idx + 1}
              </div>
              <div className="min-w-0">
                <div
                  className="text-xs font-medium truncate"
                  style={{ color: isActive ? '#1890ff' : isDone ? '#52c41a' : '#999' }}
                >
                  {item.title}
                </div>
              </div>
            </button>
            {idx < STEP_ITEMS.length - 1 && (
              <div
                className="h-px flex-shrink-0 mx-2"
                style={{ width: 20, background: idx < current ? '#52c41a' : '#e8e8e8' }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function CheckupPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
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

  // Family member popup state
  const [memberPopupVisible, setMemberPopupVisible] = useState(false);
  const [familyMembers, setFamilyMembers] = useState<FamilyMemberInfo[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);

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

  const openMemberPopup = async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      let items: FamilyMemberInfo[] = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
      if (!items.some((m) => m.is_self)) {
        items = [{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }, ...items];
      }
      setFamilyMembers(items);
      setSelectedMemberId(items[0]?.id ?? null);
    } catch {
      setFamilyMembers([{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }]);
      setSelectedMemberId(-1);
    }
    setCurrentStep(1);
    setMemberPopupVisible(true);
  };

  const handleMemberConfirm = () => {
    setMemberPopupVisible(false);
    setCurrentStep(2);
    handleSubmitWithMember();
  };

  const handleSubmitWithMember = async () => {
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

      const memberId = selectedMemberId !== null && selectedMemberId !== -1 ? selectedMemberId : null;
      if (memberId !== null) {
        formData.append('family_member_id', String(memberId));
      }

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
        setCurrentStep(0);
        return;
      }

      if (data.fail_count && data.fail_count > 0) {
        Toast.show({ content: `${data.fail_count}张图片识别失败，已跳过` });
      }

      const reportId = data.report_id || data.merged_record_id;
      if (!reportId) {
        Toast.show({ content: '识别返回异常，请重试' });
        setUploading(false);
        setUploadProgress('');
        setUploadPercent(-1);
        setCurrentStep(0);
        return;
      }

      Toast.show({ icon: 'success', content: '识别完成' });
      selectedFiles.forEach((sf) => URL.revokeObjectURL(sf.previewUrl));
      setSelectedFiles([]);
      setUploading(false);
      setUploadProgress('');
      setUploadPercent(-1);
      router.push(`/checkup/result/${reportId}`);
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
      setCurrentStep(0);
    }
  };

  const handleStepClick = (idx: number) => {
    if (idx < currentStep && !uploading) {
      setCurrentStep(idx);
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

      <div className="px-4 pt-2">
        <div className="card mb-3">
          <StepBar current={currentStep} onStepClick={handleStepClick} />
        </div>

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
              onClick={openMemberPopup}
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
          reports.map((report) => {
            const memberTag = getMemberTagLabel(report.family_member);
            return (
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
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800 truncate">
                        体检报告 - {formatDate(report.created_at)}
                      </span>
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
                        style={{
                          background: `${memberTag.color}15`,
                          color: memberTag.color,
                        }}
                      >
                        {memberTag.label}
                      </span>
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
            );
          })
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

      {/* Family member selection popup */}
      <Popup
        visible={memberPopupVisible}
        onMaskClick={() => {
          setMemberPopupVisible(false);
          setCurrentStep(0);
        }}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '70vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">选择咨询对象</span>
            <button
              onClick={() => {
                setMemberPopupVisible(false);
                setCurrentStep(0);
              }}
              className="text-gray-400 text-xl leading-none"
            >
              ×
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2 mb-3">请选择这份报告是谁的体检报告</p>

          <div className="space-y-2">
            {familyMembers.map((m) => {
              const relationLabel = m.relation_type_name || m.relationship_type;
              const emoji = m.is_self ? '👤' : getMemberEmoji(relationLabel);
              const displayName = m.is_self ? '本人' : `${relationLabel} · ${m.nickname}`;
              return (
                <div
                  key={m.id}
                  className="flex items-center justify-between px-3 py-3 rounded-xl cursor-pointer"
                  style={{
                    background: selectedMemberId === m.id ? '#f6ffed' : '#f9f9f9',
                    border: selectedMemberId === m.id ? '1px solid #52c41a' : '1px solid transparent',
                  }}
                  onClick={() => setSelectedMemberId(m.id)}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-xl"
                      style={{ background: selectedMemberId === m.id ? 'linear-gradient(135deg,#52c41a,#13c2c2)' : '#f0f0f0' }}
                    >
                      {m.is_self && selectedMemberId === m.id ? <span className="text-white text-sm">我</span> : emoji}
                    </div>
                    <div className="text-sm font-medium">{displayName}</div>
                  </div>
                  <Radio
                    checked={selectedMemberId === m.id}
                    onChange={() => setSelectedMemberId(m.id)}
                    style={{ '--icon-size': '18px', '--font-size': '14px', '--gap': '6px' }}
                  />
                </div>
              );
            })}

            <div
              className="flex items-center gap-2 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: '#f9f9f9', border: '1px solid transparent' }}
              onClick={() => router.push('/health-profile?from=checkup')}
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg"
                style={{ background: '#52c41a' }}
              >
                +
              </div>
              <span className="text-sm font-medium" style={{ color: '#52c41a' }}>添加家庭成员</span>
            </div>
          </div>

          <button
            className="w-full mt-5 py-3 rounded-xl text-white text-sm font-medium"
            style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            onClick={handleMemberConfirm}
          >
            确认并开始识别
          </button>
        </div>
      </Popup>
    </div>
  );
}
