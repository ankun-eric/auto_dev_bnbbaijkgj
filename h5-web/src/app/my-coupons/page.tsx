'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Tabs, Empty, SpinLoading, Button, Tag, InfiniteScroll } from 'antd-mobile';
import api from '@/lib/api';

interface CouponInfo {
  id: number;
  name: string;
  type: string;
  condition_amount: number;
  discount_value: number;
  discount_rate: number;
  valid_start: string | null;
  valid_end: string | null;
}

interface UserCoupon {
  id: number;
  user_id: number;
  coupon_id: number;
  status: string;
  used_at: string | null;
  coupon: CouponInfo | null;
  created_at: string;
}

const STATUS_TABS: Record<string, string> = {
  unused: '未使用',
  used: '已使用',
  expired: '已过期',
};

export default function MyCouponsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('unused');
  const [coupons, setCoupons] = useState<UserCoupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const fetchCoupons = useCallback(async (pageNum: number, reset = false) => {
    try {
      const res: any = await api.get(`/api/coupons/mine?tab=${activeTab}&page=${pageNum}&page_size=20`);
      const data = res.data || res;
      const items = data.items || data || [];
      if (reset) {
        setCoupons(Array.isArray(items) ? items : []);
      } else {
        setCoupons((prev) => [...prev, ...(Array.isArray(items) ? items : [])]);
      }
      setHasMore(pageNum * 20 < (data.total || 0));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    fetchCoupons(1, true);
  }, [fetchCoupons]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await fetchCoupons(next);
  };

  const getCouponValue = (coupon: CouponInfo) => {
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
        我的优惠券
      </NavBar>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          background: '#fff',
        }}
      >
        {Object.entries(STATUS_TABS).map(([key, title]) => (
          <Tabs.Tab key={key} title={title} />
        ))}
      </Tabs>

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : coupons.length === 0 ? (
          <div className="text-center py-20">
            <Empty description="暂无优惠券" />
            <Button
              size="small"
              onClick={() => router.push('/coupon-center')}
              style={{ marginTop: 16, borderRadius: 20, color: '#52c41a', borderColor: '#52c41a' }}
            >
              去领券中心
            </Button>
          </div>
        ) : (
          coupons.map((uc) => {
            const coupon = uc.coupon;
            if (!coupon) return null;
            const isDisabled = activeTab !== 'unused';
            return (
              <div
                key={uc.id}
                className="mb-3 rounded-xl overflow-hidden flex"
                style={{
                  background: '#fff',
                  opacity: isDisabled ? 0.6 : 1,
                  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                }}
              >
                <div
                  className="w-24 flex flex-col items-center justify-center text-white flex-shrink-0"
                  style={{
                    background: isDisabled
                      ? '#bfbfbf'
                      : 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  }}
                >
                  <div className="text-xl font-bold">{getCouponValue(coupon)}</div>
                  <div className="text-xs mt-0.5">满{coupon.condition_amount}可用</div>
                </div>
                <div className="flex-1 p-3 min-w-0">
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
                  {isDisabled && uc.used_at && (
                    <div className="text-xs text-gray-400 mt-0.5">
                      使用于 {new Date(uc.used_at).toLocaleDateString('zh-CN')}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
        {!loading && coupons.length > 0 && (
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        )}

        {activeTab === 'unused' && coupons.length > 0 && (
          <div className="text-center py-4">
            <Button
              size="small"
              onClick={() => router.push('/coupon-center')}
              style={{ borderRadius: 20, color: '#52c41a', borderColor: '#52c41a' }}
            >
              领更多券
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
