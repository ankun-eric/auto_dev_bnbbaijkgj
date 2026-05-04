'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Spin, Tooltip } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import api from '@/lib/api';
import type { CalendarFilters, CellInfo } from './types';

const CN_WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

interface WeekViewProps {
  storeId: number | null;
  currentDate: Dayjs;
  onCellClick?: (date: string, cell: CellInfo | null) => void;
  filters: CalendarFilters;
}

export default function WeekView({
  storeId,
  currentDate,
  onCellClick,
  filters,
}: WeekViewProps) {
  const [cellMap, setCellMap] = useState<Record<string, CellInfo>>({});
  const [loading, setLoading] = useState(false);

  const monday = currentDate.startOf('week').day() === 0
    ? currentDate.startOf('week').add(1, 'day')
    : currentDate.startOf('week').add(1, 'day').subtract(currentDate.day() === 0 ? 7 : 0, 'day');
  const weekStart = currentDate.subtract(currentDate.day() === 0 ? 6 : currentDate.day() - 1, 'day');
  const days: Dayjs[] = Array.from({ length: 7 }, (_, i) => weekStart.add(i, 'day'));

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const start = days[0].format('YYYY-MM-DD');
      const end = days[6].format('YYYY-MM-DD');
      const params: any = {
        store_id: storeId,
        view: 'week',
        start_date: start,
        end_date: end,
      };
      if (filters.product_ids?.length) params.product_ids = filters.product_ids;
      if (filters.staff_ids?.length) params.staff_ids = filters.staff_ids;
      if (filters.statuses?.length) params.statuses = filters.statuses;
      if (filters.sources?.length) params.sources = filters.sources;
      if (filters.q) params.q = filters.q;
      const res: any = await api.get('/api/merchant/calendar/cells', { params });
      const map: Record<string, CellInfo> = {};
      (res?.cells || []).forEach((c: CellInfo) => {
        map[c.date] = c;
      });
      setCellMap(map);
    } catch {
      setCellMap({});
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, currentDate.format('YYYY-MM-DD'), JSON.stringify(filters)]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Spin spinning={loading}>
      <Card>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: 8,
          }}
        >
          {days.map((d, idx) => {
            const ds = d.format('YYYY-MM-DD');
            const cell = cellMap[ds];
            const isToday = d.isSame(dayjs(), 'day');
            return (
              <div
                key={ds}
                onClick={() => onCellClick?.(ds, cell ?? null)}
                style={{
                  border: isToday ? '2px solid #1677ff' : '1px solid #f0f0f0',
                  borderRadius: 8,
                  padding: 12,
                  minHeight: 120,
                  cursor: 'pointer',
                  background: '#fff',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>{CN_WEEKDAYS[idx]}</div>
                <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>
                  {d.format('M/D')}
                </div>
                {cell && cell.booking_count > 0 ? (
                  <Tooltip
                    title={`预约 ${cell.booking_count} · 已核 ${cell.verified_count}
占用 ${cell.occupied_rate}% · 收入 ¥${cell.revenue}
取消 ${cell.cancelled_count}`}
                  >
                    <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                      <div style={{ color: '#1677ff', fontWeight: 500 }}>
                        预约 {cell.booking_count}
                      </div>
                      <div style={{ color: '#52c41a' }}>已核 {cell.verified_count}</div>
                      <div style={{ color: '#fa8c16' }}>占用 {cell.occupied_rate}%</div>
                      <div style={{ color: '#722ed1' }}>¥{cell.revenue}</div>
                    </div>
                  </Tooltip>
                ) : (
                  <div style={{ fontSize: 12, color: '#bfbfbf' }}>无预约</div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </Spin>
  );
}
