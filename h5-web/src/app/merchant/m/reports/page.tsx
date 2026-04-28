'use client';

// [2026-04-24] 移动端 - 报表 PRD §4.5
// K1：4 个汇总卡片 + 简化图表（使用 SVG 自绘，避免引入 echarts 增加体积）

import React, { useEffect, useState } from 'react';
import { NavBar, Tabs, Toast, Button } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId } from '../mobile-lib';

type RangeKey = '1' | '7' | '30';

interface Report {
  total_amount?: number;
  total_orders?: number;
  total_verifications?: number;
  avg_price?: number;
  trend?: { date: string; amount: number }[];
  status_distribution?: { status: string; count: number }[];
}

export default function ReportsMobilePage() {
  const router = useRouter();
  const [range, setRange] = useState<RangeKey>('7');
  const [data, setData] = useState<Report>({});
  const [loading, setLoading] = useState(false);

  const load = async (r: RangeKey = range) => {
    setLoading(true);
    try {
      const sid = getCurrentStoreId();
      const params: any = { days: Number(r) };
      if (sid) params.store_id = sid;
      const res: any = await api.get('/api/merchant/v1/reports', { params });
      setData(res || {});
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(range);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range]);

  const trend = data.trend || [];
  const maxTrend = Math.max(1, ...trend.map((t) => Number(t.amount) || 0));

  const statusColors: Record<string, string> = {
    paid: '#1677ff',
    redeemed: '#52c41a',
    cancelled: '#8c8c8c',
    refunded: '#ff4d4f',
    pending_payment: '#faad14',
    completed: '#52c41a',
  };

  const statusLabel: Record<string, string> = {
    paid: '待核销',
    redeemed: '已核销',
    cancelled: '已取消',
    refunded: '已退款',
    pending_payment: '待支付',
    completed: '已完成',
  };

  const totalStatus = (data.status_distribution || []).reduce((s, x) => s + (x.count || 0), 0) || 1;

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: 24 }}>
      <NavBar onBack={() => router.back()}>报表</NavBar>

      <div style={{ background: '#fff' }}>
        <Tabs activeKey={range} onChange={(k) => setRange(k as RangeKey)}>
          <Tabs.Tab title="今日" key="1" />
          <Tabs.Tab title="近 7 日" key="7" />
          <Tabs.Tab title="近 30 日" key="30" />
        </Tabs>
      </div>

      {/* 汇总卡片 */}
      <div style={{ padding: 12 }}>
        <div
          style={{
            background: '#fff',
            borderRadius: 12,
            padding: 16,
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 12,
          }}
        >
          {[
            { label: '营业额', value: `¥${data.total_amount || 0}`, color: '#fa541c' },
            { label: '订单数', value: data.total_orders ?? 0, color: '#1677ff' },
            { label: '核销数', value: data.total_verifications ?? 0, color: '#52c41a' },
            { label: '客单价', value: `¥${data.avg_price || 0}`, color: '#722ed1' },
          ].map((m) => (
            <div key={m.label} style={{ textAlign: 'center', padding: '12px 0' }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: m.color }}>{m.value}</div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{m.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 趋势图（简化 SVG） */}
      <div style={{ padding: '0 12px 12px' }}>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>营业额趋势</div>
          {trend.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', fontSize: 12, padding: '24px 0' }}>
              {loading ? '加载中...' : '暂无数据'}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <svg width={Math.max(320, trend.length * 40)} height={160} style={{ display: 'block' }}>
                {trend.map((t, i) => {
                  const v = Number(t.amount) || 0;
                  const h = Math.round((v / maxTrend) * 120);
                  const x = i * 40 + 20;
                  const y = 140 - h;
                  return (
                    <g key={i}>
                      <rect x={x - 10} y={y} width={20} height={h} fill="#52c41a" rx={2} />
                      <text x={x} y={155} textAnchor="middle" fontSize={9} fill="#666">
                        {t.date?.slice(5) || ''}
                      </text>
                      {v > 0 && (
                        <text x={x} y={y - 3} textAnchor="middle" fontSize={9} fill="#333">
                          {v.toFixed(0)}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </div>
      </div>

      {/* 状态占比 */}
      <div style={{ padding: '0 12px 12px' }}>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>订单状态占比</div>
          {(data.status_distribution || []).length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', fontSize: 12, padding: '16px 0' }}>
              {loading ? '加载中...' : '暂无数据'}
            </div>
          ) : (
            (data.status_distribution || []).map((s) => {
              const pct = ((s.count / totalStatus) * 100).toFixed(1);
              const c = statusColors[s.status] || '#888';
              return (
                <div key={s.status} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                    <span>{statusLabel[s.status] || s.status}</span>
                    <span>
                      {s.count} · {pct}%
                    </span>
                  </div>
                  <div style={{ height: 6, background: '#f0f0f0', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: c }} />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 引导 PC */}
      <div style={{ padding: 12, textAlign: 'center' }}>
        <div style={{ background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 8, padding: 12, fontSize: 12, color: '#614700' }}>
          查看完整报表明细请使用电脑访问 PC 商家端
          <div style={{ marginTop: 8 }}>
            <Button
              size="mini"
              color="primary"
              fill="outline"
              onClick={() => {
                const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
                const url = `${window.location.origin}${basePath}/merchant/reports?desktop=1`;
                navigator.clipboard?.writeText(url).then(
                  () => Toast.show({ icon: 'success', content: 'PC 链接已复制' }),
                  () => Toast.show({ content: url })
                );
              }}
            >
              复制 PC 端链接
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
