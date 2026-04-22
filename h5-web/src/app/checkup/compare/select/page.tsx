'use client';

import { useEffect, useMemo, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Toast, SpinLoading, Empty } from 'antd-mobile';
import api from '@/lib/api';

interface MemberItem {
  id: number;
  nickname: string;
  relationship_type: string;
  is_self?: boolean;
  relation_type_name?: string;
}

interface ReportItem {
  id: number;
  title: string;
  report_date?: string | null;
  created_at: string;
  thumbnail_url?: string | null;
  file_url?: string | null;
}

function CompareSelectContent() {
  const router = useRouter();
  const search = useSearchParams();
  const urlMember = Number(search.get('member_id')) || null;
  const preselect = Number(search.get('preselect')) || null;

  const [step, setStep] = useState<1 | 2>(urlMember ? 2 : 1);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [memberCounts, setMemberCounts] = useState<Record<number, number>>({});
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(urlMember);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => (preselect ? new Set([preselect]) : new Set()));
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Step 1: 加载咨询人列表
  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get('/api/family/members');
        const items: MemberItem[] = res?.items || res?.list || res || [];
        setMembers(items);

        // 并发查各成员报告数量
        const counts: Record<number, number> = {};
        await Promise.all(
          items.map(async (m) => {
            try {
              const r: any = await api.get(`/api/member/${m.id}/reports?for_compare=1`);
              counts[m.id] = (r?.items || []).length;
            } catch {
              counts[m.id] = 0;
            }
          })
        );
        setMemberCounts(counts);
      } catch (e: any) {
        Toast.show({ content: e?.message || '加载咨询人失败' });
      }
    })();
  }, []);

  // Step 2: 加载该咨询人报告
  useEffect(() => {
    if (!selectedMemberId) return;
    setLoading(true);
    (async () => {
      try {
        const res: any = await api.get(`/api/member/${selectedMemberId}/reports?for_compare=1`);
        setReports(res?.items || []);
      } catch (e: any) {
        Toast.show({ content: e?.message || '加载报告失败' });
      } finally {
        setLoading(false);
      }
    })();
  }, [selectedMemberId]);

  const currentMember = useMemo(
    () => members.find((m) => m.id === selectedMemberId) || null,
    [members, selectedMemberId]
  );

  const toggleReport = (rid: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(rid)) {
        next.delete(rid);
      } else {
        if (next.size >= 2) {
          Toast.show({ content: '最多只能选 2 份' });
          return prev;
        }
        next.add(rid);
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!selectedMemberId || selectedIds.size !== 2) return;
    setSubmitting(true);
    try {
      const resp: any = await api.post('/api/report/compare/start', {
        member_id: selectedMemberId,
        report_ids: Array.from(selectedIds),
      });
      const sid = resp?.session_id;
      if (sid) {
        router.replace(`/checkup/chat/${sid}?auto_start=1&type=report_compare`);
      }
    } catch (e: any) {
      Toast.show({ content: e?.message || '创建对比会话失败' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f6f7f9', paddingBottom: 80 }}>
      <NavBar onBack={() => (step === 2 && !urlMember ? setStep(1) : router.back())}>
        报告对比 · {step === 1 ? '选咨询人' : '选 2 份报告'}
      </NavBar>

      {step === 1 && (
        <div style={{ padding: 12 }}>
          {members.length === 0 ? (
            <Empty description="暂无家庭成员，请先在家庭管理中添加" style={{ padding: '40px 0' }} />
          ) : (
            members.map((m) => {
              const count = memberCounts[m.id] ?? 0;
              const disabled = count < 2;
              return (
                <div
                  key={m.id}
                  onClick={() => {
                    if (disabled) {
                      Toast.show({ content: '当前咨询人仅有不足 2 份报告，无法对比' });
                      return;
                    }
                    setSelectedMemberId(m.id);
                    setStep(2);
                  }}
                  style={{
                    background: '#fff',
                    borderRadius: 12,
                    padding: 14,
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    opacity: disabled ? 0.55 : 1,
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 500 }}>
                      {m.nickname || '未命名'}
                      <span style={{ marginLeft: 6, fontSize: 12, color: '#999' }}>
                        {m.relation_type_name || m.relationship_type}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: disabled ? '#cc4e4e' : '#52c41a', marginTop: 4 }}>
                      {count} 份报告{disabled ? ' · 不足 2 份' : ''}
                    </div>
                  </div>
                  <span style={{ color: disabled ? '#ccc' : '#1890ff', fontSize: 13 }}>
                    {disabled ? '不可选' : '选择 →'}
                  </span>
                </div>
              );
            })
          )}
        </div>
      )}

      {step === 2 && (
        <div style={{ padding: 12 }}>
          <div style={{ background: '#e6f7ff', padding: 10, borderRadius: 8, fontSize: 13, color: '#0050b3', marginBottom: 10 }}>
            咨询人：{currentMember?.nickname || ''}（{currentMember?.relation_type_name || currentMember?.relationship_type || ''}）· 请勾选 2 份报告
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: 'center' }}><SpinLoading color="primary" /></div>
          ) : reports.length === 0 ? (
            <Empty description="暂无报告" />
          ) : (
            reports.map((r) => {
              const selected = selectedIds.has(r.id);
              const disabled = !selected && selectedIds.size >= 2;
              return (
                <div
                  key={r.id}
                  onClick={() => !disabled && toggleReport(r.id)}
                  style={{
                    background: '#fff',
                    borderRadius: 12,
                    padding: 12,
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    border: selected ? '2px solid #1890ff' : '2px solid transparent',
                    opacity: disabled ? 0.4 : 1,
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      border: '2px solid ' + (selected ? '#1890ff' : '#ccc'),
                      background: selected ? '#1890ff' : '#fff',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 14,
                      flexShrink: 0,
                    }}
                  >
                    {selected ? '✓' : ''}
                  </div>
                  {r.thumbnail_url ? (
                    <img
                      src={r.thumbnail_url}
                      alt=""
                      style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 8 }}
                    />
                  ) : (
                    <div style={{ width: 56, height: 56, borderRadius: 8, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>📄</div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                      {new Date(r.created_at).toLocaleString('zh-CN')}
                    </div>
                  </div>
                </div>
              );
            })
          )}

          {/* 底部固定按钮 */}
          <div
            style={{
              position: 'fixed',
              bottom: 0,
              left: 0,
              right: 0,
              padding: '10px 16px',
              background: '#fff',
              borderTop: '1px solid #eee',
            }}
          >
            <button
              onClick={handleSubmit}
              disabled={selectedIds.size !== 2 || submitting}
              style={{
                width: '100%',
                padding: 14,
                borderRadius: 24,
                border: 0,
                fontSize: 15,
                fontWeight: 500,
                color: '#fff',
                background:
                  selectedIds.size === 2 && !submitting
                    ? 'linear-gradient(135deg, #52c41a, #13c2c2)'
                    : '#d9d9d9',
              }}
            >
              {submitting ? '创建中...' : `下一步（已选 ${selectedIds.size}/2）`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CompareSelectPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}><SpinLoading color="primary" /></div>}>
      <CompareSelectContent />
    </Suspense>
  );
}
