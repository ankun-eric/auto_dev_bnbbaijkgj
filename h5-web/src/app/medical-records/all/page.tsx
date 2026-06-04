'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import GreenNavBar from '@/components/GreenNavBar';
import { BH_TOKENS } from '@/lib/health-tokens';
import { formatRecordTime } from '@/lib/datetime';

const TABS = [
  { key: 'case_note', label: '病例单' },
  { key: 'checkup_report', label: '体检报告' },
  { key: 'drug', label: '药物' },
  { key: 'other', label: '其他' },
] as const;

type TabKey = typeof TABS[number]['key'];

interface RecordItem {
  id: number;
  title?: string;
  name?: string;
  category: string;
  created_at?: string;
  summary?: string;
}

function MedicalRecordsAllInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = (searchParams?.get('tab') as TabKey) || 'case_note';
  const highlightId = searchParams?.get('highlight');
  const memberId = searchParams?.get('member_id');

  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [items, setItems] = useState<RecordItem[]>([]);
  const [loading, setLoading] = useState(false);
  const highlightRef = useRef<HTMLDivElement | null>(null);

  const fetchRecords = useCallback(async (category: string) => {
    setLoading(true);
    try {
      const memberQs = memberId ? `&member_id=${memberId}` : '';
      const res: any = await api.get(`/api/medical-records?category=${category}${memberQs}`);
      const data = res?.data || res || {};
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => {
    fetchRecords(activeTab);
  }, [activeTab, fetchRecords]);

  useEffect(() => {
    if (highlightId && highlightRef.current) {
      setTimeout(() => {
        highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 300);
    }
  }, [highlightId, items]);

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 40 }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 60, background: BH_TOKENS.brand50, boxShadow: '0 1px 6px rgba(0,0,0,0.05)' }}>
        <GreenNavBar onBack={() => router.back()}>就医资料</GreenNavBar>
        <div style={{ display: 'flex', background: '#fff', borderBottom: '1px solid #f1f5f9' }}>
          {TABS.map((tab) => (
            <div
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                flex: 1,
                textAlign: 'center',
                padding: '12px 0',
                fontSize: 14,
                fontWeight: activeTab === tab.key ? 600 : 400,
                color: activeTab === tab.key ? BH_TOKENS.brand600 : '#6B7280',
                borderBottom: activeTab === tab.key ? `2px solid ${BH_TOKENS.brand500}` : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 200ms ease',
              }}
            >
              {tab.label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: 16 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#9CA3AF', fontSize: 14 }}>加载中…</div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
            <div style={{ fontSize: 15, color: '#9CA3AF' }}>暂无{TABS.find(t => t.key === activeTab)?.label}资料</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {items.map((item) => {
              const isHighlighted = String(item.id) === highlightId;
              return (
                <div
                  key={item.id}
                  ref={isHighlighted ? highlightRef : undefined}
                  onClick={() => router.push(`/medical-records/${item.id}`)}
                  style={{
                    background: '#FFFFFF',
                    borderRadius: 12,
                    padding: '14px 16px',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                    cursor: 'pointer',
                    borderLeft: isHighlighted ? `4px solid ${BH_TOKENS.brand500}` : '4px solid transparent',
                    transition: 'border-color 300ms ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 15, fontWeight: 600, color: '#1F2937',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {item.title || item.name || '未命名'}
                      </div>
                      {item.summary && (
                        <div style={{ fontSize: 13, color: '#6B7280', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.summary}
                        </div>
                      )}
                      {item.created_at && (
                        <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>{formatRecordTime(item.created_at)}</div>
                      )}
                    </div>
                    <span style={{ fontSize: 16, color: '#9CA3AF', marginLeft: 8 }}>›</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MedicalRecordsAllPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <MedicalRecordsAllInner />
    </Suspense>
  );
}
