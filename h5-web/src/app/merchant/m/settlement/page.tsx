'use client';

// [2026-04-24] 移动端 - 对账列表 PRD §4.6

import React, { useEffect, useState } from 'react';
import { NavBar, List, Tag, PullToRefresh, Empty, Toast } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

const STATUS_MAP: Record<string, { text: string; color: string }> = {
  pending: { text: '待确认', color: 'warning' },
  confirmed: { text: '已确认', color: 'primary' },
  disputed: { text: '有争议', color: 'danger' },
  settled: { text: '已结算', color: 'success' },
};

export default function SettlementMobilePage() {
  const router = useRouter();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/settlements', { params: { page: 1, page_size: 50 } });
      setRows(res.items || res || []);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar onBack={() => router.back()}>对账结算</NavBar>
      <PullToRefresh onRefresh={load}>
        <div style={{ padding: 12 }}>
          {rows.length === 0 ? (
            <Empty description={loading ? '加载中...' : '暂无对账单'} />
          ) : (
            rows.map((s: any) => {
              const st = STATUS_MAP[s.status] || { text: s.status, color: 'default' };
              return (
                <div
                  key={s.id}
                  onClick={() => router.push(`/merchant/m/settlement/${s.id}`)}
                  style={{
                    background: '#fff',
                    borderRadius: 10,
                    padding: 14,
                    marginBottom: 10,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {s.period || s.cycle || `#${s.id}`}
                    </div>
                    <Tag color={st.color as any}>{st.text}</Tag>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#666' }}>
                    <span>应结金额</span>
                    <span style={{ color: '#fa541c', fontSize: 15, fontWeight: 600 }}>
                      ¥{Number(s.amount || s.total_amount || 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </PullToRefresh>
    </div>
  );
}
