'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Calendar, Card, Spin, Tooltip, Typography } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import api from '@/lib/api';
import type { CalendarFilters, CellInfo } from './types';

const { Text } = Typography;

interface MonthViewProps {
  storeId: number | null;
  currentDate: Dayjs;
  onPanelChange?: (d: Dayjs) => void;
  onCellClick?: (date: string, cell: CellInfo | null) => void;
  filters: CalendarFilters;
}

export default function MonthView({
  storeId,
  currentDate,
  onPanelChange,
  onCellClick,
  filters,
}: MonthViewProps) {
  const [cellMap, setCellMap] = useState<Record<string, CellInfo>>({});
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const start = currentDate.startOf('month').format('YYYY-MM-DD');
      const end = currentDate.endOf('month').format('YYYY-MM-DD');
      const params: any = {
        store_id: storeId,
        view: 'month',
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
  }, [storeId, currentDate, filters]);

  useEffect(() => {
    load();
  }, [load]);

  const dateCellRender = (value: Dayjs) => {
    const ds = value.format('YYYY-MM-DD');
    const cell = cellMap[ds];
    if (!cell || cell.booking_count === 0) return null;
    const lineText = `预约 ${cell.booking_count} · 已核 ${cell.verified_count} · 占用 ${cell.occupied_rate}% · ¥${cell.revenue}`;
    const tooltipText = `预约 ${cell.booking_count} · 已核 ${cell.verified_count}\n占用 ${cell.occupied_rate}% · 收入 ¥${cell.revenue}\n取消 ${cell.cancelled_count}`;
    return (
      <Tooltip title={<div style={{ whiteSpace: 'pre-line' }}>{tooltipText}</div>}>
        <div
          style={{
            fontSize: 12,
            color: '#1677ff',
            fontWeight: 500,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {lineText}
        </div>
      </Tooltip>
    );
  };

  return (
    <Spin spinning={loading}>
      <Card>
        <Calendar
          value={currentDate}
          fullscreen
          headerRender={() => (
            <div style={{ padding: '8px 12px', textAlign: 'center' }}>
              <Text strong style={{ fontSize: 16 }}>
                {currentDate.format('YYYY 年 M 月')}
              </Text>
            </div>
          )}
          onSelect={(d) => onCellClick?.(d.format('YYYY-MM-DD'), cellMap[d.format('YYYY-MM-DD')] ?? null)}
          onPanelChange={(d) => onPanelChange?.(d)}
          cellRender={(current, info) => {
            if (info.type === 'date') return dateCellRender(current as Dayjs);
            return null;
          }}
        />
      </Card>
    </Spin>
  );
}
