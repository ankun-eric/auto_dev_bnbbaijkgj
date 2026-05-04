'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Tag, Button, Empty, SpinLoading, InfiniteScroll, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { jumpToUseCoupon } from '@/lib/coupon';

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
  ref_coupon_id?: number | null;
  ref_user_coupon_id?: number | null;
  ref_service_type?: string | null;
  ref_service_id?: number | null;
  ref_order_no?: string | null;
  use_button_state?: string;
  use_button_text?: string;
  use_button_target?: string | null;
  // [OPT-4] 后端返回的优惠券维度状态（'available' / 'used' / 'expired' 等），用于决定是否展示"去使用"
  coupon_id?: number | null;
  coupon_status?: string | null;
}

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

// [OPT-2/OPT-3] 用户可见文案中"free_trial / 免费试用" → "免费体验券 / 免费体验"
function localizeText(text: string | null | undefined): string {
  if (!text) return '';
  return String(text)
    .replace(/free_trial/gi, '免费体验券')
    .replace(/免费试用/g, '免费体验');
}

const SERVICE_ROUTE: Record<string, (id: number) => string> = {
  expert: (id) => `/expert/${id}`,
  physical_exam: (id) => `/physical-exam/${id}`,
  tcm: (id) => `/tcm/${id}`,
  health_plan: (id) => `/health-plan/${id}`,
};

export default function PointsExchangeRecordsPage() {
  const router = useRouter();
  const [items, setItems] = useState<ExchangeRecord[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);

  const loadPage = useCallback(async (p: number) => {
    try {
      const res: any = await api.get('/api/points/exchange-records', {
        params: { page: p, page_size: 20 },
      });
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

  useEffect(() => {
    loadPage(1);
  }, [loadPage]);

  const handleAppointment = (r: ExchangeRecord) => {
    if (r.status === 'expired') {
      Toast.show({ content: '该服务券已过期' });
      return;
    }
    const fn = r.ref_service_type && SERVICE_ROUTE[r.ref_service_type];
    if (fn && r.ref_service_id) {
      router.push(fn(r.ref_service_id));
    } else {
      Toast.show({ content: '暂无对应预约入口' });
    }
  };

  const handleViewCoupon = () => {
    router.push('/my-coupons?tab=available');
  };

  const handleViewOrder = (r: ExchangeRecord) => {
    if (r.ref_order_no) {
      router.push('/unified-orders');
    }
  };

  // v1.1 使用按钮：优先走替代款智能跳转；已下架无替代时禁用
  const handleUseButton = (r: ExchangeRecord) => {
    const state = r.use_button_state || 'normal';
    if (state === 'offline') {
      Toast.show({ content: '该商品已下架' });
      return;
    }
    if (state === 'redirect_replaced' && r.use_button_target) {
      router.push(r.use_button_target);
      return;
    }
    // 正常：按商品类型分发原流程
    if (r.goods_type === 'service') {
      handleAppointment(r);
    } else if (r.goods_type === 'coupon') {
      handleViewCoupon();
    } else if (r.goods_type === 'physical') {
      handleViewOrder(r);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-8">
      <GreenNavBar>兑换记录</GreenNavBar>

      <div style={{ background: '#C8E6C9' }} className="px-4 py-3">
        <div style={{ color: '#1B5E20', fontSize: 13, fontWeight: 600 }}>
          我的兑换记录
        </div>
        <div style={{ color: '#2E7D32', fontSize: 12, marginTop: 2 }}>
          优惠券、体验服务、实物兑换均在此处查看
        </div>
      </div>

      <div className="px-4 pt-3">
        {loading && items.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            <SpinLoading color="primary" />
          </div>
        ) : items.length === 0 ? (
          <Empty description="暂无兑换记录" />
        ) : (
          <div className="space-y-3">
            {items.map((r) => {
              const meta = TYPE_META[r.goods_type] || TYPE_META.virtual;
              const sm = STATUS_META[r.status] || { text: r.status, color: '#666' };
              return (
                <Card key={r.id} style={{ borderRadius: 10 }}>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ width: 56, height: 56, background: '#f5f5f5', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {r.goods_image ? (
                        <img
                          src={r.goods_image}
                          alt={r.goods_name}
                          style={{ maxWidth: '100%', maxHeight: '100%' }}
                        />
                      ) : (
                        <span style={{ fontSize: 28 }}>
                          {r.goods_type === 'coupon' ? '🎫' : r.goods_type === 'service' ? '💆' : '📦'}
                        </span>
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Tag color={meta.color} style={{ fontSize: 10 }}>
                          {meta.text}
                        </Tag>
                        <Tag color={sm.color} fill="outline" style={{ fontSize: 10 }}>
                          {sm.text}
                        </Tag>
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 500, marginTop: 4 }} className="truncate">
                        {localizeText(r.goods_name)}
                      </div>
                      <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
                        兑换时间：{fmt(r.exchange_time)}
                      </div>
                      {r.expire_at && (
                        <div style={{ fontSize: 12, color: '#fa8c16', marginTop: 2 }}>
                          有效期至：{fmt(r.expire_at)}
                        </div>
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                        <span style={{ color: '#B8860B', fontWeight: 600 }}>
                          -{r.points_cost} 积分
                        </span>
                        {r.goods_type === 'coupon' ? (
                          // [OPT-4] 优惠券记录：拆为【查看券】（始终）+【去使用】（仅 coupon_status==='available'）
                          (() => {
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
                          })()
                        ) : (
                          (() => {
                            const useState = r.use_button_state || 'normal';
                            const offline = useState === 'offline';
                            const replaced = useState === 'redirect_replaced';
                            let text = r.use_button_text || '';
                            if (!text || text === '立即使用') {
                              text = r.goods_type === 'service' ? '去预约' : r.goods_type === 'physical' ? '查看订单' : '立即使用';
                            }
                            if (replaced) text = r.use_button_text || '去看替代款';
                            if (offline) text = r.use_button_text || '已下架';
                            return (
                              <Button
                                size="mini"
                                disabled={offline}
                                onClick={() => handleUseButton(r)}
                                style={{
                                  borderRadius: 12,
                                  background: offline
                                    ? '#f0f0f0'
                                    : replaced
                                    ? 'linear-gradient(135deg, #fa8c16, #faad14)'
                                    : r.goods_type === 'service'
                                    ? 'linear-gradient(135deg, #52c41a, #13c2c2)'
                                    : 'rgba(114, 46, 209, 0.1)',
                                  color: offline
                                    ? '#bfbfbf'
                                    : replaced
                                    ? '#fff'
                                    : r.goods_type === 'service'
                                    ? '#fff'
                                    : '#722ed1',
                                  border: offline
                                    ? 'none'
                                    : replaced || r.goods_type === 'service'
                                    ? 'none'
                                    : '1px solid #722ed1',
                                  fontSize: 12,
                                }}
                              >
                                {text}
                              </Button>
                            );
                          })()
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        <InfiniteScroll loadMore={async () => loadPage(page)} hasMore={hasMore} />
      </div>
    </div>
  );
}
