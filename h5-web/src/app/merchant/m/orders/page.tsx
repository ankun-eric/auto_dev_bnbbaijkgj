'use client';

// [2026-04-24] 移动端 - 订单列表 PRD §4.3
// J1 列表字段：商品名、金额、状态标签、下单时间

import React, { useEffect, useState, useCallback } from 'react';
import { Tabs, InfiniteScroll, PullToRefresh, SearchBar, Empty } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId, statusMap } from '../mobile-lib';

// PRD「商家 PC 后台优化 v1.1」F1：移动端商家 Tab 改为 14 态体系常用项
// 全部 / 待付款 / 待发货 / 待核销 / 已完成 / 已退款（不暴露 redeemed/paid）
const STATUS_TABS: { key: string; title: string }[] = [
  { key: '', title: '全部' },
  { key: 'pending_payment', title: '待付款' },
  { key: 'pending_shipment', title: '待发货' },
  { key: 'pending_use', title: '待核销' },
  { key: 'completed', title: '已完成' },
  { key: 'refunded', title: '已退款' },
];

export default function OrdersMobilePage() {
  const router = useRouter();
  const [status, setStatus] = useState<string>('');
  const [keyword, setKeyword] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (p: number, reset = false) => {
      try {
        const params: any = { page: p, page_size: 20 };
        const sid = getCurrentStoreId();
        if (sid) params.store_id = sid;
        if (status) params.status = status;
        if (keyword) params.keyword = keyword;
        const res: any = await api.get('/api/merchant/orders', { params });
        const list = res.items || [];
        setItems((prev) => (reset ? list : [...prev, ...list]));
        setPage(p);
        setHasMore(list.length >= 20);
      } catch (e: any) {
        console.warn('load orders error', e?.response?.data || e?.message);
        setHasMore(false);
      }
    },
    [status, keyword]
  );

  useEffect(() => {
    setItems([]);
    setHasMore(true);
    load(1, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const onSearch = (v: string) => {
    setKeyword(v);
    setItems([]);
    setHasMore(true);
    load(1, true);
  };

  const loadMore = async () => {
    await load(page + 1);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await load(1, true);
    setRefreshing(false);
  };

  return (
    <div style={{ minHeight: '100vh' }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 10, background: '#fff', paddingBottom: 8 }}>
        <div style={{ padding: '10px 12px 6px', background: '#fff' }}>
          <SearchBar placeholder="搜索订单号/商品名" value={keyword} onChange={setKeyword} onSearch={onSearch} onClear={() => onSearch('')} />
        </div>
        <Tabs activeKey={status} onChange={(k) => setStatus(k)} style={{ '--title-font-size': '13px' } as any}>
          {STATUS_TABS.map((t) => (
            <Tabs.Tab title={t.title} key={t.key} />
          ))}
        </Tabs>
      </div>

      <PullToRefresh onRefresh={onRefresh}>
        <div style={{ padding: '8px 12px' }}>
          {items.length === 0 && !hasMore ? (
            <Empty description="暂无订单" />
          ) : (
            items.map((o) => {
              const st = statusMap[o.status] || { text: o.status, color: '#999' };
              return (
                <div
                  key={o.order_id || o.id}
                  onClick={() => router.push(`/merchant/m/orders/${o.order_id || o.id}`)}
                  style={{
                    background: '#fff',
                    borderRadius: 10,
                    padding: '12px 14px',
                    marginBottom: 10,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                    <div
                      style={{
                        flex: 1,
                        fontSize: 15,
                        fontWeight: 500,
                        marginRight: 10,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {o.product_name || '—'}
                    </div>
                    <div style={{ color: '#fa541c', fontSize: 16, fontWeight: 700 }}>¥{o.amount || 0}</div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 10,
                        background: `${st.color}22`,
                        color: st.color,
                      }}
                    >
                      {st.text}
                    </span>
                    <span style={{ fontSize: 11, color: '#999' }}>
                      {o.created_at ? new Date(o.created_at).toLocaleString('zh-CN') : ''}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
        <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
      </PullToRefresh>
    </div>
  );
}
