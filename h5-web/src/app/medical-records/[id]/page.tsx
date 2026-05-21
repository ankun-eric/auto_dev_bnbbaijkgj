'use client';

/**
 * [PRD-HEALTH-ARCHIVE-V5-20260521] 就医资料详情页
 *
 * 路由：/medical-records/[id]
 *
 * 功能：
 *   F21 统一详情模板（手动上传带"暂无 AI 解读"占位）
 *   F22 全屏预览 + 同分组左右滑动切换
 *   F23 删除走回收站
 */

export const dynamic = 'force-dynamic';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Toast, Dialog } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import {
  MedicalRecordDetail,
  getRecord,
  patchRecord,
  softDeleteRecord,
} from '@/lib/api/health-archive-v5';

const SOURCE_BADGE: Record<string, { bg: string; text: string }> = {
  ai_checkup: { bg: '#10B981', text: 'AI 体检' },
  ai_drug: { bg: '#3B82F6', text: 'AI 药物' },
  manual: { bg: '#9CA3AF', text: '手动' },
};

export default function MedicalRecordDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);

  const [data, setData] = useState<MedicalRecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState('');
  const [draftRemark, setDraftRemark] = useState('');
  const [preview, setPreview] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(id) || id <= 0) return;
    setLoading(true);
    try {
      const d = await getRecord(id);
      setData(d);
      setDraftTitle(d.title);
      setDraftRemark(d.remark || '');
    } catch {
      Toast.show({ icon: 'fail', content: '资料不存在或加载失败' });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const saveEdit = useCallback(async () => {
    try {
      await patchRecord(id, { title: draftTitle, remark: draftRemark });
      Toast.show({ icon: 'success', content: '已保存' });
      setEditing(false);
      load();
    } catch {
      Toast.show({ icon: 'fail', content: '保存失败' });
    }
  }, [id, draftTitle, draftRemark, load]);

  const remove = useCallback(async () => {
    const ok = await Dialog.confirm({ content: '删除后将进入回收站，30 天后自动清理，是否继续？' });
    if (!ok) return;
    try {
      await softDeleteRecord(id);
      Toast.show({ icon: 'success', content: '已移入回收站' });
      router.back();
    } catch {
      Toast.show({ icon: 'fail', content: '删除失败' });
    }
  }, [id, router]);

  if (loading || !data) {
    return (
      <div style={{ background: '#F5F7FA', minHeight: '100vh' }}>
        <GreenNavBar back={() => router.back()}>资料详情</GreenNavBar>
        <div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>
          {loading ? '加载中...' : '资料不存在'}
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: '#F5F7FA', minHeight: '100vh', paddingBottom: 80 }}>
      <GreenNavBar back={() => router.back()}>资料详情</GreenNavBar>

      <div style={{ padding: 16 }}>
        {/* 标题区 */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12 }}>
          {editing ? (
            <input
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 16, fontWeight: 600 }}
            />
          ) : (
            <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>{data.title}</div>
          )}
          <div style={{ fontSize: 12, color: '#6B7280', marginTop: 6 }}>
            <span style={{
              display: 'inline-block', background: SOURCE_BADGE[data.source]?.bg || '#9CA3AF',
              color: '#fff', padding: '1px 6px', borderRadius: 3, marginRight: 6, fontSize: 11,
            }}>{SOURCE_BADGE[data.source]?.text || '手动'}</span>
            {data.category_label} · {data.record_date || data.created_at.slice(0, 10)}
            {data.file_count > 0 ? ` · ${data.file_count} 文件` : ''}
          </div>
        </div>

        {/* 文件区 */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12 }}>
          <div style={{ fontSize: 13, color: '#374151', fontWeight: 500, marginBottom: 8 }}>原始文件</div>
          {data.files.length === 0 ? (
            <div style={{ color: '#9CA3AF', fontSize: 13 }}>暂无文件</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {data.files.map((f, idx) => (
                <div
                  key={f.id || idx}
                  onClick={() => setPreview(idx)}
                  style={{
                    aspectRatio: '1 / 1', borderRadius: 8, overflow: 'hidden',
                    background: '#F3F4F6', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  {f.file_type === 'image' ? (
                    <img src={f.file_url} alt={f.file_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <div style={{ textAlign: 'center', padding: 4 }}>
                      <div style={{ fontSize: 24 }}>📄</div>
                      <div style={{ fontSize: 11, color: '#6B7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.file_name}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI 解读 */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12 }}>
          <div style={{ fontSize: 13, color: '#374151', fontWeight: 500, marginBottom: 8 }}>AI 解读结果</div>
          {data.ai_interpretation ? (
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
{typeof data.ai_interpretation === 'string' ? data.ai_interpretation : JSON.stringify(data.ai_interpretation, null, 2)}
            </pre>
          ) : (
            <div style={{ background: '#F9FAFB', padding: 10, borderRadius: 8, fontSize: 13, color: '#6B7280' }}>
              暂无 AI 解读（该资料为手动上传），可去【健康档案】或【用药识别】重新解读
            </div>
          )}
        </div>

        {/* 备注 */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12 }}>
          <div style={{ fontSize: 13, color: '#374151', fontWeight: 500, marginBottom: 8 }}>备注</div>
          {editing ? (
            <textarea
              value={draftRemark}
              onChange={(e) => setDraftRemark(e.target.value)}
              rows={3}
              placeholder="可填写备注信息"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #E5E7EB', fontSize: 13 }}
            />
          ) : (
            <div style={{ fontSize: 13, color: data.remark ? '#374151' : '#9CA3AF' }}>{data.remark || '（暂无备注）'}</div>
          )}
        </div>

        {/* 操作 */}
        <div style={{ display: 'flex', gap: 8 }}>
          {editing ? (
            <>
              <button onClick={() => { setEditing(false); setDraftTitle(data.title); setDraftRemark(data.remark || ''); }} style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff' }}>取消</button>
              <button onClick={saveEdit} style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: 'none', background: '#10B981', color: '#fff' }}>保存</button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)} style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff' }}>编辑标题/备注</button>
              <button onClick={remove} style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #DC2626', background: '#fff', color: '#DC2626' }}>删除</button>
            </>
          )}
        </div>
      </div>

      {/* 预览 */}
      {preview != null && (
        <div
          onClick={() => setPreview(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.9)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}
        >
          <div style={{ position: 'absolute', top: 16, right: 16, color: '#fff', fontSize: 24, cursor: 'pointer' }} onClick={() => setPreview(null)}>×</div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, width: '100%' }}>
            {data.files[preview].file_type === 'image' ? (
              <img
                src={data.files[preview].file_url}
                alt=""
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
              />
            ) : (
              <iframe
                src={data.files[preview].file_url}
                style={{ width: '100%', height: '80vh', background: '#fff', borderRadius: 8 }}
                title={data.files[preview].file_name}
              />
            )}
          </div>
          <div style={{ display: 'flex', gap: 16, padding: 16, alignItems: 'center', color: '#fff' }}>
            <button
              onClick={(e) => { e.stopPropagation(); setPreview((p) => p! > 0 ? p! - 1 : 0); }}
              disabled={preview <= 0}
              style={{ background: 'transparent', border: '1px solid #fff', color: '#fff', borderRadius: 6, padding: '6px 14px', opacity: preview <= 0 ? 0.4 : 1 }}
            >‹ 上一份</button>
            <span style={{ fontSize: 13 }}>{preview + 1} / {data.files.length}</span>
            <button
              onClick={(e) => { e.stopPropagation(); setPreview((p) => p! < data.files.length - 1 ? p! + 1 : data.files.length - 1); }}
              disabled={preview >= data.files.length - 1}
              style={{ background: 'transparent', border: '1px solid #fff', color: '#fff', borderRadius: 6, padding: '6px 14px', opacity: preview >= data.files.length - 1 ? 0.4 : 1 }}
            >下一份 ›</button>
          </div>
        </div>
      )}
    </div>
  );
}
