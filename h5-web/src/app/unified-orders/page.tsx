'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, Card, Tag, Image, Button, Empty, SpinLoading, InfiniteScroll, Dialog, Badge } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import ContactStoreModal from '@/app/orders/components/ContactStoreModal';
import { resolveAssetUrl } from '@/lib/asset-url';
import { formatDateTime } from '@/lib/datetime';

interface OrderItem {
  id: number;
  product_id: number;
  product_name: string;
  product_image: string | null;
  product_price: number;
  quantity: number;
  subtotal: number;
  fulfillment_type: string;
  redemption_code_status?: string;
}

interface Order {
  id: number;
  order_no: string;
  total_amount: number;
  paid_amount: number;
  status: string;
  refund_status: string;
  has_reviewed?: boolean;
  display_status?: string;
  display_status_color?: string;
  action_buttons?: string[];
  badges?: string[];
  items: OrderItem[];
  created_at: string;
  completed_at?: string | null;
  // PRD F-12：15 天评价时效
  review_deadline_at?: string | null;
  review_expired?: boolean;
  // PRD F-13：用户撤销售后能力
  can_withdraw_refund?: boolean;
  // PRD F-05/F-07：售后逻辑状态
  aftersales_logical_status?: string;
  aftersales_logical_label?: string;
  // [核销订单过期+改期规则优化 v1.0] 改期次数 + 商家联系入口
  reschedule_count?: number;
  reschedule_limit?: number;
  allow_reschedule?: boolean;
  store_id?: number | null;
  store_name?: string | null;
}

// PRD「我的订单与售后状态体系优化」：客户端 5 Tab + 全部
// 顺序：全部 / 待付款 / 待收货 / 待使用 / 已完成 / 退货/售后
// F-03：末位 Tab 文案补斜杠 "退货售后" → "退货/售后"
const TABS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'pending_payment', label: '待付款' },
  { key: 'pending_receipt', label: '待收货' },
  { key: 'pending_use', label: '待使用' },
  { key: 'completed', label: '已完成' },
  { key: 'refund_aftersales', label: '退货/售后' },
];

// PRD F-05：退货/售后二级筛选 — 4 个统一逻辑状态
// 待审核 / 处理中 / 已完成 / 已驳回（与 H5 退款独立列表 / 后台筛选完全一致）
const REFUND_SUB_TABS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'processing', label: '处理中' },
  { key: 'completed', label: '已完成' },
  { key: 'rejected', label: '已驳回' },
];

// PRD V2：12 状态显示文案 + 颜色（卡片右上角）
const STATUS_TEXT: Record<string, string> = {
  pending_payment: '待付款',
  pending_shipment: '待发货',
  pending_receipt: '待收货',
  pending_appointment: '待预约',
  appointed: '待核销',
  pending_use: '待核销',
  partial_used: '部分核销',
  pending_review: '待评价',
  completed: '已完成',
  expired: '已过期',
  refunding: '退款中',
  refunded: '已退款',
  cancelled: '已取消',
};

const STATUS_COLOR: Record<string, string> = {
  pending_payment: '#fa8c16',
  pending_shipment: '#1890ff',
  pending_receipt: '#38BDF8',
  pending_appointment: '#722ed1',
  appointed: '#722ed1',
  pending_use: '#38BDF8',
  partial_used: '#faad14',
  pending_review: '#eb2f96',
  completed: '#0EA5E9',
  expired: '#8c8c8c',
  refunding: '#f5222d',
  refunded: '#8c8c8c',
  cancelled: '#8c8c8c',
};

export default function UnifiedOrdersWrapper() {
  return (
    <Suspense fallback={<div />}>
      <UnifiedOrdersPage />
    </Suspense>
  );
}

function UnifiedOrdersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'all';
  const initialSub = searchParams.get('sub_tab') || 'all';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [activeSubTab, setActiveSubTab] = useState(initialSub);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  // [核销订单过期+改期规则优化 v1.0]「联系商家」弹窗
  const [contactOrder, setContactOrder] = useState<Order | null>(null);

  const fetchOrders = useCallback(async (pageNum: number, reset = false) => {
    try {
      const params: Record<string, any> = { page: pageNum, page_size: 20 };
      // PRD V2：使用 tab 参数，后端自动按映射规则过滤
      params.tab = activeTab;
      if (activeTab === 'refund_aftersales') {
        params.sub_tab = activeSubTab;
      }
      const res: any = await api.get('/api/orders/unified', { params });
      const data = res.data || res;
      const items = data.items || [];
      if (reset) {
        setOrders(items);
      } else {
        setOrders((prev) => [...prev, ...items]);
      }
      setHasMore(pageNum * 20 < (data.total || 0));
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [activeTab, activeSubTab]);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    fetchOrders(1, true);
  }, [fetchOrders]);

  // [BUG-FIX-RESCHEDULE-POPUP-AUTO-CLOSE v1.0]
  // 当顾客在订单详情页改约/预约成功后，会写 localStorage 标志，列表页在以下时机检测并强制刷新：
  // 1) pageshow：浏览器返回（含 BFCache 命中）时触发，覆盖 H5 路由 router.back() 与浏览器后退
  // 2) visibilitychange：页面从后台切回前台
  // 3) focus：窗口重新获得焦点（兜底）
  useEffect(() => {
    const REFRESH_KEY = 'bini_unified_orders_need_refresh';
    const checkAndRefresh = () => {
      try {
        const flag = window.localStorage.getItem(REFRESH_KEY);
        if (flag) {
          window.localStorage.removeItem(REFRESH_KEY);
          setLoading(true);
          setPage(1);
          fetchOrders(1, true);
        }
      } catch {
        /* localStorage 不可用时静默忽略 */
      }
    };
    const onPageShow = () => checkAndRefresh();
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') checkAndRefresh();
    };
    const onFocus = () => checkAndRefresh();
    window.addEventListener('pageshow', onPageShow);
    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('focus', onFocus);
    // 进入页面时也检测一次（覆盖 SPA 同窗口路由切换的情况）
    checkAndRefresh();
    return () => {
      window.removeEventListener('pageshow', onPageShow);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('focus', onFocus);
    };
  }, [fetchOrders]);

  const loadMore = async () => {
    const next = page + 1;
    setPage(next);
    await fetchOrders(next);
  };

  const handlePay = async (orderId: number) => {
    try {
      await api.post(`/api/orders/unified/${orderId}/pay`, { payment_method: 'wechat' });
      showToast('支付成功');
      setLoading(true);
      setPage(1);
      fetchOrders(1, true);
    } catch (err: any) {
      showToast(err?.response?.data?.detail || '支付失败');
    }
  };

  const handleCancel = async (orderId: number) => {
    Dialog.confirm({
      content: '确认取消该订单？',
      confirmText: '确认',
      cancelText: '再想想',
      onConfirm: async () => {
        try {
          await api.post(`/api/orders/unified/${orderId}/cancel`, {});
          showToast('已取消');
          setLoading(true);
          setPage(1);
          fetchOrders(1, true);
        } catch (err: any) {
          showToast(err?.response?.data?.detail || '取消失败');
        }
      },
    });
  };

  const handleConfirmReceipt = async (orderId: number) => {
    try {
      await api.post(`/api/orders/unified/${orderId}/confirm`);
      showToast('已确认收货');
      setLoading(true);
      setPage(1);
      fetchOrders(1, true);
    } catch {
      showToast('操作失败');
    }
  };

  // [BUG-FIX-REBUY-V1 2026-05-07]「再来一单」：调后端 reorder 校验商品状态后跳支付页
  // 不再跳转原订单详情页（旧 ?action=rebuy 参数从未被处理，导致 Bug）。
  const handleRebuy = async (orderId: number) => {
    try {
      const res: any = await api.post(`/api/orders/unified/${orderId}/reorder`, {});
      const data = res?.data || res;
      const status = data?.status;
      const items: any[] = data?.available_items || [];
      if (status === 'all_unavailable' || items.length === 0) {
        showToast(data?.message || '商品已全部下架，无法再来一单');
        return;
      }
      if (status === 'partial_filtered') {
        showToast(data?.message || '部分商品已下架，已为您过滤');
      }
      // checkout 页是单品流转：取首品作为复购入口（携带 sku_id/quantity）
      const first = items[0];
      const params = new URLSearchParams();
      params.set('product_id', String(first.product_id));
      if (first.sku_id) params.set('sku_id', String(first.sku_id));
      if (first.quantity) params.set('quantity', String(first.quantity));
      params.set('from_rebuy', '1');
      router.push(`/checkout?${params.toString()}`);
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        // 登录态过期：跳登录页（登录成功后用户回到本页面继续点击）
        showToast('请先登录');
        router.push(`/login?redirect=${encodeURIComponent('/unified-orders')}`);
        return;
      }
      showToast(err?.response?.data?.detail || '网络异常，请稍后重试');
    }
  };

  const getStatusDisplay = (order: Order) => {
    // 后端已经返回 display_status / display_status_color，优先用
    if (order.display_status) {
      return {
        text: order.display_status,
        color: order.display_status_color || STATUS_COLOR[order.status] || '#8c8c8c',
      };
    }
    if (order.status === 'cancelled' && order.refund_status === 'refund_success') {
      return { text: '已取消（已退款）', color: '#8c8c8c' };
    }
    // V2: 完成态但未评价 → 显示"待评价"
    if (order.status === 'completed' && order.has_reviewed === false) {
      return { text: '待评价', color: STATUS_COLOR.pending_review };
    }
    return {
      text: STATUS_TEXT[order.status] || order.status,
      color: STATUS_COLOR[order.status] || '#8c8c8c',
    };
  };

  // PRD V2：根据当前订单状态/Tab 渲染按钮组
  const renderButtons = (order: Order) => {
    const btns = order.action_buttons || [];
    const items: React.ReactNode[] = [];
    if (btns.includes('cancel')) {
      items.push(
        <Button
          key="cancel"
          size="mini"
          onClick={(e) => { e.stopPropagation(); handleCancel(order.id); }}
          style={{ borderRadius: 16, fontSize: 12 }}
        >取消订单</Button>
      );
    }
    if (btns.includes('pay')) {
      items.push(
        <Button
          key="pay"
          size="mini"
          onClick={(e) => { e.stopPropagation(); handlePay(order.id); }}
          style={{ borderRadius: 16, fontSize: 12, background: '#0EA5E9', color: '#fff', border: 'none' }}
        >去支付</Button>
      );
    }
    if (btns.includes('confirm_receipt')) {
      items.push(
        <Button
          key="confirm"
          size="mini"
          onClick={(e) => { e.stopPropagation(); handleConfirmReceipt(order.id); }}
          style={{ borderRadius: 16, fontSize: 12, background: '#0EA5E9', color: '#fff', border: 'none' }}
        >确认收货</Button>
      );
    }
    if (btns.includes('set_appointment')) {
      items.push(
        <Button
          key="appt"
          size="mini"
          onClick={(e) => { e.stopPropagation(); router.push(`/unified-order/${order.id}?action=appointment`); }}
          style={{ borderRadius: 16, fontSize: 12, background: '#722ed1', color: '#fff', border: 'none' }}
        >去预约</Button>
      );
    }
    if (btns.includes('show_qrcode')) {
      items.push(
        <Button
          key="qr"
          size="mini"
          onClick={(e) => { e.stopPropagation(); router.push(`/unified-order/${order.id}`); }}
          style={{ borderRadius: 16, fontSize: 12, background: '#38BDF8', color: '#fff', border: 'none' }}
        >查看核销码</Button>
      );
    }
    if (btns.includes('modify_appointment')) {
      // [核销订单过期+改期规则优化 v1.0] 已达改期上限：按钮置灰 + Toast 提示
      const blocked =
        (order.reschedule_count ?? 0) >= (order.reschedule_limit ?? 3) ||
        (order.badges || []).includes('reschedule_blocked');
      if (blocked) {
        items.push(
          <Button
            key="modify_appt_blocked"
            size="mini"
            disabled
            onClick={(e) => {
              e.stopPropagation();
              showToast('本订单已达改期上限');
            }}
            style={{ borderRadius: 16, fontSize: 12, color: '#bfbfbf', borderColor: '#d9d9d9' }}
          >
            改约
          </Button>
        );
      } else {
        items.push(
          <Button
            key="modify_appt"
            size="mini"
            onClick={(e) => { e.stopPropagation(); router.push(`/unified-order/${order.id}?action=appointment`); }}
            style={{ borderRadius: 16, fontSize: 12 }}
          >改约</Button>
        );
      }
    }
    if (btns.includes('apply_refund')) {
      items.push(
        <Button
          key="apply_refund"
          size="mini"
          onClick={(e) => { e.stopPropagation(); router.push(`/unified-order/${order.id}/refund`); }}
          style={{ borderRadius: 16, fontSize: 12 }}
        >申请退款</Button>
      );
    }
    if (btns.includes('review')) {
      items.push(
        <Button
          key="review"
          size="mini"
          onClick={(e) => { e.stopPropagation(); router.push(`/review/${order.id}`); }}
          style={{ borderRadius: 16, fontSize: 12, color: '#0EA5E9', borderColor: '#0EA5E9' }}
        >去评价</Button>
      );
    }
    // PRD F-12：超过 15 天评价时效，按钮置灰显示「评价已过期」
    if (btns.includes('review_expired')) {
      items.push(
        <Button
          key="review_expired"
          size="mini"
          disabled
          onClick={(e) => { e.stopPropagation(); }}
          style={{ borderRadius: 16, fontSize: 12, color: '#bfbfbf', borderColor: '#d9d9d9', background: '#f5f5f5' }}
        >评价已过期</Button>
      );
    }
    if (btns.includes('view_review')) {
      items.push(
        <Button
          key="view_review"
          size="mini"
          onClick={(e) => { e.stopPropagation(); router.push(`/review/${order.id}?mode=view`); }}
          style={{ borderRadius: 16, fontSize: 12 }}
        >查看评价</Button>
      );
    }
    // PRD F-13：售后处于「待审核」时用户可在订单卡上直接撤销
    if (btns.includes('view_refund') && order.can_withdraw_refund) {
      items.push(
        <Button
          key="withdraw_refund"
          size="mini"
          onClick={(e) => {
            e.stopPropagation();
            Dialog.confirm({
              content: '确认撤销本次售后申请？撤销后订单将恢复原状态',
              confirmText: '确认撤销',
              cancelText: '再想想',
              onConfirm: async () => {
                try {
                  await api.post(`/api/orders/unified/${order.id}/refund/cancel`, {});
                  showToast('已撤销');
                  setLoading(true);
                  setPage(1);
                  fetchOrders(1, true);
                } catch (err: any) {
                  showToast(err?.response?.data?.detail || '撤销失败');
                }
              },
            });
          }}
          style={{ borderRadius: 16, fontSize: 12, color: '#fa8c16', borderColor: '#fa8c16' }}
        >撤销申请</Button>
      );
    }
    if (btns.includes('view_refund')) {
      items.push(
        <Button
          key="refund"
          size="mini"
          onClick={(e) => { e.stopPropagation(); router.push(`/unified-order/${order.id}?action=refund`); }}
          style={{ borderRadius: 16, fontSize: 12, color: '#f5222d', borderColor: '#f5222d' }}
        >退款详情</Button>
      );
    }
    if (btns.includes('rebuy')) {
      items.push(
        <Button
          key="rebuy"
          size="mini"
          onClick={(e) => { e.stopPropagation(); handleRebuy(order.id); }}
          style={{ borderRadius: 16, fontSize: 12 }}
        >再来一单</Button>
      );
    }
    // [核销订单过期+改期规则优化 v1.0] 所有状态下「联系商家」按钮始终展示
    if (btns.includes('contact_store')) {
      items.push(
        <Button
          key="contact_store"
          size="mini"
          onClick={(e) => { e.stopPropagation(); setContactOrder(order); }}
          style={{ borderRadius: 16, fontSize: 12 }}
        >联系商家</Button>
      );
    }
    if (items.length === 0) return null;
    return (
      <div className="flex justify-end gap-2 mt-3 pt-3 border-t border-gray-50">
        {items}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar>
        我的订单
      </GreenNavBar>

      {/* PRD V2: 5 Tab + 全部，取消"待评价"独立 Tab */}
      <Tabs
        activeKey={activeTab}
        onChange={(k) => { setActiveTab(k); setActiveSubTab('all'); }}
        className="green-bold-tabs"
        style={{
          '--active-line-color': '#0EA5E9',
          '--active-title-color': '#0EA5E9',
          '--title-font-size': '14px',
          '--active-line-height': '2px',
          background: '#fff',
        } as React.CSSProperties}
      >
        {TABS.map(t => <Tabs.Tab key={t.key} title={t.label} />)}
      </Tabs>

      {/* PRD V2: "退货售后" 才有二级筛选；"全部" Tab 取消二级筛选 */}
      {activeTab === 'refund_aftersales' && (
        <div
          className="px-4 py-2 flex gap-2 overflow-x-auto"
          style={{ background: '#fff', borderTop: '1px solid #f0f0f0' }}
        >
          {REFUND_SUB_TABS.map(s => (
            <span
              key={s.key}
              onClick={() => setActiveSubTab(s.key)}
              style={{
                padding: '4px 12px',
                borderRadius: 16,
                fontSize: 12,
                whiteSpace: 'nowrap',
                background: activeSubTab === s.key ? '#0EA5E915' : '#f5f5f5',
                color: activeSubTab === s.key ? '#0EA5E9' : '#666',
                fontWeight: activeSubTab === s.key ? 600 : 400,
                cursor: 'pointer',
              }}
            >
              {s.label}
            </span>
          ))}
        </div>
      )}

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : orders.length === 0 ? (
          <Empty description="暂无订单" style={{ padding: '80px 0' }} />
        ) : (
          orders.map((order) => {
            const statusInfo = getStatusDisplay(order);
            // PRD V2 待使用徽章 — 待核销/部分核销时高亮
            const showHotBadge = order.badges && order.badges.includes('可核销');
            return (
              <Card
                key={order.id}
                onClick={() => router.push(`/unified-order/${order.id}`)}
                style={{ marginBottom: 12, borderRadius: 12 }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-gray-400">订单号：{order.order_no}</span>
                  {/* 全部 Tab 卡片右上角直接显示状态文字（PRD V2 第 0.2 节） */}
                  <Tag
                    style={{
                      '--background-color': `${statusInfo.color}15`,
                      '--text-color': statusInfo.color,
                      '--border-color': 'transparent',
                      fontSize: 10,
                      fontWeight: 600,
                    }}
                  >
                    {statusInfo.text}
                  </Tag>
                </div>
                {order.items.map((item) => (
                  <div key={item.id} className="flex items-center mb-2">
                    <div className="w-16 h-16 rounded-lg flex-shrink-0 overflow-hidden">
                      {item.product_image ? (
                        <Image src={resolveAssetUrl(item.product_image)} width={64} height={64} fit="cover" style={{ borderRadius: 8 }} />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-2xl" style={{ background: '#F0F9FF' }}>
                          🛍️
                        </div>
                      )}
                    </div>
                    <div className="flex-1 ml-3 min-w-0">
                      <div className="font-medium text-sm truncate">{item.product_name}</div>
                      <div className="text-xs text-gray-400 mt-1">x{item.quantity}</div>
                    </div>
                    <span className="font-bold text-sm">¥{item.subtotal}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between pt-2 border-t border-gray-50">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">
                      {formatDateTime(order.created_at)}
                    </span>
                    {showHotBadge && (
                      <span style={{
                        background: '#38BDF8',
                        color: '#fff',
                        fontSize: 10,
                        padding: '2px 6px',
                        borderRadius: 8,
                      }}>可核销</span>
                    )}
                  </div>
                  <span className="text-sm">
                    实付 <span className="font-bold text-red-500">¥{order.paid_amount}</span>
                  </span>
                </div>
                {renderButtons(order)}
              </Card>
            );
          })
        )}
        {!loading && orders.length > 0 && (
          <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
        )}
      </div>

      <ContactStoreModal
        visible={!!contactOrder}
        storeId={contactOrder?.store_id ?? null}
        fallbackStoreName={contactOrder?.store_name ?? null}
        onClose={() => setContactOrder(null)}
      />
    </div>
  );
}
