'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Spin } from 'antd';
import api from '@/lib/api';
import type { KpiData } from './types';

interface KpiBarProps {
  storeId: number | null;
  onClickKpi?: (type: 'today' | 'week' | 'month') => void;
}

const KPI_ITEMS: { key: 'today' | 'week' | 'month'; title: string; field: keyof KpiData }[] = [
  { key: 'today', title: '今日预约数', field: 'today_count' },
  { key: 'week', title: '本周预约数', field: 'week_count' },
  { key: 'month', title: '本月预约数', field: 'month_count' },
];

export default function KpiBar({ storeId, onClickKpi }: KpiBarProps) {
  const [data, setData] = useState<KpiData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/calendar/kpi', {
        params: { store_id: storeId },
      });
      setData({
        today_count: res?.today_count ?? 0,
        week_count: res?.week_count ?? 0,
        month_count: res?.month_count ?? 0,
      });
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Spin spinning={loading}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        {KPI_ITEMS.map((it) => (
          <Col span={8} key={it.key}>
            <Card
              hoverable
              onClick={() => onClickKpi?.(it.key)}
              styles={{ body: { padding: '20px 24px' } }}
            >
              <div style={{ color: '#8c8c8c', fontSize: 14, marginBottom: 8 }}>
                {it.title}
              </div>
              <div style={{ fontSize: 36, fontWeight: 700, color: '#1677ff', lineHeight: 1.1 }}>
                {data ? (data[it.field] as number) : '--'}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </Spin>
  );
}
