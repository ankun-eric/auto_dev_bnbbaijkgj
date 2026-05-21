'use client';

/**
 * [PRD-HEALTH-ARCHIVE-V5-20260521] 就医资料模块
 *
 * 路由：/medical-records?member_id=xxx&category=xxx
 *
 * 功能：
 *   F18 4 分组：病例单 / 体检报告 / 药物 / 其他
 *   F19 上传：图片 + PDF，单次最多 9 文件作为 1 份资料
 *   F22 全屏预览（同分组左右滑切换）—— 见详情页
 *   F23 回收站入口
 */

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import {
  MedicalRecordItem,
  RecordCategory,
  RecordFile,
  createRecord,
  listRecords,
} from '@/lib/api/health-archive-v5';
import api from '@/lib/api';

const CATS: { key: RecordCategory; label: string; color: string; emoji: string }[] = [
  { key: 'case_note', label: '病例单', color: '#3B82F6', emoji: '📋' },
  { key: 'checkup_report', label: '体检报告', color: '#10B981', emoji: '🔬' },
  { key: 'drug', label: '药物', color: '#8B5CF6', emoji: '💊' },
  { key: 'other', label: '其他', color: '#6B7280', emoji: '📦' },
];

const SOURCE_BADGE: Record<string, { bg: string; text: string }> = {
  ai_checkup: { bg: '#10B981', text: 'AI 体检' },
  ai_drug: { bg: '#3B82F6', text: 'AI 药物' },
  manual: { bg: '#9CA3AF', text: '手动' },
};

function MedicalRecordsInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const memberIdParam = sp.get('member_id');
  const memberId = memberIdParam ? Number(memberIdParam) : null;

  const [items, setItems] = useState<MedicalRecordItem[]>([]);
  const [grouped, setGrouped] = useState<Record<RecordCategory, number>>({
    case_note: 0, checkup_report: 0, drug: 0, other: 0,
  });
  const [expanded, setExpanded] = useState<Record<RecordCategory, boolean>>({
    case_note: true, checkup_report: true, drug: true, other: true,
  });
  const [loading, setLoading] = useState(false);
  const [showUpload, setShowUpload] = useState<RecordCategory | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listRecords({ memberId });
      setItems(res.items || []);
      setGrouped(res.grouped || { case_note: 0, checkup_report: 0, drug: 0, other: 0 });
    } catch {
      showToast('加载失败', 'fail');
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => { load(); }, [load]);

  const itemsByCategory = useMemo(() => {
    const map: Record<RecordCategory, MedicalRecordItem[]> = {
      case_note: [], checkup_report: [], drug: [], other: [],
    };
    items.forEach((it) => {
      if (map[it.category]) map[it.category].push(it);
    });
    return map;
  }, [items]);

  return (
    <div style={{ background: '#F5F7FA', minHeight: '100vh', paddingBottom: 64 }}>
      <GreenNavBar
        back={() => router.back()}
        right={
          <button
            onClick={() => setShowUpload('case_note')}
            style={{ color: '#fff', background: 'transparent', border: 'none', fontSize: 22, fontWeight: 600 }}
            aria-label="上传"
          >+</button>
        }
      >就医资料</GreenNavBar>

      <div style={{ padding: 16 }}>
        {loading && <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>加载中...</div>}
        {!loading && CATS.map((c) => {
          const list = itemsByCategory[c.key];
          const open = expanded[c.key];
          return (
            <div key={c.key} style={{
              background: '#fff', borderRadius: 12, marginBottom: 12, overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}>
              <div
                onClick={() => setExpanded((s) => ({ ...s, [c.key]: !s[c.key] }))}
                style={{
                  display: 'flex', alignItems: 'center', padding: '14px 16px', cursor: 'pointer',
                  borderLeft: `4px solid ${c.color}`,
                }}
              >
                <span style={{ fontSize: 18, marginRight: 8 }}>{c.emoji}</span>
                <span style={{ flex: 1, fontWeight: 600 }}>{c.label}</span>
                <span style={{ color: '#9CA3AF', fontSize: 13, marginRight: 8 }}>{grouped[c.key] || 0}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); setShowUpload(c.key); }}
                  style={{
                    background: c.color, color: '#fff', border: 'none', borderRadius: 6,
                    padding: '4px 10px', fontSize: 12, marginRight: 6,
                  }}
                >+ 上传</button>
                <span style={{ color: '#9CA3AF', fontSize: 12 }}>{open ? '▾' : '▸'}</span>
              </div>
              {open && (
                <div style={{ padding: '0 12px 12px' }}>
                  {list.length === 0 ? (
                    <div style={{ padding: 16, color: '#9CA3AF', fontSize: 13, textAlign: 'center' }}>
                      暂无资料，点击右上角 + 上传
                    </div>
                  ) : list.map((it) => (
                    <div
                      key={it.id}
                      onClick={() => router.push(`/medical-records/${it.id}`)}
                      style={{
                        display: 'flex', alignItems: 'center', padding: 10,
                        borderTop: '1px solid #F3F4F6', cursor: 'pointer', gap: 10,
                      }}
                    >
                      <div style={{
                        width: 52, height: 52, borderRadius: 6,
                        background: it.thumbnail_url ? `url(${it.thumbnail_url}) center/cover` : '#F3F4F6',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                      }}>
                        {!it.thumbnail_url && <span style={{ fontSize: 22 }}>📄</span>}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.title}</div>
                        <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
                          <span style={{
                            display: 'inline-block', background: SOURCE_BADGE[it.source]?.bg || '#9CA3AF',
                            color: '#fff', padding: '1px 6px', borderRadius: 3, marginRight: 6, fontSize: 11,
                          }}>{SOURCE_BADGE[it.source]?.text || '其他'}</span>
                          {it.record_date || it.created_at.slice(0, 10)}
                          {it.file_count > 1 ? ` · ${it.file_count} 文件` : ''}
                        </div>
                      </div>
                      <span style={{ color: '#9CA3AF', fontSize: 12 }}>›</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {/* 回收站入口 */}
        <div
          onClick={() => router.push(`/medical-records/trash${memberId ? `?member_id=${memberId}` : ''}`)}
          style={{
            background: '#fff', borderRadius: 12, padding: 14,
            display: 'flex', alignItems: 'center', cursor: 'pointer',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          }}
        >
          <span style={{ fontSize: 18, marginRight: 8 }}>🗑️</span>
          <span style={{ flex: 1, color: '#374151' }}>回收站</span>
          <span style={{ color: '#9CA3AF', fontSize: 12 }}>30 天后自动清理</span>
          <span style={{ color: '#9CA3AF', marginLeft: 6 }}>›</span>
        </div>
      </div>

      {showUpload && (
        <UploadSheet
          memberId={memberId}
          defaultCategory={showUpload}
          onClose={() => setShowUpload(null)}
          onSuccess={() => { setShowUpload(null); load(); }}
        />
      )}
    </div>
  );
}

function UploadSheet({
  memberId,
  defaultCategory,
  onClose,
  onSuccess,
}: {
  memberId: number | null;
  defaultCategory: RecordCategory;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [category, setCategory] = useState<RecordCategory>(defaultCategory);
  const [title, setTitle] = useState('');
  const [recordDate, setRecordDate] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}-${`${d.getMonth() + 1}`.padStart(2, '0')}-${`${d.getDate()}`.padStart(2, '0')}`;
  });
  const [files, setFiles] = useState<RecordFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const handlePick = useCallback(async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const all = Array.from(fileList);
    if (files.length + all.length > 9) {
      showToast('一份资料最多 9 个文件', 'fail');
      return;
    }
    setUploading(true);
    const newFiles: RecordFile[] = [];
    for (const f of all) {
      const isPdf = f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf');
      const maxSize = isPdf ? 20 * 1024 * 1024 : 10 * 1024 * 1024;
      if (f.size > maxSize) {
        showToast(isPdf ? 'PDF 不能超过 20MB' : '单文件不能超过 10MB', 'fail');
        continue;
      }
      try {
        const fd = new FormData();
        fd.append('file', f);
        const endpoint = isPdf ? '/api/upload/file' : '/api/upload/image';
        const res: any = await api.post(endpoint, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const url = (res && (res.data?.url || res.url || res.data?.file_url)) as string;
        if (!url) throw new Error('upload no url');
        newFiles.push({
          file_url: url,
          file_name: f.name,
          file_type: isPdf ? 'pdf' : 'image',
          file_size: f.size,
        });
      } catch (e) {
        showToast(`上传失败: ${f.name}`, 'fail');
      }
    }
    if (newFiles.length) setFiles((prev) => [...prev, ...newFiles]);
    setUploading(false);
  }, [files.length]);

  const submit = useCallback(async () => {
    if (!title.trim()) {
      showToast('请填写标题', 'fail');
      return;
    }
    if (files.length === 0) {
      showToast('请至少上传 1 个文件', 'fail');
      return;
    }
    try {
      await createRecord({
        member_id: memberId,
        category,
        title: title.trim(),
        record_date: recordDate,
        source: 'manual',
        files,
      });
      showToast('已保存');
      onSuccess();
    } catch (e: any) {
      showToast(e?.message || '保存失败', 'fail');
    }
  }, [title, files, memberId, category, recordDate, onSuccess]);

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100 }}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ position: 'absolute', left: 0, right: 0, bottom: 0, background: '#fff', borderRadius: '16px 16px 0 0', padding: 16, maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div style={{ width: 36, height: 4, background: '#D1D5DB', borderRadius: 2, margin: '0 auto 12px' }} />
        <div style={{ fontWeight: 600, marginBottom: 12 }}>上传就医资料</div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>资料类型</div>
          <div style={{ display: 'flex', gap: 8 }}>
            {CATS.map((c) => (
              <button
                key={c.key}
                onClick={() => setCategory(c.key)}
                style={{
                  flex: 1, padding: '8px 0', borderRadius: 8,
                  border: '1px solid ' + (category === c.key ? c.color : '#E5E7EB'),
                  background: category === c.key ? c.color + '22' : '#fff',
                  color: category === c.key ? c.color : '#374151',
                  fontSize: 13,
                }}
              >{c.emoji} {c.label}</button>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>标题</div>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="如：体检报告 2026.05"
            style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #E5E7EB' }}
          />
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>资料日期</div>
          <input
            type="date"
            value={recordDate}
            onChange={(e) => setRecordDate(e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #E5E7EB' }}
          />
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>文件（最多 9 个，图片 ≤ 10MB / PDF ≤ 20MB）</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {files.map((f, i) => (
              <div key={i} style={{ position: 'relative', width: 64, height: 64, borderRadius: 6, background: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {f.file_type === 'image' ? (
                  <img src={f.file_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 6 }} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                ) : (
                  <span style={{ fontSize: 11, color: '#374151', textAlign: 'center', padding: 4, overflow: 'hidden' }}>📄 PDF</span>
                )}
                <button
                  onClick={() => setFiles((s) => s.filter((_, idx) => idx !== i))}
                  style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: 9, background: '#DC2626', color: '#fff', border: 'none', fontSize: 12, lineHeight: '18px', padding: 0 }}
                >×</button>
              </div>
            ))}
            {files.length < 9 && (
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                style={{ width: 64, height: 64, borderRadius: 6, border: '1px dashed #D1D5DB', background: '#fff', color: '#9CA3AF', fontSize: 24 }}
              >{uploading ? '...' : '+'}</button>
            )}
            <input
              ref={fileRef}
              type="file"
              multiple
              accept="image/*,application/pdf"
              style={{ display: 'none' }}
              onChange={(e) => { handlePick(e.target.files); e.target.value = ''; }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onClose} style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', color: '#374151' }}>取消</button>
          <button onClick={submit} disabled={uploading} style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: 'none', background: '#10B981', color: '#fff', opacity: uploading ? 0.6 : 1 }}>保存</button>
        </div>
      </div>
    </div>
  );
}

export default function MedicalRecordsPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>加载中...</div>}>
      <MedicalRecordsInner />
    </Suspense>
  );
}
