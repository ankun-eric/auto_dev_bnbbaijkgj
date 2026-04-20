'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, Empty, SpinLoading, Button, Tag, InfiniteScroll, Dialog, Input, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface CouponInfo {
  id: number;
  name: string;
  type: string;
  condition_amount: number;
  discount_value: number;
  discount_rate: number;
  validity_days?: number;
}

interface UserCoupon {
  id: number;
  user_id: number;
  coupon_id: number;
  status: string;
  used_at: string | null;
  expire_at: string | null;
  source?: string;
  coupon: CouponInfo | null;
  created_at: string;
}

const STATUS_TABS: Record<string, string> = {
  unused: '可用',
  used: '已使用',
  expired: '已过期',
};

// Bug#3：合计数 与 "可用(N)" Tab 必须同源——均来自"可用券列表"的 total
// 后端约定字段（新）：available_count / used_count / expired_count / total_count
// 兼容旧字段：若后端仅返回 total（/coupons/mine?tab=unused&exclude_expired=true），以 total 为准
interface CouponCounts {
  available: number;
  used: number;
  expired: number;
}

export default function MyCouponsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('unused');
  const [coupons, setCoupons] = useState<UserCoupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [counts, setCounts] = useState<CouponCounts>({ available: 0, used: 0, expired: 0 });

  const fetchCoupons = useCallback(async (pageNum: number, reset = false) => {
    try {
      const excludeExpired = activeTab === 'unused' ? '&exclude_expired=true' : '';
      const res: any = await api.get(`/api/coupons/mine?tab=${activeTab}&page=${pageNum}&page_size=20${excludeExpired}`);
      const data = res.data || res;
      const items = data.items || data || [];
      if (reset) {
        setCoupons(Array.isArray(items) ? items : []);
      } else {
        setCoupons((prev) => [...prev, ...(Array.isArray(items) ? items : [])]);
      }
      const total = Number(data.total || 0);
      setHasMore(pageNum * 20 < total);
      if (reset) {
        setCounts((prev) => {
          const next = { ...prev };
          if (activeTab === 'unused') next.available = total;
          else if (activeTab === 'used') next.used = total;
          else if (activeTab === 'expired') next.expired = total;
          return next;
        });
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  // Bug#3：合计 = 可用券数量（独立于当前 Tab），始终拉取一次 unused 总数
  const fetchAvailableCount = useCallback(async () => {
    try {
      const res: any = await api.get('/api/coupons/summary');
      const data = res?.data || res || {};
      if (
        typeof data.available_count === 'number' ||
        typeof data.used_count === 'number' ||
        typeof data.expired_count === 'number'
      ) {
        setCounts({
          available: Number(data.available_count || 0),
          used: Number(data.used_count || 0),
          expired: Number(data.expired_count || 0),
        });
        return;
      }
    } catch {
      // ignore, fallback below
    }
    try {
      const res: any = await api.get('/api/coupons/mine?tab=unused&page=1&page_size=1&exclude_expired=true');
      const data = res?.data || res || {};
      setCounts((prev) => ({ ...prev, available: Number(data.total || 0) }));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    fetchCoupons(1, true);
  }, [fetchCoupons]);

  useEffect(() => {
    fetchAvailableCount();
  }, [fetchAvailableCount]);

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

  const getCouponExpiryStatus = (expireAt: string | null): 'expiring' | 'normal' => {
    if (!expireAt) return 'normal';
    const endTime = new Date(expireAt).getTime();
    if (Number.isNaN(endTime)) return 'normal';
    const diffMs = endTime - Date.now();
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    if (diffMs > 0 && diffMs <= sevenDays) return 'expiring';
    return 'normal';
  };

  const handleRedeem = async () => {
    let inputCode = '';
    const ok = await Dialog.confirm({
      title: '兑换码兑换',
      content: (
        <Input
          placeholder="请输入兑换码"
          maxLength={32}
          onChange={(v) => { inputCode = v.trim(); }}
          style={{ '--font-size': '16px' } as any}
        />
      ),
      confirmText: '兑换',
    });
    if (!ok) return;
    if (!inputCode) {
      Toast.show({ content: '请输入兑换码', icon: 'fail' });
      return;
    }
    try {
      const res: any = await api.post('/api/coupons/redeem', { code: inputCode });
      const data = res.data || res;
      Toast.show({ content: data?.message || '兑换成功', icon: 'success' });
      setLoading(true);
      setPage(1);
      fetchCoupons(1, true);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '兑换失败';
      Toast.show({ content: String(detail), icon: 'fail', duration: 3000 });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar
        right={
          <a
            className="text-white text-sm font-medium cursor-pointer"
            onClick={handleRedeem}
          >
            兑换码
          </a>
        }
      >
        我的优惠券
      </GreenNavBar>

      {/* Bug#3：顶部"合计"与下方"可用(N)" Tab 同源（均来自可用券 total） */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)', color: '#fff' }}
      >
        <div>
          <div className="text-xs opacity-80">合计可用</div>
          <div className="text-2xl font-bold">{counts.available}</div>
        </div>
        <div className="text-xs opacity-80">张优惠券</div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        className="green-bold-tabs"
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          '--active-line-height': '2px',
          background: '#fff',
        } as React.CSSProperties}
      >
        {Object.entries(STATUS_TABS).map(([key, title]) => {
          const n = key === 'unused' ? counts.available
            : key === 'used' ? counts.used
            : key === 'expired' ? counts.expired
            : 0;
          return <Tabs.Tab key={key} title={`${title}(${n})`} />;
        })}
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
            const expiryStatus = getCouponExpiryStatus(uc.expire_at);
            const isExpiring = expiryStatus === 'expiring' && !isDisabled;
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
                  <div className="flex items-center flex-wrap gap-1">
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
                    {isExpiring && (
                      <Tag
                        style={{
                          '--background-color': '#fff1f0',
                          '--text-color': '#f5222d',
                          '--border-color': '#ffa39e',
                          fontSize: 10,
                        }}
                      >
                        即将到期
                      </Tag>
                    )}
                  </div>
                  <div
                    className="text-xs mt-1"
                    style={{ color: isExpiring ? '#f5222d' : '#999' }}
                  >
                    {uc.expire_at
                      ? `有效期至 ${new Date(uc.expire_at).toLocaleDateString('zh-CN')}`
                      : `领取后 ${coupon.validity_days || 30} 天内有效`}
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
