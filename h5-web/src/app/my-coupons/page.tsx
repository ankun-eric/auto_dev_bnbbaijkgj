'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, Empty, SpinLoading, Button, Tag, InfiniteScroll, Dialog, Input, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { couponTypeLabel, jumpToUseCoupon } from '@/lib/coupon';

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

export default function MyCouponsPageWrapper() {
  return (
    <Suspense fallback={<div />}>
      <MyCouponsPage />
    </Suspense>
  );
}

function MyCouponsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // [OPT-1] 支持 ?tab=available&highlightCouponId={id} —— 进入即定位"可用"Tab，并高亮闪烁对应券
  const initialTab = (() => {
    const t = searchParams.get('tab');
    if (t === 'available' || t === 'unused') return 'unused';
    if (t === 'used' || t === 'expired') return t;
    return 'unused';
  })();
  const highlightCouponIdParam = searchParams.get('highlightCouponId');
  const highlightCouponId = highlightCouponIdParam ? Number(highlightCouponIdParam) : null;
  const couponItemRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [highlightedId, setHighlightedId] = useState<number | null>(null);
  const hasScrolledRef = useRef(false);
  const [activeTab, setActiveTab] = useState(initialTab);
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

  // [OPT-1] 进入页面后定位高亮目标券：滚动到可视区 + 1.5s 闪烁动画
  useEffect(() => {
    if (!highlightCouponId) return;
    if (hasScrolledRef.current) return;
    if (activeTab !== 'unused') return;
    if (loading) return;
    if (coupons.length === 0) return;
    // [OPT-4 链路一致性修复] 兑换记录"查看券"按钮传过来的 highlightCouponId
    // 实际是 UserCoupon.id（与小程序/Flutter 行为一致，后端 _coupon_extras 也按 UserCoupon.id 下发），
    // 因此优先按 uc.id 匹配；同时保留按 Coupon 模板 id 兜底，兼容历史调用方。
    const target = coupons.find(
      (uc) =>
        uc.id === highlightCouponId ||
        uc.coupon?.id === highlightCouponId ||
        uc.coupon_id === highlightCouponId,
    );
    if (!target) return;
    hasScrolledRef.current = true;
    const el = couponItemRefs.current.get(target.id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setHighlightedId(target.id);
    const timer = setTimeout(() => setHighlightedId(null), 1500);
    return () => clearTimeout(timer);
  }, [highlightCouponId, activeTab, loading, coupons]);

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

  const getCouponTypeLabel = (type: string) => couponTypeLabel(type);

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
      {/* [OPT-1] 高亮闪烁动画：1.5s 后由组件 setHighlightedId(null) 移除 class */}
      <style jsx global>{`
        @keyframes couponFlashHighlight {
          0%, 100% {
            box-shadow: 0 0 0 2px #ffd666, 0 1px 4px rgba(0,0,0,0.06);
            background: #fffbe6 !important;
          }
          50% {
            box-shadow: 0 0 0 4px #faad14, 0 1px 4px rgba(0,0,0,0.06);
            background: #fff7cc !important;
          }
        }
        .coupon-flash-highlight {
          animation: couponFlashHighlight 0.5s ease-in-out 3;
        }
      `}</style>
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
            const isHighlighted = highlightedId === uc.id;
            return (
              <div
                key={uc.id}
                ref={(el) => {
                  if (el) couponItemRefs.current.set(uc.id, el);
                  else couponItemRefs.current.delete(uc.id);
                }}
                className={`mb-3 rounded-xl overflow-hidden flex${isHighlighted ? ' coupon-flash-highlight' : ''}`}
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
                <div className="flex-1 p-3 min-w-0 relative">
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
                  {/* [OPT-1] 仅"可用"Tab 显示【去使用】主按钮 */}
                  {activeTab === 'unused' && (
                    <div className="flex justify-end mt-2">
                      <Button
                        size="mini"
                        fill="solid"
                        onClick={() => jumpToUseCoupon(router, uc.id)}
                        style={{
                          borderRadius: 14,
                          fontSize: 12,
                          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                          color: '#fff',
                          border: 'none',
                          padding: '0 14px',
                        }}
                      >
                        去使用
                      </Button>
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
