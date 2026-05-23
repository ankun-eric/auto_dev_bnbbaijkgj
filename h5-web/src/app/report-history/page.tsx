'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { SwipeAction, SpinLoading } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';

interface FamilyMember {
  id: number;
  nickname: string;
  is_self: boolean;
  relationship_type?: string;
  relation_type_name?: string;
}

interface ReportItem {
  id: number;
  report_name: string;
  report_date: string;
  source_type: string;
  ai_summary: string;
  is_comparison: boolean;
  created_at: string;
}

function ReportHistoryListInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preSelected = searchParams?.get('pre_selected');

  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [showMemberPicker, setShowMemberPicker] = useState(false);

  const fetchMembers = useCallback(async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: FamilyMember[] = Array.isArray(data.items) ? data.items : [];
      setMembers(items);
      if (items.length > 0 && selectedMemberId == null) {
        const fallback = items.find((m) => m.is_self) || items[0];
        setSelectedMemberId(fallback.id);
      }
    } catch {
      setMembers([]);
    }
  }, [selectedMemberId]);

  const fetchReports = useCallback(async (memberId: number, pageNum: number, append = false) => {
    if (!append) setLoading(true);
    else setLoadingMore(true);
    try {
      const res: any = await api.get(`/api/report-history/list?member_id=${memberId}&page=${pageNum}&page_size=20`);
      const data = res.data || res;
      const items: ReportItem[] = Array.isArray(data.items) ? data.items : [];
      if (append) {
        setReports((prev) => [...prev, ...items]);
      } else {
        setReports(items);
      }
      setHasMore(items.length >= 20);
    } catch {
      if (!append) setReports([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  useEffect(() => {
    if (selectedMemberId == null) return;
    setPage(1);
    setCheckedIds(new Set());
    fetchReports(selectedMemberId, 1);
  }, [selectedMemberId, fetchReports]);

  useEffect(() => {
    if (preSelected && reports.length > 0) {
      const id = Number(preSelected);
      if (id && reports.some((r) => r.id === id)) {
        setCheckedIds(new Set([id]));
      }
    }
  }, [preSelected, reports]);

  const loadMore = () => {
    if (!hasMore || loadingMore || !selectedMemberId) return;
    const nextPage = page + 1;
    setPage(nextPage);
    fetchReports(selectedMemberId, nextPage, true);
  };

  const toggleCheck = (id: number) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 2) return prev;
        next.add(id);
      }
      return next;
    });
  };

  const handleCompare = async () => {
    if (checkedIds.size !== 2 || !selectedMemberId) return;
    setComparing(true);
    const ids = Array.from(checkedIds);
    try {
      const res: any = await api.post('/api/report-history/compare', {
        member_id: selectedMemberId,
        report_history_ids: ids,
      });
      const data = res.data || res;
      if (data?.id) {
        router.push(`/report-history/comparison/${data.id}`);
      } else {
        showToast('对比分析失败', 'fail');
      }
    } catch {
      showToast('对比分析请求失败', 'fail');
    } finally {
      setComparing(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/report-history/${id}`);
      setReports((prev) => prev.filter((r) => r.id !== id));
      setCheckedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      showToast('已删除');
    } catch {
      showToast('删除失败', 'fail');
    }
  };

  const selectedMember = useMemo(
    () => members.find((m) => m.id === selectedMemberId) || null,
    [members, selectedMemberId],
  );

  const getMemberDisplayName = (m: FamilyMember) =>
    m.nickname || (m.is_self ? '本人' : m.relation_type_name || m.relationship_type || '家人');

  const sourceLabel = (type: string) => {
    if (type === '对比报告' || type === 'comparison' || type === 'compare') return '对比报告';
    return '体检报告';
  };

  const sourceStyle = (type: string): React.CSSProperties => {
    if (type === '对比报告' || type === 'comparison' || type === 'compare') {
      return { background: '#EFF6FF', color: '#0284C7', border: '1px solid #BAE6FD' };
    }
    return { background: '#F3F4F6', color: '#6B7280', border: '1px solid #E5E7EB' };
  };

  const bottomBarHeight = checkedIds.size > 0 ? 70 : 0;

  return (
    <div style={{ background: '#F0F9FF', minHeight: '100vh', paddingBottom: bottomBarHeight + 16 }}>
      {/* Nav Bar */}
      <div style={{ position: 'sticky', top: 0, zIndex: 60, background: 'linear-gradient(180deg, #0284C7, #0EA5E9)' }}>
        <GreenNavBar>历史报告</GreenNavBar>
      </div>

      {/* Member Selector */}
      <div style={{ padding: '12px 16px 8px' }}>
        <div
          onClick={() => setShowMemberPicker(!showMemberPicker)}
          style={{
            background: '#fff',
            borderRadius: 12,
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, color: '#6B7280' }}>咨询人：</span>
            <span style={{ fontSize: 15, fontWeight: 600, color: '#0C4A6E' }}>
              {selectedMember ? getMemberDisplayName(selectedMember) : '选择咨询人'}
            </span>
          </div>
          <span style={{ fontSize: 12, color: '#9CA3AF', transform: showMemberPicker ? 'rotate(180deg)' : 'none', transition: 'transform 200ms' }}>▼</span>
        </div>

        {showMemberPicker && (
          <div style={{
            background: '#fff',
            borderRadius: 12,
            marginTop: 4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            overflow: 'hidden',
          }}>
            {members.map((m) => (
              <div
                key={m.id}
                onClick={() => {
                  setSelectedMemberId(m.id);
                  setShowMemberPicker(false);
                }}
                style={{
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  background: m.id === selectedMemberId ? '#F0F9FF' : '#fff',
                  borderBottom: '1px solid #F3F4F6',
                }}
              >
                <span style={{ fontSize: 14, color: m.id === selectedMemberId ? '#0284C7' : '#374151', fontWeight: m.id === selectedMemberId ? 600 : 400 }}>
                  {getMemberDisplayName(m)}
                </span>
                {m.id === selectedMemberId && <span style={{ color: '#0284C7', fontSize: 14 }}>✓</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Report List */}
      <div style={{ padding: '0 16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <SpinLoading color="#0284C7" style={{ fontSize: 28 }} />
            <div style={{ color: '#9CA3AF', fontSize: 14, marginTop: 12 }}>加载中…</div>
          </div>
        ) : reports.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
            <div style={{ color: '#9CA3AF', fontSize: 15 }}>暂无历史报告</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {reports.map((report) => (
              <SwipeAction
                key={report.id}
                rightActions={[
                  {
                    key: 'delete',
                    text: '删除',
                    color: 'danger',
                    onClick: () => handleDelete(report.id),
                  },
                ]}
              >
                <div
                  style={{
                    background: '#fff',
                    borderRadius: 16,
                    padding: '14px 14px 14px 10px',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                  }}
                >
                  {/* Checkbox */}
                  <div
                    onClick={(e) => { e.stopPropagation(); toggleCheck(report.id); }}
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      border: checkedIds.has(report.id) ? '2px solid #0284C7' : '2px solid #D1D5DB',
                      background: checkedIds.has(report.id) ? '#0284C7' : '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  >
                    {checkedIds.has(report.id) && (
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 7l3 3 5-5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>

                  {/* Card Content */}
                  <div
                    style={{ flex: 1, minWidth: 0, cursor: 'pointer' }}
                    onClick={() => router.push(report.is_comparison ? `/report-history/comparison/${report.id}` : `/report-history/${report.id}`)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 15, fontWeight: 600, color: '#1F2937', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                        {report.report_name || '未命名报告'}
                      </span>
                      <span style={{
                        fontSize: 11,
                        fontWeight: 500,
                        padding: '2px 8px',
                        borderRadius: 10,
                        whiteSpace: 'nowrap',
                        ...sourceStyle(report.source_type),
                      }}>
                        {sourceLabel(report.source_type)}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 6 }}>
                      {report.report_date || report.created_at || ''}
                    </div>
                    {report.ai_summary && (
                      <div style={{
                        fontSize: 13,
                        color: '#6B7280',
                        lineHeight: 1.5,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}>
                        {report.ai_summary}
                      </div>
                    )}
                  </div>
                </div>
              </SwipeAction>
            ))}

            {/* Load More */}
            {hasMore && (
              <div
                onClick={loadMore}
                style={{ textAlign: 'center', padding: '16px 0', cursor: 'pointer' }}
              >
                {loadingMore ? (
                  <SpinLoading color="#0284C7" style={{ fontSize: 20 }} />
                ) : (
                  <span style={{ color: '#0284C7', fontSize: 13 }}>加载更多</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Action Bar */}
      {checkedIds.size > 0 && (
        <div style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#fff',
          borderTop: '1px solid #E5E7EB',
          padding: '12px 16px',
          zIndex: 50,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {checkedIds.size === 1 ? (
            <span style={{ fontSize: 14, color: '#9CA3AF' }}>请再选一份报告进行对比</span>
          ) : (
            <button
              onClick={handleCompare}
              disabled={comparing}
              style={{
                width: '100%',
                height: 44,
                borderRadius: 22,
                border: 'none',
                background: comparing ? '#93C5FD' : 'linear-gradient(135deg, #0284C7, #0EA5E9)',
                color: '#fff',
                fontSize: 16,
                fontWeight: 600,
                cursor: comparing ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              {comparing ? (
                <>
                  <SpinLoading color="#fff" style={{ fontSize: 16, '--size': '16px' } as any} />
                  <span>分析中…</span>
                </>
              ) : (
                '开始对比分析'
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReportHistoryListPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <ReportHistoryListInner />
    </Suspense>
  );
}
