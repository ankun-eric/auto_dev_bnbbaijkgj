'use client';

/**
 * [PRD-469 M8] 健康事件 Tab —— 时间轴 + 手动日记 + 病历卡上传
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Mask } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';

interface EventItem {
  id: number;
  event_type: string;
  title?: string;
  content?: string;
  event_date: string;
  tags: string[];
  extra_data?: any;
}

const TYPE_FILTERS = [
  { value: '', label: '全部' },
  { value: 'diary', label: '日记' },
  { value: 'medication', label: '用药' },
  { value: 'abnormal', label: '异常' },
  { value: 'upload', label: '病历卡' },
];

const DIARY_TAGS = ['不适', '复诊', '用药调整', '其他'];

interface Props {
  profileId?: number;
  token: any;
}

export default function HealthEventsBlock({ profileId, token: T }: Props) {
  const [items, setItems] = useState<EventItem[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [adding, setAdding] = useState(false);
  const [showUploadRecord, setShowUploadRecord] = useState(false);
  const [uploadImageUrl, setUploadImageUrl] = useState<string | null>(null);
  const [uploadOcrText, setUploadOcrText] = useState('');
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadNote, setUploadNote] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [draftTitle, setDraftTitle] = useState('');
  const [draftContent, setDraftContent] = useState('');
  const [draftTag, setDraftTag] = useState<string>('');
  const [draftDate, setDraftDate] = useState<string>(new Date().toISOString().slice(0, 10));

  const fetchTimeline = useCallback(async () => {
    try {
      const params: any = { limit: 50 };
      if (profileId) params.profile_id = profileId;
      if (filter) params.event_type = filter;
      const qs = new URLSearchParams(params).toString();
      const res: any = await api.get(`/api/prd469/health-event/timeline?${qs}`);
      const data = res.data || res;
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setItems([]);
    }
  }, [profileId, filter]);

  useEffect(() => { fetchTimeline(); }, [fetchTimeline]);

  const handleAddDiary = async () => {
    if (!draftTitle.trim() && !draftContent.trim()) {
      showToast('请填写标题或内容', 'fail');
      return;
    }
    try {
      await api.post('/api/prd469/health-event', {
        event_type: 'diary',
        title: draftTitle.trim() || '健康日记',
        content: draftContent.trim(),
        event_date: draftDate,
        tags: draftTag ? [draftTag] : [],
        profile_id: profileId,
      });
      setAdding(false);
      setDraftTitle(''); setDraftContent(''); setDraftTag('');
      await fetchTimeline();
      showToast('已记录', 'success');
    } catch {
      showToast('保存失败', 'fail');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setUploadImageUrl(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleUploadRecord = async () => {
    if (!uploadImageUrl && !uploadOcrText) {
      showToast('请选择图片或输入OCR文字', 'fail');
      return;
    }
    setUploading(true);
    try {
      const body: any = {
        profile_id: profileId,
        title: uploadTitle.trim() || undefined,
        note: uploadNote.trim() || undefined,
      };
      if (uploadImageUrl) body.image_url = uploadImageUrl;
      if (uploadOcrText.trim()) body.ocr_text = uploadOcrText.trim();

      await api.post('/api/prd469/medical-record', body);
      setShowUploadRecord(false);
      setUploadImageUrl(null);
      setUploadOcrText('');
      setUploadTitle('');
      setUploadNote('');
      await fetchTimeline();
      showToast('病历卡已上传', 'success');
    } catch {
      showToast('上传失败，请重试', 'fail');
    } finally {
      setUploading(false);
    }
  };

  const isMedicalCard = (e: EventItem) => {
    return e.event_type === 'upload' && e.tags && e.tags.includes('病历卡');
  };

  return (
    <div id="health-events" data-testid="prd469-health-events" style={{ padding: '12px 16px 80px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0 12px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: 0 }}>健康事件</h3>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => setAdding(true)}
            data-testid="prd469-add-event-btn"
            style={{
              padding: '6px 12px', background: T.brand500, color: '#fff',
              border: 'none', borderRadius: 16, fontSize: 12, fontWeight: 600,
            }}
          >+ 写日记</button>
          <button
            onClick={() => setShowUploadRecord(true)}
            data-testid="prd469-upload-record-btn"
            style={{
              padding: '6px 12px', background: T.brand600, color: '#fff',
              border: 'none', borderRadius: 16, fontSize: 12, fontWeight: 600,
            }}
          >📋 上传病历</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, overflowX: 'auto' }}>
        {TYPE_FILTERS.map((f) => {
          const active = filter === f.value;
          return (
            <button
              key={f.value || 'all'}
              onClick={() => setFilter(f.value)}
              style={{
                flex: '0 0 auto', padding: '6px 14px', borderRadius: 14,
                background: active ? T.brand500 : '#fff',
                color: active ? '#fff' : '#374151',
                border: `1px solid ${active ? T.brand500 : '#e5e7eb'}`,
                fontSize: 13, cursor: 'pointer',
              }}
            >{f.label}</button>
          );
        })}
      </div>

      {items.length === 0 ? (
        <div
          style={{
            background: '#fff', borderRadius: 12, padding: 24,
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            borderLeft: '3px solid #22c55e',
            textAlign: 'center', color: '#9ca3af', fontSize: 14,
          }}
        >
          暂无事件记录，点击右上角「写日记」或「上传病历」开始记录
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((e) => {
            const isMedical = isMedicalCard(e);
            return (
              <div
                key={e.id}
                data-testid={`prd469-event-${e.id}`}
                style={{
                  background: '#fff', borderRadius: 12, padding: 14,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  borderLeft: isMedical ? '3px solid #3b82f6' : '3px solid #22c55e',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>
                    {isMedical ? '📋 ' : iconOfType(e.event_type)} {e.title || labelOfType(e.event_type)}
                  </span>
                  <span style={{ fontSize: 12, color: '#9ca3af' }}>{e.event_date}</span>
                </div>
                {e.content && (
                  <div style={{ fontSize: 13, color: '#4b5563', lineHeight: 1.6, marginBottom: 4 }}>{e.content}</div>
                )}
                {isMedical && e.extra_data?.image_url && (
                  <div style={{ marginTop: 8 }}>
                    <img src={e.extra_data.image_url} alt="病历卡" style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 8 }} />
                  </div>
                )}
                {e.tags && e.tags.length > 0 && (
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {e.tags.map((t) => (
                      <span key={t} style={{
                        padding: '2px 8px', background: T.brand100, color: T.brand700,
                        borderRadius: 8, fontSize: 11,
                      }}>{t}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {adding && (
        <Mask visible color="rgba(0,0,0,0.5)">
          <div
            style={{
              position: 'fixed', left: 0, right: 0, bottom: 0,
              background: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16,
            }}
          >
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>写健康日记</span>
              <span onClick={() => setAdding(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>日期</div>
                <input
                  type="date" value={draftDate} onChange={(e) => setDraftDate(e.target.value)}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: `1px solid ${T.brand200}`, fontSize: 14, boxSizing: 'border-box' }}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>标题</div>
                <input
                  type="text" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)}
                  placeholder="如：感冒就诊"
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: `1px solid ${T.brand200}`, fontSize: 14, boxSizing: 'border-box' }}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>详情</div>
                <textarea
                  value={draftContent} onChange={(e) => setDraftContent(e.target.value)}
                  placeholder="详细记录…"
                  rows={4}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: `1px solid ${T.brand200}`, fontSize: 14, boxSizing: 'border-box', resize: 'none' }}
                />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>标签</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {DIARY_TAGS.map((t) => (
                    <button
                      key={t}
                      onClick={() => setDraftTag(t === draftTag ? '' : t)}
                      style={{
                        padding: '6px 12px', borderRadius: 14,
                        background: draftTag === t ? T.brand500 : '#f3f4f6',
                        color: draftTag === t ? '#fff' : '#374151',
                        border: 'none', fontSize: 13, cursor: 'pointer',
                      }}
                    >{t}</button>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={() => setAdding(false)}
                  style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
                <button onClick={handleAddDiary} data-testid="prd469-save-diary"
                  style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
              </div>
            </div>
          </div>
        </Mask>
      )}

      {showUploadRecord && (
        <Mask visible color="rgba(0,0,0,0.5)">
          <div
            data-testid="prd469-upload-record-modal"
            style={{
              position: 'fixed', left: 0, right: 0, bottom: 0,
              background: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16,
              maxHeight: '90vh', display: 'flex', flexDirection: 'column',
            }}
          >
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>上传病历卡</span>
              <span onClick={() => setShowUploadRecord(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 8 }}>病历卡图片</div>
                <div
                  data-testid="prd469-upload-image-area"
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: '2px dashed #22c55e50', borderRadius: 12, padding: 40,
                    textAlign: 'center', cursor: 'pointer', background: '#f0fdf4',
                  }}
                >
                  {uploadImageUrl ? (
                    <img src={uploadImageUrl} alt="Preview" style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 8 }} />
                  ) : (
                    <div>
                      <div style={{ fontSize: 32, marginBottom: 8 }}>📷</div>
                      <div style={{ fontSize: 14, color: '#22c55e' }}>点击拍照或选择图片</div>
                    </div>
                  )}
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file" accept="image/*" capture="environment"
                style={{ display: 'none' }}
                onChange={handleFileSelect}
              />
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>标题（可选）</div>
                <input
                  type="text" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="如：XX医院就诊记录"
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: `1px solid #e5e7eb`, fontSize: 14, boxSizing: 'border-box' }}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>备注（可选）</div>
                <textarea
                  value={uploadNote} onChange={(e) => setUploadNote(e.target.value)}
                  placeholder="补充说明…"
                  rows={2}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: `1px solid #e5e7eb`, fontSize: 14, boxSizing: 'border-box', resize: 'none' }}
                />
              </div>
            </div>
            <div style={{ padding: 16, borderTop: `1px solid ${T.brand100}`, display: 'flex', gap: 12 }}>
              <button onClick={() => setShowUploadRecord(false)}
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
              <button onClick={handleUploadRecord} disabled={uploading}
                data-testid="prd469-upload-record-save"
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>
                {uploading ? '上传中…' : '上传病历'}
              </button>
            </div>
          </div>
        </Mask>
      )}
    </div>
  );
}

function iconOfType(t: string): string {
  return ({ diary: '📝', medication: '💊', abnormal: '⚠️', upload: '📄' } as any)[t] || '•';
}
function labelOfType(t: string): string {
  return ({ diary: '健康日记', medication: '用药打卡', abnormal: '异常告警', upload: '报告上传' } as any)[t] || '健康事件';
}
