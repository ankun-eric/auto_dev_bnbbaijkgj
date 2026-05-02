'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Empty, SpinLoading, Tag } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface CardItemRef {
  product_id: number;
  product_name?: string;
  product_image?: string;
}

interface PublicCard {
  id: number;
  name: string;
  cover_image?: string | null;
  description?: string | null;
  card_type: 'times' | 'period';
  scope_type: 'platform' | 'merchant';
  price: number;
  original_price?: number | null;
  total_times?: number | null;
  valid_days: number;
  frequency_limit?: { scope: string; times: number } | null;
  items: CardItemRef[];
  sales_count: number;
}

export default function CardsListPage() {
  const router = useRouter();
  const [cards, setCards] = useState<PublicCard[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get('/api/cards', { params: { page: 1, page_size: 50 } });
        const data = res.data || res;
        setCards(data.items || []);
      } catch (e) {
        // 静默
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f7', paddingBottom: 32 }}>
      <GreenNavBar>卡专区</GreenNavBar>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <SpinLoading color="primary" />
        </div>
      ) : cards.length === 0 ? (
        <Empty description="暂无可购买的卡" style={{ padding: 60 }} />
      ) : (
        <div style={{ padding: 12 }}>
          {cards.map((c) => (
            <div
              key={c.id}
              onClick={() => router.push(`/cards/${c.id}`)}
              style={{
                background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12,
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              }}
            >
              <div style={{ display: 'flex', gap: 12 }}>
                {c.cover_image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.cover_image} alt={c.name} style={{
                    width: 90, height: 90, borderRadius: 10, objectFit: 'cover',
                  }} />
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
                      {c.card_type === 'times' ? '次卡' : '时卡'}
                    </Tag>
                    {c.scope_type === 'merchant' ? <Tag color="warning">商家专属</Tag> : <Tag color="success">平台通用</Tag>}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, color: '#111' }}>
                    {c.name}
                  </div>
                  <div style={{ color: '#666', fontSize: 12, marginTop: 2 }}>
                    {c.card_type === 'times' ? `${c.total_times} 次 · ${c.valid_days} 天有效` : `${c.valid_days} 天 · 时卡`}
                    {c.items.length > 0 ? ` · 含 ${c.items.length} 个项目` : ''}
                  </div>
                  <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <span style={{ color: '#f5222d', fontSize: 20, fontWeight: 700 }}>
                      ¥{Number(c.price).toFixed(0)}
                    </span>
                    {c.original_price ? (
                      <span style={{ color: '#999', textDecoration: 'line-through', fontSize: 12 }}>
                        ¥{Number(c.original_price).toFixed(0)}
                      </span>
                    ) : null}
                    <span style={{ marginLeft: 'auto', color: '#999', fontSize: 12 }}>
                      已售 {c.sales_count}
                    </span>
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
