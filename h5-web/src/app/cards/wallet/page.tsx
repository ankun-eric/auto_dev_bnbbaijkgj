'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Empty, SpinLoading, Tabs, Tag } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface UserCard {
  id: number;
  card_definition_id: number;
  card_name: string;
  cover_image?: string | null;
  card_type: 'times' | 'period';
  scope_type: 'platform' | 'merchant';
  bound_items: { product_id: number; product_name?: string }[];
  remaining_times?: number | null;
  total_times?: number | null;
  valid_from: string;
  valid_to: string;
  status: 'active' | 'used_up' | 'expired' | 'refunded';
  days_to_expire?: number | null;
}

const TABS = [
  { key: 'all', title: '全部' },
  { key: 'unused', title: '未使用' },
  { key: 'in_use', title: '使用中' },
  { key: 'expired', title: '已过期' },
];

export default function CardWalletPage() {
  const router = useRouter();
  const [tab, setTab] = useState<string>('all');
  const [items, setItems] = useState<UserCard[]>([]);
  const [counts, setCounts] = useState({ unused: 0, in_use: 0, expired: 0 });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (tab === 'unused' || tab === 'in_use') params.status = 'active';
      else if (tab === 'expired') params.status = 'expired';
      const res: any = await api.get('/api/cards/me/wallet', { params });
      const data = res.data || res;
      let list: UserCard[] = data.items || [];
      if (tab === 'unused') {
        list = list.filter((it) =>
          it.card_type === 'times' && it.remaining_times === it.total_times,
        );
      } else if (tab === 'in_use') {
        list = list.filter(
          (it) => it.card_type === 'period' || (it.remaining_times !== it.total_times),
        );
      }
      setItems(list);
      setCounts({
        unused: data.unused_count || 0,
        in_use: data.in_use_count || 0,
        expired: data.expired_count || 0,
      });
    } catch (e: any) {
      // 401 已由 interceptor 处理
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f7', paddingBottom: 32 }}>
      <GreenNavBar>我的卡包</GreenNavBar>

      <Tabs activeKey={tab} onChange={setTab}>
        {TABS.map((t) => {
          const cnt =
            t.key === 'unused' ? counts.unused
            : t.key === 'in_use' ? counts.in_use
            : t.key === 'expired' ? counts.expired
            : null;
          return (
            <Tabs.Tab
              key={t.key}
              title={cnt !== null ? `${t.title}(${cnt})` : t.title}
            />
          );
        })}
      </Tabs>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <SpinLoading color="primary" />
        </div>
      ) : items.length === 0 ? (
        <Empty description="暂无卡片" style={{ padding: 60 }} />
      ) : (
        <div style={{ padding: 12 }}>
          {items.map((it) => (
            <div
              key={it.id}
              onClick={() => router.push(`/cards/${it.card_definition_id}`)}
              style={{
                background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12,
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                opacity: it.status === 'expired' || it.status === 'refunded' ? 0.6 : 1,
              }}
            >
              <div style={{ display: 'flex', gap: 12 }}>
                {it.cover_image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={it.cover_image} alt={it.card_name}
                    style={{ width: 90, height: 90, borderRadius: 10, objectFit: 'cover' }} />
                ) : (
                  <div style={{
                    width: 90, height: 90, borderRadius: 10,
                    background: 'linear-gradient(135deg,#9333ea,#6366f1)',
                    color: '#fff', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: 28,
                  }}>卡</div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <Tag color="primary" style={{ background: '#f0e6ff', color: '#7c3aed' }}>
                      {it.card_type === 'times' ? '次卡' : '时卡'}
                    </Tag>
                    {it.status === 'expired' ? <Tag color="danger">已过期</Tag>
                      : it.status === 'used_up' ? <Tag color="default">用完</Tag>
                      : it.status === 'refunded' ? <Tag color="default">已退款</Tag>
                      : <Tag color="success">使用中</Tag>}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, color: '#111' }}>
                    {it.card_name}
                  </div>
                  <div style={{ color: '#666', fontSize: 12, marginTop: 2 }}>
                    {it.card_type === 'times'
                      ? `剩余 ${it.remaining_times ?? 0} / ${it.total_times ?? 0} 次`
                      : '时卡'}
                    {it.bound_items.length > 0 ? ` · 含 ${it.bound_items.length} 个项目` : ''}
                  </div>
                  <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                    有效期至 {new Date(it.valid_to).toLocaleDateString()}
                    {it.days_to_expire !== null && it.days_to_expire !== undefined && it.status === 'active'
                      ? ` · 剩 ${it.days_to_expire} 天`
                      : ''}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
