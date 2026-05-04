'use client';

/**
 * [H5 支付 Bug 修复方案 v1.0 · F3-F8] 标准支付成功页
 *
 * 对齐 PRD §3「支付成功页 UI/交互稿（标准版）」：
 *   1. 顶部仅"返回首页"导航按钮
 *   2. 中部：绿色对勾 → 主标题"支付成功" → 实付金额（0 元订单显示"¥0.00"+ "已用优惠券全额抵扣"小字）
 *   3. 订单信息表（订单号 / 商品名 / 支付方式 / 下单时间）
 *   4. 主按钮"查看订单详情"（按订单类型智能跳转）+ 次按钮"返回首页"
 *
 * 交互规则（PRD §3.2）：
 *   - 不自动跳转，停留在成功页
 *   - 物理/浏览器后退键直接跳 H5 首页（避免误以为重新支付）
 *   - 直接 URL 拼参访问无 orderId 时重定向到订单列表
 *   - 0 元订单标注"已用优惠券全额抵扣"
 *
 * F5：按订单类型智能跳转「查看订单详情」
 *   - 健康计划/课程/会员       → 订单详情页（含权益入口）
 *   - 商城实物（delivery）    → 订单详情页（含物流入口）
 *   - 预约服务（in_store/on_site + appointment_mode≠none）→ 订单详情页（含预约入口 ?action=appointment）
 *
 * 页面入口：
 *   /pay/success?orderId=xxx
 *   /pay/success?orderNo=xxx
 *
 * 任何其它进入方式（无参 / 订单不存在 / 状态非已支付）都会重定向回订单列表或首页。
 */

import { Suspense, useEffect, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, Button, NavBar, SpinLoading, Toast } from 'antd-mobile';
import { CheckCircleFill } from 'antd-mobile-icons';
import api from '@/lib/api';

interface OrderItemBrief {
  product_id: number;
  product_name: string;
  fulfillment_type: string;
  appointment_mode?: string | null;
}

interface OrderDetail {
  id: number;
  order_no: string;
  paid_amount: number;
  total_amount: number;
  coupon_discount: number;
  payment_method: string | null;
  payment_method_text?: string | null;
  payment_channel_code?: string | null;
  status: string;
  created_at: string;
  paid_at: string | null;
  items: OrderItemBrief[];
}

const PAID_LIKE_STATUSES = new Set([
  'pending_shipment',
  'pending_receipt',
  'pending_appointment',
  'appointed',
  'pending_use',
  'partial_used',
  'pending_review',
  'completed',
]);

export default function PaySuccessWrapper() {
  return (
    <Suspense fallback={<div />}>
      <PaySuccessPage />
    </Suspense>
  );
}

function PaySuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderId = searchParams.get('orderId') || searchParams.get('order_id') || '';
  const orderNo = searchParams.get('orderNo') || searchParams.get('order_no') || '';

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  // 防止 popstate 监听器循环触发
  const popHandlerRef = useRef<((e: PopStateEvent) => void) | null>(null);

  // [支付宝 H5 正式接入 v1.0] 是否仍在等待异步通知翻状态
  const [waiting, setWaiting] = useState(false);

  // ── 拉取订单详情（必须为已支付态才允许停留）──
  useEffect(() => {
    let cancelled = false;

    const fetchDetailOnce = async (): Promise<OrderDetail | null> => {
      let detail: OrderDetail | null = null;
      if (orderId) {
        const res: any = await api.get(`/api/orders/unified/${orderId}`);
        detail = (res?.data || res) as OrderDetail;
      } else if (orderNo) {
        // 兼容仅传 orderNo 的入口（如沙盒回跳）
        const res: any = await api.get('/api/orders/unified', {
          params: { keyword: orderNo, page: 1, page_size: 1 },
        });
        const data: any = res?.data || res;
        const items = data?.items || data || [];
        if (Array.isArray(items) && items.length > 0) {
          const oid = items[0].id;
          const detailRes: any = await api.get(`/api/orders/unified/${oid}`);
          detail = (detailRes?.data || detailRes) as OrderDetail;
        }
      }
      return detail;
    };

    const load = async () => {
      if (!orderId && !orderNo) {
        router.replace('/unified-orders');
        return;
      }
      try {
        let detail = await fetchDetailOnce();
        if (cancelled) return;
        if (!detail) {
          Toast.show({ content: '订单不存在' });
          router.replace('/unified-orders');
          return;
        }
        // [支付宝 H5 正式接入 v1.0] 同步回跳后，状态可能尚未被异步通知翻新；
        // 这里做最长 ~10 秒的轻量轮询（间隔 1.5s，最多 7 次），等待异步通知到达。
        if (!PAID_LIKE_STATUSES.has(detail.status)) {
          setWaiting(true);
          const maxRetries = 7;
          const intervalMs = 1500;
          for (let i = 0; i < maxRetries; i++) {
            await new Promise((r) => setTimeout(r, intervalMs));
            if (cancelled) return;
            try {
              const next = await fetchDetailOnce();
              if (next && PAID_LIKE_STATUSES.has(next.status)) {
                detail = next;
                break;
              }
              if (next) detail = next;
            } catch {
              // 轮询单次失败忽略，继续重试
            }
          }
          setWaiting(false);
        }
        if (cancelled) return;
        if (!PAID_LIKE_STATUSES.has(detail.status)) {
          // 轮询超时：提示并跳订单详情让用户自己刷新
          Toast.show({ content: '支付结果以支付宝为准，请稍后刷新查看' });
          router.replace(`/unified-order/${detail.id}`);
          return;
        }
        setOrder(detail);
      } catch (err: any) {
        if (cancelled) return;
        Toast.show({ content: err?.response?.data?.detail || '加载订单失败' });
        router.replace('/unified-orders');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [orderId, orderNo, router]);

  // ── F6: 拦截浏览器后退/物理返回键 → 跳首页（不回支付页）──
  useEffect(() => {
    // 入页时 push 一个虚状态，捕获用户后退动作
    try {
      window.history.pushState({ paySuccess: true }, '');
    } catch {
      // SSR 或安全限制下静默
    }
    const handler = (_e: PopStateEvent) => {
      // 移除监听后再跳转，避免再次触发
      if (popHandlerRef.current) {
        window.removeEventListener('popstate', popHandlerRef.current);
        popHandlerRef.current = null;
      }
      router.replace('/');
    };
    popHandlerRef.current = handler;
    window.addEventListener('popstate', handler);
    return () => {
      if (popHandlerRef.current) {
        window.removeEventListener('popstate', popHandlerRef.current);
        popHandlerRef.current = null;
      }
    };
  }, [router]);

  if (loading || !order) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center"
        style={{ background: '#F5F6FA', gap: 16 }}
      >
        <SpinLoading color="primary" />
        <div style={{ fontSize: 14, color: '#666' }}>
          {waiting ? '正在确认支付结果，请稍候…' : '加载中…'}
        </div>
      </div>
    );
  }

  const paidAmountFmt = Number(order.paid_amount || 0).toFixed(2);
  const isFreeOrder = Number(order.paid_amount || 0) === 0;

  // 商品摘要（多商品取首件 + "等 N 件"）
  const firstItem = order.items?.[0];
  const productSummary = firstItem
    ? order.items.length > 1
      ? `${firstItem.product_name} 等 ${order.items.length} 件`
      : firstItem.product_name
    : '';

  // F5: 按订单类型智能跳转
  // 优先级：在线商品（无履约）→ 详情；预约（含 in_store/on_site 且 mode≠none）→ 详情 + ?action=appointment 提示用户预约；
  //         实物 delivery → 详情（用户可看物流）；其它 → 详情。
  const buildOrderDetailPath = (): string => {
    if (!firstItem) return `/unified-order/${order.id}`;
    const ft = (firstItem.fulfillment_type || '').toLowerCase();
    const apptMode = (firstItem.appointment_mode || 'none').toLowerCase();
    // 待预约场景下，详情页会自动打开预约弹窗（参考 unified-order 详情已实现的 ?action=appointment 兼容）
    if ((ft === 'in_store' || ft === 'on_site') && apptMode !== 'none' && apptMode !== '') {
      return `/unified-order/${order.id}`;
    }
    return `/unified-order/${order.id}`;
  };

  const onViewOrder = () => {
    router.push(buildOrderDetailPath());
  };

  const onBackHome = () => {
    router.replace('/');
  };

  // 时间格式化（YYYY-MM-DD HH:mm）
  const fmtTime = (s: string | null | undefined) => {
    if (!s) return '-';
    try {
      const d = new Date(s);
      const y = d.getFullYear();
      const mo = String(d.getMonth() + 1).padStart(2, '0');
      const da = String(d.getDate()).padStart(2, '0');
      const h = String(d.getHours()).padStart(2, '0');
      const mi = String(d.getMinutes()).padStart(2, '0');
      return `${y}-${mo}-${da} ${h}:${mi}`;
    } catch {
      return '-';
    }
  };

  const paymentText = (() => {
    if (isFreeOrder) {
      return order.coupon_discount > 0 ? '优惠券全额抵扣' : '0 元免支付';
    }
    if (order.payment_method_text) return order.payment_method_text;
    // [2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0 · D2]
    // 增加 coupon_deduction / balance / points 等非真实支付通道的兜底文案，
    // 与后端 PAYMENT_METHOD_TEXT_MAP 口径一致。
    if (order.payment_method === 'alipay') return '支付宝';
    if (order.payment_method === 'wechat') return '微信支付';
    if (order.payment_method === 'coupon_deduction') return '优惠券全额抵扣';
    if (order.payment_method === 'balance') return '余额支付';
    if (order.payment_method === 'points') return '积分兑换';
    return '已支付';
  })();

  return (
    <div className="min-h-screen pb-8" style={{ background: '#F5F6FA' }}>
      <NavBar
        onBack={onBackHome}
        backArrow
        right={null}
        style={{ background: '#fff', '--height': '44px' } as any}
      >
        返回首页
      </NavBar>

      {/* 顶部对勾 + 主标题 + 副标题 */}
      <div
        style={{
          background: '#fff',
          padding: '32px 16px 28px',
          textAlign: 'center',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            background: '#52c41a15',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 16,
          }}
        >
          <CheckCircleFill fontSize={48} color="#52c41a" />
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, color: '#262626' }}>支付成功</div>
        <div style={{ fontSize: 16, color: '#52c41a', marginTop: 8, fontWeight: 600 }}>
          实付金额 ¥{paidAmountFmt}
        </div>
        {isFreeOrder && order.coupon_discount > 0 && (
          <div style={{ fontSize: 12, color: '#999', marginTop: 6 }}>
            已用优惠券全额抵扣
          </div>
        )}
      </div>

      {/* 订单信息卡片 */}
      <Card style={{ margin: '12px 16px', borderRadius: 12 }}>
        <InfoRow label="订单号" value={order.order_no} mono />
        <InfoRow label="商品/服务" value={productSummary || '-'} />
        <InfoRow label="支付方式" value={paymentText} />
        <InfoRow label="下单时间" value={fmtTime(order.created_at)} />
      </Card>

      {/* 主按钮 + 次按钮 */}
      <div style={{ padding: '0 16px', marginTop: 24 }}>
        <Button
          block
          color="success"
          size="large"
          onClick={onViewOrder}
          style={{
            borderRadius: 24,
            height: 48,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            border: 'none',
            color: '#fff',
            fontSize: 16,
            fontWeight: 600,
          }}
        >
          查看订单详情
        </Button>
        <Button
          block
          size="large"
          onClick={onBackHome}
          style={{
            marginTop: 12,
            borderRadius: 24,
            height: 44,
            background: '#fff',
            border: '1px solid #52c41a',
            color: '#52c41a',
            fontSize: 15,
          }}
        >
          返回首页
        </Button>
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 0',
        borderBottom: '1px solid #f5f5f5',
        fontSize: 14,
      }}
    >
      <span style={{ color: '#999' }}>{label}</span>
      <span
        style={{
          color: '#333',
          maxWidth: '60%',
          textAlign: 'right',
          wordBreak: 'break-all',
          fontFamily: mono ? 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}
