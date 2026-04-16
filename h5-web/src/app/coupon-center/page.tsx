'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, Tag, Empty, SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';

interface Coupon {
  id: number;
  name: string;
  type: string;
  condition_amount: number;
  discount_value: number;
  discount_rate: number;
  total_count: number;
  claimed_count: number;
  valid_start: string | null;
  valid_end: string | null;
  status: string;
}

export default function CouponCenterPage() {
  const router = useRouter();
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [claimingIds, setClaimingIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    api.get('/api/coupons/available').then((res: any) => {
      const data = res.data || res;
      setCoupons(data.items || data || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleClaim = async (couponId: number) => {
    setClaimingIds((prev) => new Set(prev).add(couponId));
    try {
      await api.post('/api/coupons/claim', { coupon_id: couponId });
      Toast.show({ content: '领取成功', icon: 'success' });
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '领取失败' });
    } finally {
      setClaimingIds((prev) => {
        const next = new Set(prev);
        next.delete(couponId);
        return next;
      });
    }
  };

  const getCouponValue = (coupon: Coupon) => {
    if (coupon.type === 'discount') {
      return `${(coupon.discount_rate * 10).toFixed(1)}折`;
    }
    return `¥${coupon.discount_value}`;
  };

  const getCouponTypeLabel = (type: string) => {
    const map: Record<string, string> = { full_reduction: '满减', discount: '折扣', voucher: '代金券' };
    return map[type] || type;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        领券中心
      </NavBar>

      <div
        className="px-4 py-4"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="text-white text-lg font-bold">优惠券等你来领</div>
        <div className="text-white/70 text-xs mt-1">领取优惠券，享受更多折扣</div>
      </div>

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : coupons.length === 0 ? (
          <Empty description="暂无可领取的优惠券" style={{ padding: '80px 0' }} />
        ) : (
          coupons.map((coupon) => {
            const remaining = coupon.total_count - coupon.claimed_count;
            return (
              <div
                key={coupon.id}
                className="mb-3 rounded-xl overflow-hidden flex"
                style={{ background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}
              >
                <div
                  className="w-24 flex flex-col items-center justify-center text-white flex-shrink-0"
                  style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                >
                  <div className="text-xl font-bold">{getCouponValue(coupon)}</div>
                  <div className="text-xs mt-0.5">满{coupon.condition_amount}可用</div>
                </div>
                <div className="flex-1 p-3 flex items-center justify-between min-w-0">
                  <div className="min-w-0">
                    <div className="flex items-center">
                      <span className="font-medium text-sm truncate">{coupon.name}</span>
                      <Tag
                        style={{
                          '--background-color': '#52c41a15',
                          '--text-color': '#52c41a',
                          '--border-color': 'transparent',
                          fontSize: 10,
                          marginLeft: 6,
                        }}
                      >
                        {getCouponTypeLabel(coupon.type)}
                      </Tag>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {coupon.valid_end
                        ? `有效期至 ${new Date(coupon.valid_end).toLocaleDateString('zh-CN')}`
                        : '长期有效'}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">剩余{remaining}张</div>
                  </div>
                  <Button
                    size="small"
                    loading={claimingIds.has(coupon.id)}
                    disabled={remaining <= 0}
                    onClick={() => handleClaim(coupon.id)}
                    style={{
                      borderRadius: 20,
                      background: remaining > 0 ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
                      color: remaining > 0 ? '#fff' : '#999',
                      border: 'none',
                      flexShrink: 0,
                      marginLeft: 12,
                    }}
                  >
                    {remaining > 0 ? '立即领取' : '已领完'}
                  </Button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
