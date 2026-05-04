'use client';

/**
 * v3.1 — 积分明细聚合页（PRD F3）
 *
 * 合并了原来的「积分详情」+「兑换记录」两个入口，提供两 Tab：
 *  - 积分明细（复用 /points/records 的数据源 /api/points/records）
 *  - 兑换记录（复用 /api/points/exchange-records）
 *
 * 路由参数：?tab=exchange 直接激活兑换记录 Tab。
 */

import { useCallback, useEffect, useMemo, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, List, InfiniteScroll, Empty, SpinLoading, Card, Tag, Button, Toast } from 'antd-mobile';

export const dynamic = 'force-dynamic';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { jumpToUseCoupon } from '@/lib/coupon';

interface PointsRecord {
  id: number;
  points: number;
  type: string;
  description?: string;
  created_at: string;
}

interface ExchangeRecord {
  id: number;
  order_no: string;
  goods_id: number;
  goods_type: string;
  goods_name: string;
  goods_image?: string | null;
  points_cost: number;
  quantity: number;
  status: string;
  exchange_time?: string | null;
  expire_at?: string | null;
  used_at?: string | null;
  ref_service_id?: number | null;
  ref_order_no?: string | null;
  coupon_id?: number | string | null;
  ref_coupon_id?: number | string | null;
  ref_user_coupon_id?: number | string | null;
  coupon_status?: string | null;
}

const TYPE_LABEL: Record<string, string> = {
  signin: '每日签到',
  checkin: '健康打卡',
  completeProfile: '完善档案',
  invite: '邀请奖励',
  firstOrder: '首次下单',
  reviewService: '订单评价',
  exchange: '积分兑换',
  consume: '积分消费',
  redeem: '积分兑换',
  task: '任务奖励',
  purchase: '购物奖励',
};

const TYPE_META: Record<string, { text: string; color: string }> = {
  coupon: { text: '优惠券', color: '#fa8c16' },
  service: { text: '体验服务', color: '#13c2c2' },
  physical: { text: '实物', color: '#722ed1' },
  virtual: { text: '虚拟', color: '#bfbfbf' },
  third_party: { text: '第三方', color: '#bfbfbf' },
};

const STATUS_META: Record<string, { text: string; color: string }> = {
  success: { text: '兑换成功', color: '#52c41a' },
  pending: { text: '处理中', color: '#1890ff' },
  failed: { text: '失败', color: '#ff4d4f' },
  used: { text: '已使用', color: '#8c8c8c' },
  expired: { text: '已过期', color: '#bfbfbf' },
  cancelled: { text: '已取消', color: '#bfbfbf' },
};

function fmt(dt?: string | null) {
  if (!dt) return '';
  try {
    return new Date(dt).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return dt;
  }
}

// ──────────── 子组件：积分明细 Tab ────────────
function PointsRecordsTab() {
  const [records, setRecords] = useState<PointsRecord[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const loadMore = useCallback(async () => {
    try {
      const res: any = await api.get('/api/points/records', { params: { page, page_size: 20 } });
      const data = res?.data || res || {};
      const items: PointsRecord[] = data?.records || data?.items || [];
      setRecords((prev) => (page === 1 ? items : [...prev, ...items]));
      setHasMore(items.length >= 20);
      setPage((p) => p + 1);
    } catch {
      setHasMore(false);
    }
  }, [page]);

  useEffect(() => {
    loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (records.length === 0 && !hasMore) {
    return <Empty description="暂无积分记录" style={{ marginTop: 60 }} />;
  }

  return (
    <>
      <List style={{ background: '#fff' }}>
        {records.map((r) => (
          <List.Item
            key={r.id}
            extra={
              <span style={{ color: r.points >= 0 ? '#4CAF50' : '#F44336', fontWeight: 600 }}>
                {r.points >= 0 ? '+' : ''}{r.points}
              </span>
            }
            description={r.created_at?.replace('T', ' ').slice(0, 19)}
          >
            <span>{r.description || TYPE_LABEL[r.type] || r.type}</span>
          </List.Item>
        ))}
      </List>
      <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
    </>
  );
}

// ──────────── 子组件：兑换记录 Tab ────────────
function ExchangeRecordsTab() {
  const router = useRouter();
  const [items, setItems] = useState<ExchangeRecord[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);

  const loadPage = useCallback(async (p: number) => {
    try {
      const res: any = await api.get('/api/points/exchange-records', { params: { page: p, page_size: 20 } });
      const data = res?.data || res || {};
      const list: ExchangeRecord[] = Array.isArray(data.items) ? data.items : [];
      setItems((prev) => (p === 1 ? list : [...prev, ...list]));
      const total = Number(data.total || 0);
      const loaded = (p - 1) * 20 + list.length;
      setHasMore(loaded < total && list.length > 0);
      setPage(p + 1);
    } catch {
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPage(1); }, [loadPage]);

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center justify-center py-10">
        <SpinLoading color="primary" />
      </div>
    );
  }

  if (!loading && items.length === 0) {
    return <Empty description="暂无兑换记录" />;
  }

  return (
    <div className="px-4 pt-3">
      <div className="space-y-3">
        {items.map((r) => {
          const meta = TYPE_META[r.goods_type] || TYPE_META.virtual;
          const sm = STATUS_META[r.status] || { text: r.status, color: '#666' };
          return (
            <Card key={r.id} style={{ borderRadius: 10 }}>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 56, height: 56, background: '#f5f5f5', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {r.goods_image ? (
                    <img src={r.goods_image} alt={r.goods_name} style={{ maxWidth: '100%', maxHeight: '100%' }} />
                  ) : (
                    <span style={{ fontSize: 28 }}>
                      {r.goods_type === 'coupon' ? '🎫' : r.goods_type === 'service' ? '💆' : '📦'}
                    </span>
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Tag color={meta.color} style={{ fontSize: 10 }}>{meta.text}</Tag>
                    <Tag color={sm.color} fill="outline" style={{ fontSize: 10 }}>{sm.text}</Tag>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 500, marginTop: 4 }} className="truncate">
                    {r.goods_name}
                  </div>
                  <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>兑换时间：{fmt(r.exchange_time)}</div>
                  {r.expire_at && (
                    <div style={{ fontSize: 12, color: '#fa8c16', marginTop: 2 }}>有效期至：{fmt(r.expire_at)}</div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                    <span style={{ color: '#F44336', fontWeight: 600 }}>-{r.points_cost} 积分</span>
                    {r.goods_type === 'service' && r.ref_service_id && r.status !== 'expired' && (
                      <Button
                        size="mini"
                        onClick={() => router.push(`/product-detail/${r.ref_service_id}`)}
                        style={{ borderRadius: 12, background: '#4CAF50', color: '#fff', border: 'none', fontSize: 12 }}
                      >
                        去使用
                      </Button>
                    )}
                    {r.goods_type === 'coupon' && (() => {
                      const couponId = r.coupon_id || r.ref_coupon_id;
                      const ucId = r.ref_user_coupon_id;
                      const canUse = (r.coupon_status === 'available')
                        || (!r.coupon_status && r.status === 'success');
                      return (
                        <div style={{ display: 'flex', gap: 8 }}>
                          <Button
                            size="mini"
                            fill="outline"
                            onClick={() => {
                              if (couponId) {
                                router.push(`/my-coupons?tab=available&highlightCouponId=${couponId}`);
                              } else {
                                router.push('/my-coupons?tab=available');
                              }
                            }}
                            style={{
                              borderRadius: 12,
                              fontSize: 12,
                              color: '#fa8c16',
                              border: '1px solid #fa8c16',
                              background: '#fff',
                            }}
                          >
                            查看券
                          </Button>
                          {canUse && (
                            <Button
                              size="mini"
                              fill="solid"
                              onClick={() => {
                                if (ucId) {
                                  jumpToUseCoupon(router, ucId);
                                } else {
                                  Toast.show({ content: '券信息缺失，无法跳转' });
                                }
                              }}
                              style={{
                                borderRadius: 12,
                                fontSize: 12,
                                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                                color: '#fff',
                                border: 'none',
                              }}
                            >
                              去使用
                            </Button>
                          )}
                        </div>
                      );
                    })()}
                    {r.goods_type === 'physical' && r.ref_order_no && (
                      <Button
                        size="mini"
                        onClick={() => router.push('/unified-orders')}
                        style={{ borderRadius: 12, background: 'rgba(114,46,209,0.1)', color: '#722ed1', border: '1px solid #722ed1', fontSize: 12 }}
                      >
                        查看订单
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
      <InfiniteScroll loadMore={async () => loadPage(page)} hasMore={hasMore} />
    </div>
  );
}

function PointsDetailInner() {
  const searchParams = useSearchParams();
  const initialTab = searchParams?.get('tab') === 'exchange' ? 'exchange' : 'detail';
  const [activeKey, setActiveKey] = useState<string>(initialTab);

  useEffect(() => {
    const t = searchParams?.get('tab');
    if (t === 'exchange' || t === 'detail') setActiveKey(t);
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-gray-50 pb-6">
      <GreenNavBar>积分明细</GreenNavBar>
      <Tabs activeKey={activeKey} onChange={setActiveKey}>
        <Tabs.Tab title="积分明细" key="detail">
          <PointsRecordsTab />
        </Tabs.Tab>
        <Tabs.Tab title="兑换记录" key="exchange">
          <ExchangeRecordsTab />
        </Tabs.Tab>
      </Tabs>
    </div>
  );
}

export default function PointsDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <PointsDetailInner />
    </Suspense>
  );
}
