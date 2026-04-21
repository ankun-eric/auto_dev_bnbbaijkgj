'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Grid, Button, Tag, SpinLoading } from 'antd-mobile';

import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface MallGoods {
  id: number;
  name: string;
  description?: string | null;
  images?: string[] | null;
  type: string; // coupon/service/virtual/physical/third_party
  price_points: number;
  stock: number;
  status?: string;
}

const TYPE_BADGE: Record<string, { text: string; color: string }> = {
  coupon: { text: '优惠券', color: '#fa8c16' },
  service: { text: '体验服务', color: '#13c2c2' },
  physical: { text: '实物', color: '#722ed1' },
  virtual: { text: '虚拟（开发中）', color: '#bfbfbf' },
  third_party: { text: '第三方（开发中）', color: '#bfbfbf' },
};

const DEV_TYPES = new Set(['virtual', 'third_party']);

export default function PointsMallPage() {
  const router = useRouter();
  const [userPoints, setUserPoints] = useState(0);
  const [goods, setGoods] = useState<MallGoods[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshPoints = useCallback(async () => {
    try {
      const res: any = await api.get('/api/points/summary');
      const data = res?.data || res || {};
      const pts = data.available_points ?? data.total_points ?? 0;
      setUserPoints(Number(pts) || 0);
    } catch {
      // ignore
    }
  }, []);

  const loadGoods = useCallback(async () => {
    try {
      const res: any = await api.get('/api/points/mall', { params: { page: 1, page_size: 50 } });
      const data = res?.data || res || {};
      const items = Array.isArray(data.items) ? data.items : [];
      // 兼容后端字段：type / price_points
      const normalized: MallGoods[] = items.map((it: any) => ({
        id: it.id,
        name: it.name,
        description: it.description,
        images: Array.isArray(it.images) ? it.images : (it.images ? [it.images] : null),
        type: (typeof it.type === 'string' ? it.type : (it.type?.value || 'virtual')),
        price_points: Number(it.price_points || 0),
        stock: Number(it.stock || 0),
        status: it.status,
      }));
      setGoods(normalized);
    } catch {
      setGoods([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshPoints();
    loadGoods();
  }, [refreshPoints, loadGoods]);

  // PRD F4：卡片整体可点跳到商品详情页，不再在列表上直接兑换
  const handleCardClick = (item: MallGoods) => {
    router.push(`/points/product-detail?id=${item.id}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar>积分商城</GreenNavBar>

      {/* v3 配色：统计区统一 #C8E6C9（浅绿） */}
      <div
        className="px-4 py-4 flex items-center justify-between"
        style={{ background: '#C8E6C9' }}
      >
        <div>
          <div style={{ fontSize: 12, color: '#1B5E20' }}>可用积分</div>
          {/* v3：删除数字右边的 ⭐ */}
          <div
            style={{
              fontSize: 26,
              fontWeight: 'bold',
              color: '#1B5E20',
              lineHeight: 1.2,
              marginTop: 2,
            }}
          >
            {userPoints}
          </div>
          <div style={{ fontSize: 12, color: '#2E7D32', marginTop: 2 }}>
            用积分兑换好礼
          </div>
        </div>
        <Button
          size="small"
          onClick={() => router.push('/points/detail?tab=exchange')}
          style={{
            background: 'rgba(27, 94, 32, 0.15)',
            color: '#1B5E20',
            border: '1px solid rgba(27, 94, 32, 0.35)',
            borderRadius: 16,
          }}
        >
          兑换记录
        </Button>
      </div>

      <div className="px-4 pt-4 pb-8">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <SpinLoading color="primary" />
          </div>
        ) : goods.length === 0 ? (
          <div className="text-center text-gray-400 py-10">暂无商品</div>
        ) : (
          <Grid columns={2} gap={12}>
            {goods.map((item) => {
              const badge = TYPE_BADGE[item.type] || TYPE_BADGE.virtual;
              const img = item.images?.[0];
              return (
                <Grid.Item key={item.id}>
                  <Card
                    style={{ borderRadius: 12, cursor: 'pointer' }}
                    onClick={() => handleCardClick(item)}
                  >
                    <div className="text-center">
                      <div style={{ minHeight: 48 }} className="mb-2">
                        {img ? (
                          <img
                            src={img}
                            alt={item.name}
                            style={{ maxHeight: 64, margin: '0 auto' }}
                          />
                        ) : (
                          <div className="text-4xl">🎁</div>
                        )}
                      </div>
                      <div style={{ marginBottom: 4 }}>
                        <Tag
                          color={badge.color}
                          style={{ fontSize: 10, '--border-radius': '8px' } as any}
                        >
                          {badge.text}
                        </Tag>
                      </div>
                      <div className="text-sm font-medium" style={{ minHeight: 40 }}>
                        {item.name}
                      </div>
                      <div
                        className="font-bold mt-1"
                        style={{ color: '#2E7D32' }}
                      >
                        {item.price_points} 积分
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        {item.type === 'service' ? '服务券' : `库存 ${item.stock}`}
                      </div>
                    </div>
                  </Card>
                </Grid.Item>
              );
            })}
          </Grid>
        )}
      </div>
    </div>
  );
}
