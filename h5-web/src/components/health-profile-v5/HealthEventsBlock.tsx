'use client';

/**
 * [PRD-469 M8 + v2 P0] 健康事件 Tab —— 时间轴 + 手动日记 + 病历卡上传 OCR
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Toast, Mask } from 'antd-mobile';
import api from '@/lib/api';

interface EventItem {
  id: number;
  event_type: string;
  title?: string;
  content?: string;
  event_date: string;
  tags: string[];
}

const TYPE_FILTERS = [
  { value: '', label: '全部' },
  { value: 'diary', label: '日记' },
  { value: 'medication', label: '用药' },
  { value: 'abnormal', label: '异常' },
  { value: 'upload', label: '报告' },
];

const DIARY_TAGS = ['不适', '复诊', '用药调整', '其他'];

interface Props {
  profileId?: number;
  token: any;
}

interface MedicalRecord {
  id: number;
  title?: string;
  image_url?: string;
  parsed_hospital?: string;
  parsed_department?: string;
  parsed_diagnosis?: string;
  parsed_visit_date?: string;
  parsed_doctor?: string;
  parse_status?: string;
  created_at?: string;
}

export default function HealthEventsBlock({ profileId, token: T }: Props) {
  const [items, setItems] = useState<EventItem[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [adding, setAdding] = useState(false);

  const [draftTitle, setDraftTitle] = useState('');
  const [draftContent, setDraftContent] = useState('');
  const [draftTag, setDraftTag] = useState<string>('');
  const [draftDate, setDraftDate] = useState<string>(new Date().toISOString().slice(0, 10));

  // [PRD-469 v2 P0 M8] 病历卡列表 + OCR 上传
  const [medicalRecords, setMedicalRecords] = useState<MedicalRecord[]>([]);
  const [uploadingOcr, setUploadingOcr] = useState(false);
  const [showRecordDetail, setShowRecordDetail] = useState<MedicalRecord | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const fetchMedicalRecords = useCallback(async () => {
    try {
      const qs = profileId ? `?profile_id=${profileId}` : '';
      const res: any = await api.get(`/api/prd469/medical-record/list${qs}`);
      const data = res.data || res;
      setMedicalRecords(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedicalRecords([]);
    }
  }, [profileId]);

  useEffect(() => { fetchMedicalRecords(); }, [fetchMedicalRecords]);

  const handleUploadMedicalCard = async (file: File) => {
    setUploadingOcr(true);
    try {
      // 1) 调通用 OCR
      const fd = new FormData();
      fd.append('file', file);
      const ocrRes: any = await api.post('/api/ocr/recognize', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const ocrData = ocrRes?.data || ocrRes;
      const text = ocrData?.text || ocrData?.ocr_text || '';
      const imageUrl = ocrData?.image_url || ocrData?.original_image_url || '';
      if (!text) {
        Toast.show({ content: 'OCR 未识别到文字', icon: 'fail' });
        return;
      }
      // 2) 创建病历卡（后端自动同步事件）
      await api.post('/api/prd469/medical-record', {
        profile_id: profileId,
        image_url: imageUrl,
        ocr_text: text,
      });
      Toast.show({ content: '病历卡已添加', icon: 'success' });
      await Promise.all([fetchMedicalRecords(), fetchTimeline()]);
    } catch {
      Toast.show({ content: '上传失败', icon: 'fail' });
    } finally {
      setUploadingOcr(false);
    }
  };

  const handleDeleteRecord = async (id: number) => {
    try {
      await api.delete(`/api/prd469/medical-record/${id}`);
      await Promise.all([fetchMedicalRecords(), fetchTimeline()]);
      Toast.show({ content: '已删除', icon: 'success' });
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

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
      Toast.show({ content: '请填写标题或内容', icon: 'fail' });
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
      Toast.show({ content: '已记录', icon: 'success' });
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
  };

  return (
    <div id="health-events" data-testid="prd469-health-events" style={{ padding: '12px 16px 80px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0 12px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: 0 }}>健康事件</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploadingOcr}
            data-testid="prd469-upload-medical-btn"
            style={{
              padding: '6px 12px',
              background: uploadingOcr ? '#9ca3af' : '#0ea5e9',
              color: '#fff', border: 'none', borderRadius: 16,
              fontSize: 13, fontWeight: 600,
            }}
          >
            {uploadingOcr ? '识别中…' : '📷 病历卡'}
          </button>
          <button
            onClick={() => setAdding(true)}
            data-testid="prd469-add-event-btn"
            style={{
              padding: '6px 14px', background: T.brand500, color: '#fff',
              border: 'none', borderRadius: 16, fontSize: 13, fontWeight: 600,
            }}
          >+ 写日记</button>
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleUploadMedicalCard(f);
          e.target.value = '';
        }}
      />

      {/* [PRD-469 v2 P0 M8] 病历卡列表 */}
      {medicalRecords.length > 0 && (
        <div data-testid="prd469-medical-records" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700, marginBottom: 8 }}>
            📋 病历卡（{medicalRecords.length}）
          </div>
          <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 8 }}>
            {medicalRecords.map((r) => (
              <div
                key={r.id}
                onClick={() => setShowRecordDetail(r)}
                data-testid={`prd469-medical-card-${r.id}`}
                style={{
                  flex: '0 0 auto', width: 200,
                  background: '#fff', borderRadius: 12, padding: 10,
                  borderLeft: '3px solid #0ea5e9',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  cursor: 'pointer',
                }}
              >
                {r.image_url && (
                  <img
                    src={r.image_url}
                    alt="病历卡"
                    style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 6, marginBottom: 6 }}
                  />
                )}
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 2 }}>
                  {r.parsed_hospital || r.title || '病历卡'}
                </div>
                {r.parsed_diagnosis && (
                  <div style={{ fontSize: 11, color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.parsed_diagnosis}
                  </div>
                )}
                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>
                  {r.parsed_visit_date || (r.created_at || '').slice(0, 10)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
          暂无事件记录，点击右上角「写日记」开始记录
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((e) => (
            <div
              key={e.id}
              data-testid={`prd469-event-${e.id}`}
              style={{
                background: '#fff', borderRadius: 12, padding: 14,
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                borderLeft: '3px solid #22c55e',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>
                  {iconOfType(e.event_type)} {e.title || labelOfType(e.event_type)}
                </span>
                <span style={{ fontSize: 12, color: '#9ca3af' }}>{e.event_date}</span>
              </div>
              {e.content && (
                <div style={{ fontSize: 13, color: '#4b5563', lineHeight: 1.6, marginBottom: 4 }}>{e.content}</div>
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
          ))}
        </div>
      )}

      {/* [PRD-469 v2 P0 M8] 病历卡详情查看 */}
      {showRecordDetail && (
        <Mask visible color="rgba(0,0,0,0.5)">
          <div
            data-testid="prd469-record-detail-modal"
            style={{
              position: 'fixed', left: 16, right: 16, top: '8%', bottom: '8%',
              background: '#fff', borderRadius: 16,
              display: 'flex', flexDirection: 'column',
            }}
          >
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>病历卡详情</span>
              <span onClick={() => setShowRecordDetail(null)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
              {showRecordDetail.image_url && (
                <img
                  src={showRecordDetail.image_url}
                  alt="病历卡原图"
                  style={{ width: '100%', borderRadius: 8, marginBottom: 12 }}
                />
              )}
              <DetailRow label="医院" value={showRecordDetail.parsed_hospital} T={T} />
              <DetailRow label="科室" value={showRecordDetail.parsed_department} T={T} />
              <DetailRow label="就诊日期" value={showRecordDetail.parsed_visit_date} T={T} />
              <DetailRow label="医师" value={showRecordDetail.parsed_doctor} T={T} />
              <DetailRow label="诊断" value={showRecordDetail.parsed_diagnosis} T={T} />
            </div>
            <div style={{ padding: 12, borderTop: `1px solid ${T.brand100}`, display: 'flex', gap: 8 }}>
              <button
                onClick={() => {
                  handleDeleteRecord(showRecordDetail.id);
                  setShowRecordDetail(null);
                }}
                data-testid="prd469-delete-record"
                style={{ flex: 1, padding: '10px 0', borderRadius: 20, background: '#fee2e2', color: '#dc2626', border: 'none', fontSize: 14 }}
              >删除</button>
              <button
                onClick={() => setShowRecordDetail(null)}
                style={{ flex: 1, padding: '10px 0', borderRadius: 20, background: T.brand500, color: '#fff', border: 'none', fontSize: 14 }}
              >关闭</button>
            </div>
          </div>
        </Mask>
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
    </div>
  );
}

function iconOfType(t: string): string {
  return ({ diary: '📝', medication: '💊', abnormal: '⚠️', upload: '📄' } as any)[t] || '•';
}
function labelOfType(t: string): string {
  return ({ diary: '健康日记', medication: '用药打卡', abnormal: '异常告警', upload: '报告上传' } as any)[t] || '健康事件';
}

function DetailRow({ label, value, T }: { label: string; value?: string | null; T: any }) {
  return (
    <div style={{ display: 'flex', padding: '8px 0', borderBottom: `1px solid ${T.brand100}` }}>
      <span style={{ width: 80, fontSize: 13, color: '#6b7280' }}>{label}</span>
      <span style={{ flex: 1, fontSize: 14, color: value ? '#1f2937' : '#9ca3af' }}>
        {value || '未识别'}
      </span>
    </div>
  );
}
