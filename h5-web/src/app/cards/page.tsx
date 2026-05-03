'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Empty, SpinLoading } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import CardFace from '@/components/card/CardFace';
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
  face_style?: string;
  face_bg_code?: string;
  face_show_flags?: number;
  face_layout?: string;
}

function buildItemsSummary(items: CardItemRef[]): string {
  if (!items || items.length === 0) return '';
  const names = items.map((i) => i.product_name || `商品#${i.product_id}`);
  return names.slice(0, 3).join(' / ') + (names.length > 3 ? '…' : '');
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
      } catch {
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
              style={{ marginBottom: 12 }}
            >
              <CardFace
                faceStyle={c.face_style || 'ST1'}
                faceBgCode={c.face_bg_code || 'BG1'}
                faceShowFlags={c.face_show_flags ?? 7}
                cardName={c.name}
                itemsSummary={buildItemsSummary(c.items)}
                price={c.price}
                originalPrice={c.original_price ?? null}
                validDays={c.valid_days}
                cardType={c.card_type}
                totalTimes={c.total_times ?? null}
                scopeType={c.scope_type}
                size="md"
              />
              <div style={{ marginTop: 6, color: '#999', fontSize: 12, paddingLeft: 4 }}>
                已售 {c.sales_count}{c.items.length > 0 ? ` · 含 ${c.items.length} 个项目` : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
