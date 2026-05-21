'use client';

/**
 * [PRD-HEALTH-ARCHIVE-V5-20260521] 就医资料回收站
 *
 * 路由：/medical-records/trash?member_id=xxx
 *
 * 功能：列出本成员已删除资料 + 恢复 / 立即彻底删除 / 显示剩余天数
 */

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast, Dialog } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import {
  MedicalRecordItem,
  listTrash,
  permanentDelete,
  restoreRecord,
} from '@/lib/api/health-archive-v5';

function TrashInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const memberIdParam = sp.get('member_id');
  const memberId = memberIdParam ? Number(memberIdParam) : null;

  const [items, setItems] = useState<MedicalRecordItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listTrash(memberId);
      setItems(res.items || []);
    } catch {
      Toast.show({ icon: 'fail', content: '加载失败' });
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => { load(); }, [load]);

  const doRestore = useCallback(async (id: number) => {
    try {
      await restoreRecord(id);
      Toast.show({ icon: 'success', content: '已恢复' });
      load();
    } catch { Toast.show({ icon: 'fail', content: '恢复失败' }); }
  }, [load]);

  const doDelete = useCallback(async (id: number) => {
    const ok = await Dialog.confirm({ content: '确定要立即彻底删除此资料？此操作不可撤销。' });
    if (!ok) return;
    try {
      await permanentDelete(id);
      Toast.show({ icon: 'success', content: '已彻底删除' });
      load();
    } catch { Toast.show({ icon: 'fail', content: '删除失败' }); }
  }, [load]);

  return (
    <div style={{ background: '#F5F7FA', minHeight: '100vh', paddingBottom: 64 }}>
      <GreenNavBar back={() => router.back()}>回收站</GreenNavBar>
      <div style={{ padding: 16 }}>
        {loading && <div style={{ textAlign: 'center', padding: 40, color: '#9CA3AF' }}>加载中...</div>}
        {!loading && items.length === 0 && (
          <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF' }}>回收站为空</div>
        )}
        {items.map((it) => (
          <div key={it.id} style={{ background: '#fff', borderRadius: 12, padding: 12, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 52, height: 52, borderRadius: 6, background: it.thumbnail_url ? `url(${it.thumbnail_url}) center/cover` : '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {!it.thumbnail_url && <span style={{ fontSize: 22 }}>📄</span>}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.title}</div>
              <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>
                {it.category_label} · 剩余 {it.days_to_purge ?? 0} 天
              </div>
            </div>
            <button onClick={() => doRestore(it.id)} style={{ padding: '5px 10px', borderRadius: 6, border: '1px solid #10B981', background: '#fff', color: '#10B981', fontSize: 12 }}>恢复</button>
            <button onClick={() => doDelete(it.id)} style={{ padding: '5px 10px', borderRadius: 6, border: '1px solid #DC2626', background: '#fff', color: '#DC2626', fontSize: 12 }}>彻底删除</button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TrashPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>加载中...</div>}>
      <TrashInner />
    </Suspense>
  );
}
