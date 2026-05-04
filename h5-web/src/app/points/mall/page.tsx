'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Grid, Button, Tag, SpinLoading, Badge, Toast } from 'antd-mobile';

import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface MallGoods {
  id: number;
  name: string;
  description?: string | null;
  images?: string[] | null;
  type: string;
  price_points: number;
  stock: number;
  status?: string;
  goods_status?: string;
  button_state?: string;
  button_text?: string;
  is_low_stock?: boolean;
  // [BUG-2] 后端可下发的"按原因置灰"字段（兼容老接口：缺失则按原逻辑）
  can_redeem?: boolean;
  redeem_block_reason?:
    | 'OFF_SHELF'
    | 'NOT_STARTED'
    | 'ENDED'
    | 'SOLD_OUT'
    | 'LIMIT_REACHED'
    | 'INSUFFICIENT_POINTS'
    | string
    | null;
  shortage_text?: string | null;
}

// [BUG-2] redeem_block_reason → 按钮文案映射
const REDEEM_BLOCK_REASON_TEXT: Record<string, string> = {
  OFF_SHELF: '已下架',
  NOT_STARTED: '未开始',
  ENDED: '已结束',
  SOLD_OUT: '已兑完',
  LIMIT_REACHED: '已达上限',
  INSUFFICIENT_POINTS: '积分不足',
};

const TYPE_BADGE: Record<string, { text: string; color: string }> = {
  coupon: { text: '优惠券', color: '#fa8c16' },
  service: { text: '体验服务', color: '#13c2c2' },
  physical: { text: '实物', color: '#722ed1' },
  virtual: { text: '虚拟（开发中）', color: '#bfbfbf' },
  third_party: { text: '第三方（开发中）', color: '#bfbfbf' },
};

export default function PointsMallPage() {
  const router = useRouter();
  const [userPoints, setUserPoints] = useState(0);
  const [goods, setGoods] = useState<MallGoods[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'all' | 'exchangeable'>('all');
  const [hasExchangeable, setHasExchangeable] = useState(false);

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

  const loadGoods = useCallback(async (currentTab: 'all' | 'exchangeable') => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/points/mall', { params: { page: 1, page_size: 50, tab: currentTab } });
      const data = res?.data || res || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const normalized: MallGoods[] = items.map((it: any) => ({
        id: it.id,
        name: it.name,
        description: it.description,
        images: Array.isArray(it.images) ? it.images : (it.images ? [it.images] : null),
        type: (typeof it.type === 'string' ? it.type : (it.type?.value || 'virtual')),
        price_points: Number(it.price_points || 0),
        stock: Number(it.stock || 0),
        status: it.status,
        goods_status: it.goods_status,
        button_state: it.button_state,
        button_text: it.button_text,
        is_low_stock: Boolean(it.is_low_stock),
        can_redeem: typeof it.can_redeem === 'boolean' ? it.can_redeem : undefined,
        redeem_block_reason: it.redeem_block_reason ?? null,
        shortage_text: it.shortage_text ?? null,
      }));
      setGoods(normalized);
      setHasExchangeable(Boolean(data.has_exchangeable));
    } catch {
      setGoods([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshPoints();
    loadGoods(tab);
  }, [refreshPoints, loadGoods, tab]);

  const handleCardClick = (item: MallGoods) => {
    router.push(`/points/product-detail?id=${item.id}`);
  };

  const handleQuickExchange = async (e: React.MouseEvent, item: MallGoods) => {
    e.stopPropagation();
    // [BUG-2] 优先走新接口的 can_redeem 字段：
    //  - true  → 直发快速兑换流程
    //  - false → 跳转详情页，由详情页展示具体不可兑换原因（不在列表 Toast 拦截）
    //  - undefined（老接口） → 维持原 button_state 的 Toast 拦截逻辑（兼容性）
    if (typeof item.can_redeem === 'boolean') {
      if (!item.can_redeem) {
        router.push(`/points/product-detail?id=${item.id}`);
        return;
      }
      router.push(`/points/product-detail?id=${item.id}&quick=1`);
      return;
    }
    if (item.button_state === 'sold_out') {
      Toast.show({ content: '已兑完' });
      return;
    }
    if (item.button_state === 'not_enough') {
      const diff = Math.max(0, item.price_points - userPoints);
      Toast.show({ content: `积分不足，还差 ${diff} 积分` });
      return;
    }
    router.push(`/points/product-detail?id=${item.id}&quick=1`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar>积分商城</GreenNavBar>

      <div
        className="px-4 py-4 flex items-center justify-between"
        style={{ background: '#C8E6C9' }}
      >
        <div>
          <div style={{ fontSize: 12, color: '#1B5E20' }}>可用积分</div>
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

      {/* Tab 切换 */}
      <div
        className="px-4 py-3 flex items-center"
        style={{ background: '#fff', borderBottom: '1px solid #f0f0f0' }}
      >
        <div
          onClick={() => setTab('all')}
          style={{
            padding: '6px 16px',
            borderRadius: 16,
            marginRight: 12,
            fontSize: 14,
            fontWeight: tab === 'all' ? 600 : 400,
            color: tab === 'all' ? '#fff' : '#666',
            background: tab === 'all' ? '#2E7D32' : '#f5f5f5',
            cursor: 'pointer',
          }}
        >
          全部
        </div>
        <Badge content={hasExchangeable ? Badge.dot : null}>
          <div
            onClick={() => setTab('exchangeable')}
            style={{
              padding: '6px 16px',
              borderRadius: 16,
              fontSize: 14,
              fontWeight: tab === 'exchangeable' ? 600 : 400,
              color: tab === 'exchangeable' ? '#fff' : '#666',
              background: tab === 'exchangeable' ? '#2E7D32' : '#f5f5f5',
              cursor: 'pointer',
            }}
          >
            可兑换
          </div>
        </Badge>
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
              const btnState = item.button_state || 'normal';
              const isSoldOut = btnState === 'sold_out';
              const isNotEnough = btnState === 'not_enough';
              // [BUG-2] 新接口路径：使用 can_redeem + redeem_block_reason 决定按钮形态
              const hasCanRedeem = typeof item.can_redeem === 'boolean';
              const isBlocked = hasCanRedeem && item.can_redeem === false;
              let btnText = item.button_text || '立即兑换';
              if (isBlocked) {
                const reason = item.redeem_block_reason || '';
                if (reason === 'INSUFFICIENT_POINTS') {
                  btnText = item.shortage_text || '积分不足';
                } else if (reason && REDEEM_BLOCK_REASON_TEXT[reason]) {
                  btnText = REDEEM_BLOCK_REASON_TEXT[reason];
                } else {
                  btnText = item.button_text || '不可兑换';
                }
              }
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
                      {/* 库存展示：仅在紧张时（≤10）显示红字 "仅剩 X 件"；0 显示"已兑完" */}
                      {isSoldOut ? (
                        <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>已兑完</div>
                      ) : item.is_low_stock ? (
                        <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>仅剩 {item.stock} 件</div>
                      ) : (
                        <div style={{ height: 16, marginTop: 4 }} />
                      )}
                      {/* [BUG-2] 立即兑换按钮：
                          - can_redeem === true  → 实心高亮 "立即兑换"
                          - can_redeem === false → 按 reason 文案，**className 置灰但仍可点击**（跳详情查看原因）
                          - 老接口（can_redeem 缺失） → 维持原 disabled / fill 逻辑（兼容） */}
                      {hasCanRedeem ? (
                        isBlocked ? (
                          <Button
                            block
                            size="small"
                            fill="solid"
                            className="bg-gray-300 text-gray-500"
                            onClick={(e) => handleQuickExchange(e as any, item)}
                            style={{
                              marginTop: 6,
                              borderRadius: 16,
                              fontSize: 12,
                              background: '#e5e7eb',
                              color: '#6b7280',
                              border: 'none',
                            }}
                          >
                            {btnText}
                          </Button>
                        ) : (
                          <Button
                            block
                            size="small"
                            color="primary"
                            fill="solid"
                            onClick={(e) => handleQuickExchange(e as any, item)}
                            style={{
                              marginTop: 6,
                              borderRadius: 16,
                              fontSize: 12,
                            }}
                          >
                            {btnText}
                          </Button>
                        )
                      ) : (
                        <Button
                          block
                          size="small"
                          color={isSoldOut ? 'default' : 'primary'}
                          disabled={isSoldOut}
                          fill={isNotEnough ? 'outline' : 'solid'}
                          onClick={(e) => handleQuickExchange(e as any, item)}
                          style={{
                            marginTop: 6,
                            borderRadius: 16,
                            fontSize: 12,
                            ...(isSoldOut ? { background: '#f0f0f0', color: '#bfbfbf' } : {}),
                          }}
                        >
                          {btnText}
                        </Button>
                      )}
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
