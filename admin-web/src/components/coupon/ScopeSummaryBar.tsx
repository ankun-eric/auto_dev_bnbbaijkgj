'use client';

import React, { useEffect, useState } from 'react';
import { Alert, Spin } from 'antd';
import { get } from '@/lib/api';

interface Props {
  scope: 'all' | 'category' | 'product' | string;
  scopeIds: number[];
  excludeIds: number[];
}

/**
 * F8：适用范围统计预览（绿色背景轻提示条）
 * - scope=all：本券对全店 N 个在售商品生效，已排除 W 个商品
 * - scope=category：本券对 Y 个分类（共 Z 个商品）生效，已排除 W 个商品
 * - scope=product：本券对 X 个商品生效（指定商品模式不展示排除）
 */
export default function ScopeSummaryBar({ scope, scopeIds, excludeIds }: Props) {
  const [allCount, setAllCount] = useState<number | null>(null);
  const [catProductCount, setCatProductCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  // scope=all：拉全店在售数
  useEffect(() => {
    if (scope !== 'all') return;
    setLoading(true);
    get('/api/admin/coupons/active-product-count')
      .then((res: any) => setAllCount(res?.product_count ?? 0))
      .catch(() => setAllCount(null))
      .finally(() => setLoading(false));
  }, [scope]);

  // scope=category：拉分类下商品数
  useEffect(() => {
    if (scope !== 'category' || scopeIds.length === 0) {
      setCatProductCount(null);
      return;
    }
    setLoading(true);
    get(`/api/admin/coupons/category-product-count?category_ids=${scopeIds.join(',')}`)
      .then((res: any) => setCatProductCount(res?.product_count ?? 0))
      .catch(() => setCatProductCount(null))
      .finally(() => setLoading(false));
  }, [scope, JSON.stringify(scopeIds)]); // eslint-disable-line

  let msg: React.ReactNode;
  if (scope === 'all') {
    msg = (
      <span>
        📊 本券将对 <b>全店 {allCount ?? '--'} 个在售商品</b>（实物 + 到店服务）生效
        ，已排除 <b>{excludeIds.length}</b> 个商品。
      </span>
    );
  } else if (scope === 'category') {
    msg = (
      <span>
        📊 本券将对 <b>{scopeIds.length} 个分类</b>
        （共 <b>{catProductCount ?? '--'} 个商品</b>）生效
        ，已排除 <b>{excludeIds.length}</b> 个商品。
      </span>
    );
  } else {
    msg = (
      <span>
        📊 本券将对 <b>{scopeIds.length} 个指定商品</b>生效。
      </span>
    );
  }

  return (
    <Alert
      type="success"
      showIcon={false}
      style={{ background: '#f6ffed', border: '1px solid #b7eb8f', marginTop: 8 }}
      message={<Spin spinning={loading} size="small">{msg}</Spin>}
    />
  );
}
