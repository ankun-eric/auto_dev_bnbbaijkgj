'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Tag, Empty, SpinLoading } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { formatDate } from '@/lib/datetime';

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
  // V2.1：领券中心置灰新增字段
  claimed?: boolean;
  sold_out?: boolean;
  button_text?: string;
  button_disabled?: boolean;
}

export default function CouponCenterPage() {
  const router = useRouter();
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [claimingIds, setClaimingIds] = useState<Set<number>>(new Set());

  const fetchCoupons = () => {
    setLoading(true);
    api.get('/api/coupons/available').then((res: any) => {
      const data = res.data || res;
      setCoupons(data.items || data || []);
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCoupons();
  }, []);

  const isLoggedIn = (): boolean => {
    if (typeof window === 'undefined') return false;
    return !!(localStorage.getItem('access_token') || localStorage.getItem('token'));
  };

  const handleClaim = async (coupon: Coupon) => {
    if (coupon.button_disabled) return;
    if (!isLoggedIn()) {
      showToast('请先登录后再领取', 'fail');
      setTimeout(() => router.push('/login'), 800);
      return;
    }
    setClaimingIds((prev) => new Set(prev).add(coupon.id));
    try {
      await api.post('/api/coupons/claim', { coupon_id: coupon.id });
      showToast('领取成功', 'success');
      fetchCoupons();
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 409) {
        showToast('您已领取过该券', 'fail');
        fetchCoupons();
      } else {
        showToast(err?.response?.data?.detail || '领取失败', 'fail');
      }
    } finally {
      setClaimingIds((prev) => {
        const next = new Set(prev);
        next.delete(coupon.id);
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
    const map: Record<string, string> = { full_reduction: '满减', discount: '折扣', voucher: '代金券', free_trial: '免费体验券' };
    return map[type] || type;
  };

  // V2.1：本地兜底计算（如后端缺字段）
  const computeButtonState = (coupon: Coupon) => {
    if (typeof coupon.button_text === 'string' && typeof coupon.button_disabled === 'boolean') {
      return { text: coupon.button_text, disabled: coupon.button_disabled };
    }
    if (coupon.claimed) return { text: '已领取', disabled: true };
    if (coupon.sold_out || coupon.total_count - coupon.claimed_count <= 0) {
      return { text: '已抢光', disabled: true };
    }
    return { text: '领取', disabled: false };
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar>
        领券中心
      </GreenNavBar>

      <div className="px-4 py-4" style={{ background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)' }}>
        <div className="text-white text-lg font-bold">优惠券等你来领</div>
        <div className="text-white/70 text-xs mt-1">每张券每人限领 1 次</div>
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
            const { text: btnText, disabled: btnDisabled } = computeButtonState(coupon);
            return (
              <div
                key={coupon.id}
                className="mb-3 rounded-xl overflow-hidden flex"
                style={{ background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}
              >
                <div
                  className="w-24 flex flex-col items-center justify-center text-white flex-shrink-0"
                  style={{
                    background: btnDisabled
                      ? 'linear-gradient(135deg, #bdbdbd, #9e9e9e)'
                      : 'linear-gradient(135deg, #0284C7, #075985)',
                  }}
                >
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#fff' }}>{getCouponValue(coupon)}</div>
                  <div className="text-xs mt-0.5">满{coupon.condition_amount}可用</div>
                </div>
                <div className="flex-1 p-3 flex items-center justify-between min-w-0">
                  <div className="min-w-0">
                    <div className="flex items-center">
                      <span className="font-medium text-sm truncate" style={{ color: btnDisabled ? '#999' : '#222' }}>
                        {coupon.name}
                      </span>
                      <Tag
                        style={{
                          '--background-color': btnDisabled ? '#eee' : '#0EA5E915',
                          '--text-color': btnDisabled ? '#999' : '#0EA5E9',
                          '--border-color': 'transparent',
                          fontSize: 10,
                          marginLeft: 6,
                        }}
                      >
                        {getCouponTypeLabel(coupon.type)}
                      </Tag>
                    </div>
                    <div className="text-xs text-gray-400 mt-1" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>{coupon.valid_end
                        ? `有效期至 ${formatDate(coupon.valid_end)}`
                        : '长期有效'}</span>
                      {coupon.valid_end && (() => {
                        const daysLeft = Math.ceil((new Date(coupon.valid_end).getTime() - Date.now()) / 86400000);
                        return daysLeft <= 7 && daysLeft > 0 ? (
                          <span style={{ background: '#FFFBEB', color: '#F59E0B', fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 4 }}>即将过期</span>
                        ) : null;
                      })()}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">剩余{Math.max(0, remaining)}张</div>
                  </div>
                  <Button
                    size="small"
                    loading={claimingIds.has(coupon.id)}
                    disabled={btnDisabled}
                    onClick={() => handleClaim(coupon)}
                    style={{
                      borderRadius: 20,
                      background: btnDisabled
                        ? '#e8e8e8'
                        : 'linear-gradient(135deg, #38BDF8, #0284C7)',
                      color: btnDisabled ? '#999' : '#fff',
                      border: 'none',
                      flexShrink: 0,
                      marginLeft: 12,
                      minWidth: 72,
                    }}
                  >
                    {btnText}
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
