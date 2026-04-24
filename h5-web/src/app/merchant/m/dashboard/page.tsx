'use client';

// [2026-04-24] 移动端 - 工作台（首页） PRD §4.2
// 顶部：门店名 + 切换；4 个概览卡片；快捷操作；最近订单

import React, { useEffect, useRef, useState } from 'react';
import { PullToRefresh, Toast, Dialog } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import {
  getProfile,
  getCurrentStoreId,
  setCurrentStoreId,
  canAccess,
  MerchantLoginProfile,
  roleLabel,
} from '../mobile-lib';

interface Metrics {
  today_orders?: number;
  today_verifications?: number;
  today_amount?: number;
  pending_verify?: number;
  recent_orders?: any[];
  todos?: { title: string; type: string }[];
}

export default function DashboardMobilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<MerchantLoginProfile | null>(null);
  const [metrics, setMetrics] = useState<Metrics>({});
  const [currentStore, setCurrentStore] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<any>(null);

  const currentStoreName = React.useMemo(() => {
    if (!profile) return '';
    const s = profile.stores.find((x) => x.id === currentStore);
    return s?.name || profile.stores[0]?.name || '';
  }, [profile, currentStore]);

  const load = async () => {
    setLoading(true);
    try {
      const params: any = {};
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      const res: any = await api.get('/api/merchant/v1/dashboard/metrics', { params });
      setMetrics(res || {});
    } catch (e: any) {
      // 轻量提示，避免刷屏
      console.warn('dashboard metrics error', e?.response?.data || e?.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setProfile(getProfile());
    setCurrentStore(getCurrentStoreId());
    load();
    // 60s 轮询，隐藏时暂停
    const start = () => {
      if (timerRef.current) return;
      timerRef.current = setInterval(load, 60000);
    };
    const stop = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
    const onVis = () => {
      if (document.hidden) stop();
      else start();
    };
    start();
    document.addEventListener('visibilitychange', onVis);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchStore = async () => {
    if (!profile || profile.stores.length <= 1) return;
    const result = await Dialog.show({
      title: '切换门店',
      closeOnAction: true,
      actions: [
        profile.stores.map((s) => ({
          key: String(s.id),
          text: s.name + (s.id === currentStore ? ' ✓' : ''),
        })),
        [{ key: 'cancel', text: '取消' }],
      ],
    });
    const sid = Number((result as any) ?? 0);
    if (sid && sid !== currentStore) {
      setCurrentStoreId(sid);
      setCurrentStore(sid);
      Toast.show({ icon: 'success', content: '已切换门店' });
      load();
    }
  };

  const quick: { key: string; title: string; icon: string; path?: string; disabled?: string }[] = [
    { key: 'verify', title: '核销', icon: '✅', path: '/merchant/m/verify' },
    { key: 'orders', title: '订单', icon: '📋', path: '/merchant/m/orders' },
    { key: 'reports', title: '报表', icon: '📊', path: '/merchant/m/reports' },
    { key: 'staff', title: '员工', icon: '👥', path: '/merchant/m/staff' },
    { key: 'settlement', title: '对账', icon: '💰', path: '/merchant/m/settlement' },
    { key: 'store-settings', title: '门店', icon: '🏬', path: '/merchant/m/store-settings' },
  ];
  const visibleQuick = quick.filter((q) => canAccess(profile?.role, q.key === 'verify' ? 'verifications' : q.key));

  return (
    <PullToRefresh onRefresh={load}>
      <div style={{ padding: 0 }}>
        {/* 顶部 */}
        <div
          style={{
            background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
            color: '#fff',
            padding: '20px 16px 56px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div onClick={switchStore} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
              <span style={{ fontSize: 16, fontWeight: 600 }}>{profile?.merchant_name || '商家'}</span>
              {profile?.stores?.length ? <span style={{ opacity: 0.9, fontSize: 13 }}>· {currentStoreName}</span> : null}
              {profile && profile.stores.length > 1 && <span style={{ fontSize: 12 }}>▼</span>}
            </div>
            <div style={{ fontSize: 12, opacity: 0.9 }}>
              {profile ? roleLabel[profile.role] || profile.role : ''}
            </div>
          </div>
        </div>

        {/* 概览卡片 */}
        <div style={{ padding: '0 12px', marginTop: -36 }}>
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 16,
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 8,
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            }}
          >
            {[
              { label: '今日订单', value: metrics.today_orders ?? 0, color: '#1677ff' },
              { label: '今日核销', value: metrics.today_verifications ?? 0, color: '#52c41a' },
              { label: '今日营业额', value: `¥${Number(metrics.today_amount ?? 0).toFixed(0)}`, color: '#fa8c16' },
              { label: '待核销', value: metrics.pending_verify ?? 0, color: '#ff4d4f' },
            ].map((m) => (
              <div key={m.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{m.value}</div>
                <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>{m.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 快捷操作 */}
        <div style={{ padding: 12 }}>
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 16,
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
            }}
          >
            {visibleQuick.map((q) => (
              <div
                key={q.key}
                onClick={() => q.path && router.push(q.path)}
                style={{
                  textAlign: 'center',
                  cursor: 'pointer',
                  padding: '8px 0',
                }}
              >
                <div style={{ fontSize: 28 }}>{q.icon}</div>
                <div style={{ fontSize: 12, color: '#333', marginTop: 4 }}>{q.title}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 最近订单 */}
        <div style={{ padding: '0 12px 24px' }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: '12px 12px 4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>最近订单</div>
              <div style={{ fontSize: 12, color: '#52c41a' }} onClick={() => router.push('/merchant/m/orders')}>
                查看全部 ›
              </div>
            </div>
            {(metrics.recent_orders || []).slice(0, 5).length === 0 ? (
              <div style={{ textAlign: 'center', color: '#999', padding: '24px 0', fontSize: 13 }}>
                {loading ? '加载中...' : '暂无订单'}
              </div>
            ) : (
              (metrics.recent_orders || []).slice(0, 5).map((o: any) => (
                <div
                  key={o.order_id || o.id}
                  onClick={() => router.push(`/merchant/m/orders/${o.order_id || o.id}`)}
                  style={{
                    padding: '10px 0',
                    borderTop: '1px solid #f0f0f0',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 14,
                        color: '#333',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {o.product_name || o.title || '商品'}
                    </div>
                    <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                      {o.created_at ? new Date(o.created_at).toLocaleString('zh-CN') : ''}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: '#fa541c', fontSize: 15, fontWeight: 600 }}>
                      ¥{Number(o.amount || 0).toFixed(2)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </PullToRefresh>
  );
}
