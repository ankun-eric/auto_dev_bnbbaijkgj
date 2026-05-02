'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, Empty, SpinLoading, Tag, Toast } from 'antd-mobile';
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
  store_scope?: { type: string; store_ids?: number[] } | null;
  items: CardItemRef[];
  sales_count: number;
  user_has_active_card: boolean;
  nearest_expiry_days: number | null;
}

export default function CardDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [card, setCard] = useState<PublicCard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const res: any = await api.get(`/api/cards/${id}`);
        setCard(res.data || res);
      } catch (e: any) {
        Toast.show({ content: e?.response?.data?.detail || '加载失败' });
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const onBuy = () => {
    Toast.show({
      content: '购卡功能将在第 2 期开放，敬请期待',
      position: 'center',
    });
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#f5f5f7' }}>
        <GreenNavBar>卡详情</GreenNavBar>
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!card) {
    return (
      <div style={{ minHeight: '100vh', background: '#f5f5f7' }}>
        <GreenNavBar>卡详情</GreenNavBar>
        <Empty description="卡不存在或已下架" style={{ padding: 60 }} />
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f7', paddingBottom: 96 }}>
      <GreenNavBar>卡详情</GreenNavBar>

      {/* 头图 */}
      <div style={{
        background: card.cover_image
          ? `url(${card.cover_image}) center/cover`
          : 'linear-gradient(135deg,#9333ea,#6366f1)',
        height: 200, position: 'relative',
      }}>
        {!card.cover_image && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 48,
          }}>{card.name}</div>
        )}
      </div>

      {/* 基本信息 */}
      <div style={{ background: '#fff', padding: 16, marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <Tag color="primary" style={{ background: '#f0e6ff', color: '#7c3aed' }}>
            {card.card_type === 'times' ? '次卡' : '时卡'}
          </Tag>
          {card.scope_type === 'merchant' ? <Tag color="warning">商家专属</Tag> : <Tag color="success">平台通用</Tag>}
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>{card.name}</div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{ color: '#f5222d', fontSize: 26, fontWeight: 700 }}>
            ¥{Number(card.price).toFixed(0)}
          </span>
          {card.original_price ? (
            <span style={{ color: '#999', textDecoration: 'line-through', fontSize: 14 }}>
              ¥{Number(card.original_price).toFixed(0)}
            </span>
          ) : null}
          <span style={{ marginLeft: 'auto', color: '#999', fontSize: 12 }}>已售 {card.sales_count}</span>
        </div>
        <div style={{ color: '#666', fontSize: 13, marginTop: 6 }}>
          {card.card_type === 'times' ? `共 ${card.total_times} 次` : '时卡'}
          ·  自购买起 {card.valid_days} 天内有效
          {card.frequency_limit ? ` · 每${card.frequency_limit.scope === 'day' ? '天' : '周'}限 ${card.frequency_limit.times} 次` : ''}
        </div>

        {card.user_has_active_card ? (
          <div style={{
            marginTop: 12, padding: 10, background: '#fffbe6',
            borderRadius: 8, border: '1px solid #ffe58f', color: '#ad6800', fontSize: 13,
          }}>
            您已持有此卡{card.nearest_expiry_days !== null ? `（剩余 ${card.nearest_expiry_days} 天到期）` : ''}
            {card.nearest_expiry_days !== null && card.nearest_expiry_days <= 7 ? '，可到期续卡' : '，请到"我的卡包"查看使用'}
          </div>
        ) : null}
      </div>

      {/* 描述 */}
      {card.description ? (
        <div style={{ background: '#fff', padding: 16, marginBottom: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>卡介绍</div>
          <div style={{ color: '#444', fontSize: 14, whiteSpace: 'pre-wrap' }}>{card.description}</div>
        </div>
      ) : null}

      {/* 可用项目 */}
      <div style={{ background: '#fff', padding: 16, marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>可用项目（{card.items.length}）</div>
        {card.items.length === 0 ? (
          <div style={{ color: '#999', fontSize: 14 }}>该卡暂未绑定项目</div>
        ) : (
          <div>
            {card.items.map((it) => (
              <div
                key={it.product_id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 0', borderBottom: '1px solid #f0f0f0',
                }}
              >
                {it.product_image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={it.product_image} alt={it.product_name}
                    style={{ width: 48, height: 48, borderRadius: 8, objectFit: 'cover' }} />
                ) : (
                  <div style={{
                    width: 48, height: 48, borderRadius: 8, background: '#f0f0f0',
                  }} />
                )}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, color: '#222' }}>{it.product_name || `商品#${it.product_id}`}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 规则 */}
      <div style={{ background: '#fff', padding: 16, marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>使用规则</div>
        <ul style={{ margin: 0, paddingLeft: 20, color: '#444', fontSize: 13, lineHeight: 1.8 }}>
          <li>本卡自购买成功起算，{card.valid_days} 天内有效</li>
          <li>核销时由门店扫码二次确认，60 秒内有效</li>
          <li>本卡不参与营销活动叠加（仅享售价/划线价优惠）</li>
          {card.store_scope?.type === 'list' ? (
            <li>仅限指定门店核销</li>
          ) : (
            <li>所有签约门店通用核销</li>
          )}
          <li>退款规则：未使用全额退；已使用次数不退</li>
        </ul>
      </div>

      {/* 底部操作栏 */}
      <div style={{
        position: 'fixed', left: 0, right: 0, bottom: 0,
        background: '#fff', padding: 12, borderTop: '1px solid #eee',
        display: 'flex', gap: 10,
      }}>
        <Button onClick={() => router.push('/cards/wallet')} style={{ flex: 1 }}>
          我的卡包
        </Button>
        <Button color="primary" style={{ flex: 2 }} onClick={onBuy}>
          立即购卡（¥{Number(card.price).toFixed(0)}）
        </Button>
      </div>
    </div>
  );
}
