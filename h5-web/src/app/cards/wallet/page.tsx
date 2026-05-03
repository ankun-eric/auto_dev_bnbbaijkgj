'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Empty, SpinLoading, Tabs, Tag } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import CardFace from '@/components/card/CardFace';
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
  face_style?: string;
  face_bg_code?: string;
  face_show_flags?: number;
  face_layout?: string;
  price?: number | null;
  original_price?: number | null;
  description?: string | null;
}

const TABS = [
  { key: 'all', title: '全部' },
  { key: 'unused', title: '未使用' },
  { key: 'in_use', title: '使用中' },
  { key: 'expired', title: '已过期' },
];

function buildItemsSummary(items: { product_id: number; product_name?: string }[]): string {
  if (!items || items.length === 0) return '';
  const names = items.map((i) => i.product_name || `商品#${i.product_id}`);
  return names.slice(0, 3).join(' / ') + (names.length > 3 ? '…' : '');
}

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
          {items.map((it) => {
            const dimmed = it.status === 'expired' || it.status === 'refunded';
            return (
              <div
                key={it.id}
                onClick={() => router.push(`/cards/${it.card_definition_id}`)}
                style={{ marginBottom: 12, opacity: dimmed ? 0.55 : 1 }}
              >
                <CardFace
                  faceStyle={it.face_style || 'ST1'}
                  faceBgCode={it.face_bg_code || 'BG1'}
                  faceShowFlags={it.face_show_flags ?? 7}
                  cardName={it.card_name}
                  itemsSummary={buildItemsSummary(it.bound_items)}
                  price={it.price ?? null}
                  originalPrice={it.original_price ?? null}
                  validDays={null}
                  cardType={it.card_type}
                  totalTimes={it.total_times ?? null}
                  remainingTimes={it.remaining_times ?? null}
                  daysToExpire={it.status === 'active' ? (it.days_to_expire ?? null) : null}
                  scopeType={it.scope_type}
                  size="sm"
                />
                <div style={{ marginTop: 6, paddingLeft: 4, fontSize: 12, color: '#999', display: 'flex', gap: 8 }}>
                  {it.status === 'expired' ? <Tag color="danger">已过期</Tag>
                    : it.status === 'used_up' ? <Tag color="default">用完</Tag>
                    : it.status === 'refunded' ? <Tag color="default">已退款</Tag>
                    : <Tag color="success">使用中</Tag>}
                  <span>有效期至 {new Date(it.valid_to).toLocaleDateString()}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
